"""Abrupt owner loss, newer-schema refusal and migration rollback."""
from contextlib import closing
import sqlite3
import subprocess
import sys
import os

import pytest
from foundry_v2.contracts.models import Conflict, Unavailable
from foundry_v2.substrate.owner import Owner
from foundry_v2.substrate.migrate import migrate


@pytest.mark.skipif(os.name=='nt', reason='Abrupt WAL recovery is verified on the production Linux filesystem')
def test_killed_owner_releases_os_lock_and_preserves_committed_start(tmp_path):
    root = tmp_path/'owner'
    program = '''
import sys,time
from foundry_v2.substrate.owner import Owner
owner=Owner(sys.argv[1])
print(owner.reserve_evaluation(0),flush=True)
time.sleep(300)
'''
    child = subprocess.Popen([sys.executable,'-c',program,str(root)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        evaluation = child.stdout.readline().strip()
        assert evaluation
        with pytest.raises(Conflict):
            Owner(root)
    finally:
        child.kill()
        child.wait(timeout=10)
        child.stdout.close()
        child.stderr.close()
    with Owner(root) as replacement:
        assert replacement.epoch == 2
        with replacement.transaction() as db:
            assert db.execute('SELECT active_evaluation_id FROM installations').fetchone()[0] == evaluation


def test_newer_schema_refusal_does_not_strand_owner_lock(tmp_path):
    root = tmp_path/'owner'
    with Owner(root):
        pass
    with closing(sqlite3.connect(root/'state.sqlite')) as db:
        db.execute('PRAGMA user_version=999')
    with pytest.raises(Unavailable,match='unsupported_schema'):
        Owner(root)
    with closing(sqlite3.connect(root/'state.sqlite')) as db:
        db.execute('PRAGMA user_version=1')
    with Owner(root):
        pass


def test_failed_migration_keeps_existing_tables_and_creates_backup(tmp_path):
    with closing(sqlite3.connect(tmp_path/'state.sqlite',isolation_level=None)) as db:
        db.execute('CREATE TABLE installations (fixture TEXT)')
        db.execute("INSERT INTO installations VALUES('prior complete data')")
        with pytest.raises(sqlite3.OperationalError):
            migrate(db,tmp_path)
        assert db.execute('SELECT fixture FROM installations').fetchone()[0] == 'prior complete data'
        assert db.execute('PRAGMA user_version').fetchone()[0] == 0
    backups = list(tmp_path.glob('pre-migration-*.sqlite'))
    assert len(backups) == 1
    with closing(sqlite3.connect(backups[0])) as original:
        assert original.execute('SELECT fixture FROM installations').fetchone()[0] == 'prior complete data'


def test_only_one_installation_row_and_foreign_keys_are_enforced(tmp_path):
    with Owner(tmp_path/'owner') as owner:
        with pytest.raises(sqlite3.IntegrityError):
            with owner.transaction() as db:
                db.execute("INSERT INTO installations(installation_id) VALUES('second')")
        with pytest.raises(sqlite3.IntegrityError):
            with owner.transaction() as db:
                db.execute("INSERT INTO evaluations(evaluation_id,installation_id,state) VALUES('e','missing','configured')")


def test_owner_epoch_mismatch_fences_transactions_and_backups(tmp_path):
    with Owner(tmp_path/'owner') as owner:
        with owner.transaction() as db:
            db.execute('UPDATE installations SET owner_epoch=owner_epoch+1')
        for context in (owner.transaction,owner.consistent_snapshot):
            with pytest.raises(Unavailable,match='owner_fenced'):
                with context():
                    pytest.fail('Fenced owner served a request')
