"""Fault injection at the immutable-artifact and consistent-backup boundaries."""
import hashlib

import pytest

from foundry_v2.contracts.models import Conflict
from foundry_v2.substrate.owner import Owner
from foundry_v2.substrate.blobs import BlobStore
from foundry_v2.substrate.backup import backup, restore


@pytest.fixture
def owner(tmp_path):
    with Owner(tmp_path/'owner') as instance:
        yield instance


def test_blob_hash_verified_before_visibility_and_stable_retry(owner):
    store = BlobStore(owner)
    value = b'complete immutable artifact'
    digest = hashlib.sha256(value).hexdigest()
    assert store.put(value, expected_digest=digest) == digest
    assert store.put(value, expected_digest=digest) == digest
    assert store.read(digest) == value
    with pytest.raises(ValueError):
        store.put(b'different', expected_digest=digest)
    with owner.transaction() as db:
        assert db.execute("SELECT count(*) FROM blobs").fetchone()[0] == 1


def test_failed_visibility_commit_keeps_old_and_hides_orphan(owner, monkeypatch):
    store = BlobStore(owner)
    old = store.put(b'old complete state')
    new_digest = hashlib.sha256(b'new interrupted state').hexdigest()
    def fail(*args):
        raise RuntimeError('crash between rename and metadata commit')
    monkeypatch.setattr(store, '_publish', fail)
    with pytest.raises(RuntimeError):
        store.put(b'new interrupted state')
    assert store.read(old) == b'old complete state'
    with pytest.raises(KeyError):
        store.read(new_digest)


@pytest.mark.parametrize('digest', ['../outside', '/absolute', 'A'*64, '0'*63, 'g'*64])
def test_blob_path_input_cannot_escape_owner(owner, digest):
    with pytest.raises(ValueError):
        BlobStore(owner).read(digest)


def test_corrupt_committed_blob_is_visible_error(owner):
    store = BlobStore(owner)
    digest = store.put(b'valid')
    store.path(digest).write_bytes(b'corrupted')
    with pytest.raises(ValueError, match='digest'):
        store.read(digest)


def test_backup_restore_includes_referenced_blob_and_active_evaluation(owner, tmp_path):
    evaluation = owner.reserve_evaluation(0)
    digest = BlobStore(owner).put(b'checkpoint artifact')
    destination = tmp_path/'backup'
    backup(owner, destination)
    assert (destination/'manifest.json').exists()
    restored_path = tmp_path/'restored'
    restore(destination, restored_path)
    with Owner(restored_path) as restored:
        assert BlobStore(restored).read(digest) == b'checkpoint artifact'
        with restored.transaction() as db:
            assert db.execute('SELECT active_evaluation_id FROM installations').fetchone()[0] == evaluation


def test_corrupt_backup_never_publishes_partial_restore(owner, tmp_path):
    digest = BlobStore(owner).put(b'checkpoint artifact')
    destination = tmp_path/'backup'
    backup(owner, destination)
    (destination/'blobs'/digest).write_bytes(b'corrupt')
    restored_path = tmp_path/'restored'
    with pytest.raises(ValueError, match='digest'):
        restore(destination, restored_path)
    assert not restored_path.exists()


def test_restore_refuses_existing_owner_directory(owner, tmp_path):
    destination = tmp_path/'backup'
    backup(owner, destination)
    with pytest.raises(Conflict):
        restore(destination, owner.root)
