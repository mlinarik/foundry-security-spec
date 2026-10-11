"""Consistent SQLite backup plus verified immutable artifact manifest."""
from contextlib import contextmanager, closing
import hashlib
import json
from pathlib import Path
import os
import shutil
import sqlite3
import tempfile

from foundry_v2.contracts.models import Conflict
from foundry_v2.substrate.blobs import BlobStore, sync_directory, write_complete
from foundry_v2.substrate.migrate import SCHEMA_VERSION


@contextmanager
def staging_for(destination):
    destination = Path(destination).resolve()
    if destination.exists():
        raise Conflict('destination_exists', 'Backup and restore require a new directory')
    destination.parent.mkdir(parents=True,exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.foundry-staging-',dir=destination.parent)).resolve()
    try:
        yield stage
        if destination.exists():
            raise Conflict('destination_exists')
        sync_directory(stage)
        os.rename(stage,destination)
        sync_directory(destination.parent)
    finally:
        if stage.exists():
            # Only recursively remove the exact temporary directory created here.
            if stage.parent!=destination.parent or not stage.name.startswith('.foundry-staging-'):
                raise RuntimeError('Unsafe staging cleanup path')
            shutil.rmtree(stage)


def backup(owner,destination):
    with staging_for(destination) as stage:
        (stage/'blobs').mkdir()
        with owner.consistent_snapshot() as source:
            with closing(sqlite3.connect(stage/'state.sqlite')) as target:
                source.backup(target)
            database = (stage/'state.sqlite').read_bytes()
            manifest = {'format_version':1,'schema_version':SCHEMA_VERSION,
                        'database_sha256':hashlib.sha256(database).hexdigest(), 'blobs':[]}
            store = BlobStore(owner)
            for row in source.execute('SELECT digest,byte_length,media_type FROM blobs ORDER BY digest'):
                content = store.path(row['digest']).read_bytes()
                if len(content)!=row['byte_length'] or hashlib.sha256(content).hexdigest()!=row['digest']:
                    raise ValueError('Backup artifact digest mismatch')
                write_complete(stage/'blobs'/row['digest'],content)
                manifest['blobs'].append(dict(row))
            # Persist the backup database and manifest before publishing the directory.
            with open(stage/'state.sqlite','r+b') as database_file:
                os.fsync(database_file.fileno())
            write_complete(stage/'manifest.json',json.dumps(manifest,sort_keys=True).encode())
            sync_directory(stage/'blobs')


def restore(source,destination):
    source = Path(source).resolve()
    manifest = json.loads((source/'manifest.json').read_text())
    if manifest.get('format_version')!=1 or manifest.get('schema_version')!=SCHEMA_VERSION:
        raise ValueError('Unsupported backup schema or format')
    database = (source/'state.sqlite').read_bytes()
    if hashlib.sha256(database).hexdigest()!=manifest['database_sha256']:
        raise ValueError('Backup database digest mismatch')
    with staging_for(destination) as stage:
        write_complete(stage/'state.sqlite',database)
        (stage/'blobs').mkdir()
        # Query only the staged copy: no writes or locks against the backup source.
        with closing(sqlite3.connect(stage/'state.sqlite')) as db:
            db.row_factory = sqlite3.Row
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchone():
                raise ValueError('Backup database integrity failure')
            if db.execute('PRAGMA user_version').fetchone()[0]!=SCHEMA_VERSION:
                raise ValueError('Backup database schema mismatch')
            rows = [dict(row) for row in db.execute('SELECT digest,byte_length,media_type FROM blobs ORDER BY digest')]
            if rows!=manifest['blobs']:
                raise ValueError('Backup manifest does not match database')
            for row in rows:
                digest = row['digest']
                # Validate before using any value from the backup as a path component.
                if len(digest)!=64 or any(character not in '0123456789abcdef' for character in digest):
                    raise ValueError('Invalid backup artifact digest')
                content = (source/'blobs'/digest).read_bytes()
                if len(content)!=row['byte_length'] or hashlib.sha256(content).hexdigest()!=digest:
                    raise ValueError('Backup artifact digest mismatch')
                write_complete(stage/'blobs'/digest,content)
        sync_directory(stage/'blobs')
