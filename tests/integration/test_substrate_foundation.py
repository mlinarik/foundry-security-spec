"""Storage boundary proofs for FR-117/138; later queue/auth tests join this suite."""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from foundry_v2.contracts.models import Conflict, Unavailable
from foundry_v2.substrate.owner import Owner
from foundry_v2.substrate.transactions import mutate


@pytest.fixture
def owner(tmp_path):
    with Owner(tmp_path / "substrate") as owner:
        yield owner


def test_owner_rejects_a_second_process_and_releases_on_exit(owner):
    program = "from foundry_v2.substrate.owner import Owner; Owner(__import__('sys').argv[1])"
    competing = subprocess.run([sys.executable, "-c", program, str(owner.root)], capture_output=True, text=True)
    assert competing.returncode != 0
    assert "owner_locked" in competing.stderr
    root = owner.root
    epoch = owner.epoch
    owner.close()
    with Owner(root) as replacement:
        assert replacement.epoch == epoch + 1


def test_database_pragmas_and_required_tables(owner):
    with owner.transaction() as db:
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert db.execute("PRAGMA synchronous").fetchone()[0] == 2
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required = {'installations', 'evaluations', 'targets', 'evaluation_targets', 'config_revisions',
                'sessions', 'tasks', 'claims', 'findings', 'finding_observations', 'evidence',
                'validation_attempts', 'reports', 'publications', 'outbox', 'index_generations',
                'code_units', 'call_edges', 'security_documents', 'coverage_items', 'coverage_attempts',
                'model_calls', 'provider_state', 'operator_messages', 'checkpoint_tuples',
                'checkpoint_writes', 'blobs', 'audit_events', 'idempotency_keys', 'credentials'}
    assert required <= tables


def test_concurrent_starts_have_one_winner(owner):
    def start(_):
        try:
            return owner.reserve_evaluation(expected_version=0)
        except Conflict:
            return None
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(start, range(16)))
    assert len([result for result in results if result]) == 1
    with owner.transaction() as db:
        assert db.execute("SELECT count(*) FROM evaluations").fetchone()[0] == 1


def test_transaction_exception_preserves_prior_state(owner):
    with pytest.raises(RuntimeError):
        with owner.transaction() as db:
            db.execute("UPDATE installations SET version=100")
            raise RuntimeError("crash before commit")
    with owner.transaction() as db:
        assert db.execute("SELECT version FROM installations").fetchone()[0] == 0


def test_idempotency_receipt_and_effect_commit_once_under_race(owner):
    def call(_):
        def effect(db):
            db.execute("UPDATE installations SET version=version+1")
            return {"version": db.execute("SELECT version FROM installations").fetchone()[0]}
        return mutate(owner, "actor", "POST", "/fixture", "same-key", {"requested": 1}, effect)
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(call, range(16)))
    assert results == [{"version": 1}] * 16
    with pytest.raises(Conflict):
        mutate(owner, "actor", "POST", "/fixture", "same-key", {"requested": 2}, lambda db: {})


def test_receipt_scope_and_failure_rollback(owner):
    def failed(db):
        db.execute("UPDATE installations SET version=123")
        raise RuntimeError("interrupted")
    with pytest.raises(RuntimeError):
        mutate(owner, "a", "POST", "/fixture", "key", {}, failed)
    with owner.transaction() as db:
        assert db.execute("SELECT version FROM installations").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM idempotency_keys").fetchone()[0] == 0
    assert mutate(owner, "a", "POST", "/fixture", "key", {}, lambda db: {"ok": 1}) == {"ok": 1}
    assert mutate(owner, "b", "POST", "/fixture", "key", {}, lambda db: {"ok": 2}) == {"ok": 2}


def test_closed_owner_fails_closed(owner):
    owner.close()
    with pytest.raises(Unavailable):
        with owner.transaction():
            pytest.fail("closed owner served a transaction")


def test_committed_evaluation_survives_replacement(owner):
    evaluation = owner.reserve_evaluation(0)
    root = owner.root
    owner.close()
    with Owner(root) as restored:
        with restored.transaction() as db:
            assert db.execute("SELECT active_evaluation_id FROM installations").fetchone()[0] == evaluation
        with pytest.raises(Conflict):
            restored.reserve_evaluation(1)
