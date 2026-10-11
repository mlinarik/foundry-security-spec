from contextlib import closing
from importlib.resources import files
import sqlite3

from foundry_v2.substrate.owner import Owner


def test_runtime_migration_backs_up_and_preserves_version_one_state(tmp_path):
    with closing(sqlite3.connect(tmp_path/'state.sqlite')) as db:
        db.executescript(files('foundry_v2.substrate').joinpath('migrations/001_initial.sql').read_text())
        db.execute("INSERT INTO installations(installation_id) VALUES('legacy')")
        db.execute('PRAGMA user_version=1'); db.commit()
    with Owner(tmp_path) as owner:
        assert owner.installation_id=='legacy'
        with owner.transaction() as db:
            assert db.execute('PRAGMA user_version').fetchone()[0]==2
            assert db.execute('SELECT COUNT(*) FROM checkpoint_pending').fetchone()[0]==0
    backups=list(tmp_path.glob('pre-migration-*.sqlite'))
    assert len(backups)==1
    with closing(sqlite3.connect(backups[0])) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==1
        assert db.execute('SELECT installation_id FROM installations').fetchone()[0]=='legacy'
