"""Environment inputs and TLS serving shared by the two service processes."""
import argparse
import json
import os
from pathlib import Path

import uvicorn

from foundry_v2.api.auth import OperatorAuth, TokenReviewer


def settings():
    config = json.loads(Path(os.environ['FOUNDRY_SERVICE_CONFIG']).read_text())
    required = ('kubernetes_api_url','tokenreview_audience','operator_subjects','operator_groups','transport')
    if any(key not in config for key in required):
        raise ValueError('Missing service identity configuration')
    if config['transport'] not in ('http','https'):
        raise ValueError('Explicit HTTP/HTTPS transport required')
    if not isinstance(config['operator_subjects'],list) or not isinstance(config['operator_groups'],list):
        raise ValueError('Operator subjects/groups must be explicit lists')
    if any(not isinstance(item,str) or not item for key in ('operator_subjects','operator_groups') for item in config[key]):
        raise ValueError('Operator identities must be nonempty strings')
    reviewer = TokenReviewer(config['kubernetes_api_url'], os.environ['FOUNDRY_KUBERNETES_CA'],
                             os.environ['FOUNDRY_TOKENREVIEW_TOKEN_FILE'], config['tokenreview_audience'])
    return config, OperatorAuth(reviewer, config['operator_subjects'], config['operator_groups'], config['tokenreview_audience'])


def serve(app, prog, transport='https'):
    parser = argparse.ArgumentParser(prog=prog)
    parser.add_argument('--host',default='0.0.0.0')
    parser.add_argument('--port',type=int,default=8443 if transport=='https' else 8080)
    args = parser.parse_args()
    cert = os.environ['FOUNDRY_TLS_CERT_FILE'] if transport=='https' else None
    key = os.environ['FOUNDRY_TLS_KEY_FILE'] if transport=='https' else None
    if transport=='https' and (not Path(cert).is_file() or not Path(key).is_file()):
        raise ValueError('TLS certificate/key files are required')
    uvicorn.run(app, host=args.host, port=args.port, workers=1,
                ssl_certfile=cert, ssl_keyfile=key, proxy_headers=False, access_log=False)
