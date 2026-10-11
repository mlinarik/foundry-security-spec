"""Operator service. Workers remain gated until full runtime prerequisites pass."""
import os

from foundry_v2.api.server import serve, settings
from foundry_v2.orchestrator.app import create_app
from foundry_v2.workers.client import SubstrateClient


def main():
    config, auth = settings()
    substrate = SubstrateClient(config['substrate_url'], os.environ.get('FOUNDRY_SUBSTRATE_CA'), allow_http=config['transport']=='http')
    try:
        serve(create_app(auth, substrate, require_tls=config['transport']=='https'), 'foundry-v2-orchestrator',config['transport'])
    finally:
        substrate.close()
        auth.reviewer.close()


if __name__ == "__main__":
    main()
