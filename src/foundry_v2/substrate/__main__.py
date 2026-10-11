"""One SQLite owner, one TLS server, no production storage fallback."""
import os
from pathlib import Path

from foundry_v2.api.server import serve, settings
from foundry_v2.substrate.app import create_app
from foundry_v2.substrate.owner import Owner


def main():
    config, auth = settings()
    try:
        with Owner(os.environ['FOUNDRY_DATA_DIR']) as owner:
            token = Path(os.environ['FOUNDRY_INFRASTRUCTURE_TOKEN_FILE']).read_text().strip()
            serve(create_app(owner, auth, token, config['stale_seconds'], config['release_limit'], config['reaper_seconds'],
                             require_tls=config['transport']=='https'), 'foundry-v2-substrate', config['transport'])
    finally:
        auth.reviewer.close()


if __name__ == "__main__":
    main()
