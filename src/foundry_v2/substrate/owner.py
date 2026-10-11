"""Single-process SQLite ownership and local integrity fencing.

The process lock does not replace CSI RWOP/node fencing: deployment preflight
must establish those prerequisites before the production service is exposed.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
import threading
import time

from foundry_v2.contracts.models import Conflict, Unavailable, new_id
from foundry_v2.substrate.migrate import migrate


class Owner:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._mutex = threading.RLock()
        self._closed = True
        self._pid = os.getpid()
        self._lock = open(self.root/'owner.lock', 'a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                self._lock.seek(0,2)
                if self._lock.tell() == 0:
                    self._lock.write(b'0')
                    self._lock.flush()
                self._lock.seek(0)
                msvcrt.locking(self._lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._lock.close()
            raise Conflict('owner_locked', 'Another process owns this substrate directory') from None
        try:
            self._db = sqlite3.connect(self.root/'state.sqlite', isolation_level=None, check_same_thread=False)
            self._db.row_factory = sqlite3.Row
            self._db.execute('PRAGMA foreign_keys=ON')
            self._db.execute('PRAGMA journal_mode=WAL')
            self._db.execute('PRAGMA synchronous=FULL')
            self._db.execute('PRAGMA busy_timeout=5000')
            migrate(self._db,self.root)
            self._db.execute('BEGIN IMMEDIATE')
            row = self._db.execute('SELECT installation_id,owner_epoch FROM installations').fetchone()
            if row is None:
                self.installation_id = new_id()
                self._db.execute('INSERT INTO installations(installation_id) VALUES(?)',(self.installation_id,))
            else:
                self.installation_id = row['installation_id']
            self._db.execute('UPDATE installations SET owner_epoch=owner_epoch+1')
            self.epoch = self._db.execute('SELECT owner_epoch FROM installations').fetchone()[0]
            self._db.commit()
            self._closed = False
        except BaseException:
            if hasattr(self,'_db'):
                self._db.close()
            self._unlock()
            raise

    def _unlock(self):
        if self._lock.closed:
            return
        if os.name == 'nt':
            import msvcrt
            self._lock.seek(0)
            msvcrt.locking(self._lock.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            fcntl.flock(self._lock.fileno(),fcntl.LOCK_UN)
        self._lock.close()

    @contextmanager
    def transaction(self):
        with self._mutex:
            if self._closed or os.getpid()!=self._pid:
                raise Unavailable('owner_unavailable')
            if self._db.in_transaction:
                raise Conflict('nested_transaction', 'Compose mutations in the current transaction')
            try:
                self._db.execute('BEGIN IMMEDIATE')
                row = self._db.execute('SELECT owner_epoch FROM installations WHERE installation_id=?',(self.installation_id,)).fetchone()
                if row is None or row[0]!=self.epoch:
                    raise Unavailable('owner_fenced')
                yield self._db
                self._db.commit()
            except BaseException:
                self._db.rollback()
                raise

    def reserve_evaluation(self, expected_version):
        with self.transaction() as db:
            row = db.execute('SELECT active_evaluation_id,version FROM installations').fetchone()
            if row['version']!=expected_version or row['active_evaluation_id'] is not None:
                raise Conflict('active_evaluation', 'Version changed or an evaluation already owns this installation')
            evaluation = new_id()
            db.execute('INSERT INTO evaluations(evaluation_id,installation_id,state,started_at) VALUES(?,?,?,?)',
                       (evaluation,self.installation_id,'configured',time.time()))
            db.execute('UPDATE installations SET active_evaluation_id=?,version=version+1',(evaluation,))
            return evaluation

    @contextmanager
    def consistent_snapshot(self):
        """Hold the owner's lane while backup and blob-manifest readers run."""
        with self._mutex:
            if self._closed or os.getpid()!=self._pid:
                raise Unavailable('owner_unavailable')
            if self._db.in_transaction:
                raise Conflict('nested_transaction')
            row = self._db.execute('SELECT owner_epoch FROM installations WHERE installation_id=?',(self.installation_id,)).fetchone()
            if row is None or row[0]!=self.epoch:
                raise Unavailable('owner_fenced')
            yield self._db

    def close(self):
        with self._mutex:
            if not self._closed:
                self._db.close()
                self._closed = True
                if os.getpid()==self._pid:
                    self._unlock()
                else:
                    # A forked child must not unlock the parent's shared file description.
                    self._lock.close()

    def __enter__(self):
        return self

    def __exit__(self,*args):
        self.close()
