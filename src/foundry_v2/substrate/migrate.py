"""Migrations run only while the lifetime owner lock is held."""
from importlib.resources import files
from contextlib import closing
import sqlite3
import time

from foundry_v2.contracts.models import Unavailable

SCHEMA_VERSION = 1


def migrate(connection, root):
    current = connection.execute('PRAGMA user_version').fetchone()[0]
    if current > SCHEMA_VERSION:
        raise Unavailable('unsupported_schema', 'Database schema is newer than this binary')
    if current == SCHEMA_VERSION:
        return
    tables = connection.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    if tables:
        backup_path = root / f'pre-migration-{time.time_ns()}.sqlite'
        with closing(sqlite3.connect(backup_path)) as destination:
            connection.backup(destination)
    script = files('foundry_v2.substrate').joinpath('migrations/001_initial.sql').read_text(encoding='utf-8')
    try:
        connection.executescript('BEGIN IMMEDIATE;\n'+script+'\nPRAGMA user_version=1;\nCOMMIT;')
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
