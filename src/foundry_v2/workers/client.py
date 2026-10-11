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

    def request(self, method, path, bearer=None, payload=None, key=None, content=None, binary=False):
        token = bearer or (self.token_file.read_text().strip() if self.token_file else None)
        headers = {'Authorization': 'Bearer ' + token} if token else {}
        if key:
            headers['Idempotency-Key'] = key
        try:
            response = self.client.request(method, self.url + path, headers=headers, json=payload,content=content)
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
        return response.content if binary else response.json()

    def read_blob(self,evaluation,digest):
        from urllib.parse import quote
        return self.request('GET',f'/substrate/v1/evaluations/{quote(evaluation,safe="")}/blobs/{quote(digest,safe="")}',binary=True)

    def write_blob(self,evaluation,data,key):
        import hashlib
        from urllib.parse import quote
        digest=hashlib.sha256(data).hexdigest()
        return self.request('PUT',f'/substrate/v1/evaluations/{quote(evaluation,safe="")}/blobs/{digest}',content=data,key=key)

    def get(self, path, bearer=None):
        return self.request('GET', path, bearer)

    def ready(self):
        try:
            return self.client.get(self.url + '/readyz').status_code == 200
        except httpx.HTTPError:
            return False

    def close(self):
        self.client.close()
