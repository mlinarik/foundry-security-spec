"""Verified TLS substrate transport; never retry ambiguous mutations implicitly."""
from pathlib import Path

import httpx

from foundry_v2.contracts.models import DomainError, Unavailable


class SubstrateClient:
    def __init__(self, url, ca_file, token_file=None, allow_http=False):
        if not url.startswith('https://') and not (allow_http and url.startswith('http://')):
            raise ValueError('Substrate requires HTTPS')
        self.url = url.rstrip('/')
        self.token_file = Path(token_file) if token_file else None
        self.client = httpx.Client(verify=ca_file or True, timeout=10, trust_env=False)

    def request(self, method, path, bearer=None, payload=None, key=None):
        token = bearer or (self.token_file.read_text().strip() if self.token_file else None)
        headers = {'Authorization': 'Bearer ' + token} if token else {}
        if key:
            headers['Idempotency-Key'] = key
        try:
            response = self.client.request(method, self.url + path, headers=headers, json=payload)
        except (httpx.HTTPError, OSError):
            raise Unavailable('substrate_unavailable') from None
        if response.is_error:
            try:
                body = response.json()
            except ValueError:
                body = {}
            error = DomainError(body.get('code', 'substrate_request_failed'), body.get('message', 'Substrate request failed'))
            error.status = response.status_code
            raise error
        return response.json()

    def get(self, path, bearer=None):
        return self.request('GET', path, bearer)

    def ready(self):
        try:
            return self.client.get(self.url + '/readyz').status_code == 200
        except httpx.HTTPError:
            return False

    def close(self):
        self.client.close()
