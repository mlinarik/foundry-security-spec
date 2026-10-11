"""Immutable artifacts: durable file first, transactional visibility second."""
import hashlib
import os
import re
import tempfile
import time


def sync_directory(directory):
    # Windows does not expose directory fsync. Linux is the production runtime.
    if os.name != 'nt':
        descriptor = os.open(directory,os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def write_complete(path, data):
    with open(path,'xb') as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())


class BlobStore:
    def __init__(self,owner):
        self.owner = owner
        self.directory = owner.root/'blobs'
        self.directory.mkdir(mode=0o700,exist_ok=True)

    def path(self,digest):
        if not isinstance(digest,str) or re.fullmatch(r'[0-9a-f]{64}',digest) is None:
            raise ValueError('Invalid SHA-256 digest')
        return self.directory/digest

    def _publish(self,db,digest,length,media_type):
        db.execute('INSERT OR IGNORE INTO blobs(digest,byte_length,media_type,committed_at) VALUES(?,?,?,?)',
                   (digest,length,media_type,time.time()))

    def put(self,data,expected_digest=None,media_type='application/octet-stream'):
        if not isinstance(data,bytes):
            raise TypeError('Artifact must be bytes')
        digest = hashlib.sha256(data).hexdigest()
        if expected_digest is not None and digest!=expected_digest:
            raise ValueError('Artifact digest mismatch')
        destination = self.path(digest)
        with self.owner.transaction() as db:
            if destination.exists():
                if hashlib.sha256(destination.read_bytes()).hexdigest()!=digest:
                    raise ValueError('Existing artifact digest mismatch')
            else:
                descriptor, temporary = tempfile.mkstemp(prefix='.staging-',dir=self.directory)
                try:
                    with os.fdopen(descriptor,'wb') as output:
                        output.write(data)
                        output.flush()
                        os.fsync(output.fileno())
                    os.replace(temporary,destination)
                    sync_directory(self.directory)
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)
            self._publish(db,digest,len(data),media_type)
        return digest

    def read(self,digest):
        with self.owner.transaction() as db:
            return self.read_in_transaction(db,digest)

    def read_in_transaction(self,db,digest):
        path=self.path(digest)
        row = db.execute('SELECT byte_length FROM blobs WHERE digest=?',(digest,)).fetchone()
        if row is None:
            raise KeyError(digest)
        data = path.read_bytes()
        if len(data)!=row['byte_length'] or hashlib.sha256(data).hexdigest()!=digest:
            raise ValueError('Committed artifact digest mismatch')
        return data

    def orphan_inventory(self):
        """Report invisible leftovers; never guess retention or delete provenance."""
        with self.owner.transaction() as db:
            committed = {row[0] for row in db.execute('SELECT digest FROM blobs')}
            return sorted(path.name for path in self.directory.iterdir()
                          if path.is_file() and path.name not in committed)
