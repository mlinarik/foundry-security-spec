"""TokenReview-backed operator identities and explicit infrastructure principals."""
from dataclasses import dataclass
from pathlib import Path

import httpx

from foundry_v2.contracts.models import DomainError, Unavailable


class Unauthorized(DomainError):
    status = 401


class Forbidden(DomainError):
    status = 403


@dataclass(frozen=True)
class Principal:
    subject: str
    kind: str
    evaluation_id: str | None = None
    session_id: str | None = None
    role: str | None = None
    purpose: str = 'role'


class TokenReviewer:
    def __init__(self, url, ca_file, token_file, audience):
        if not url.startswith('https://'):
            raise ValueError('TokenReview requires HTTPS')
        self.url = url.rstrip('/') + '/apis/authentication.k8s.io/v1/tokenreviews'
        self.token_file = Path(token_file)
        self.audience = audience
        self.client = httpx.Client(verify=ca_file, timeout=10, trust_env=False)

    def __call__(self, token):
        try:
            response = self.client.post(self.url,
                headers={'Authorization': 'Bearer ' + self.token_file.read_text().strip()},
                json={'apiVersion': 'authentication.k8s.io/v1', 'kind': 'TokenReview',
                      'spec': {'token': token, 'audiences': [self.audience]}})
            response.raise_for_status()
            return response.json().get('status', {})
        except (httpx.HTTPError, OSError, ValueError):
            raise Unavailable('identity_provider_unavailable') from None

    def close(self):
        self.client.close()


class OperatorAuth:
    def __init__(self, reviewer, subjects, groups, audience):
        if not audience:
            raise ValueError('Explicit TokenReview audience required')
        self.reviewer = reviewer
        self.subjects = frozenset(subjects)
        self.groups = frozenset(groups)
        self.audience = audience

    def authenticate(self, token):
        result = self.reviewer(token)
        if result.get('authenticated') is not True or self.audience not in result.get('audiences', []):
            raise Unauthorized('invalid_credential')
        user = result.get('user', {})
        subject = user.get('username')
        if not subject or (subject not in self.subjects and not self.groups.intersection(user.get('groups', []))):
            raise Forbidden('operator_not_allowed')
        return Principal(subject, 'operator')


def bearer(request, require_tls=True):
    if require_tls and request.url.scheme != 'https':
        raise DomainError('tls_required', 'Authenticated APIs require HTTPS')
    scheme, _, token = request.headers.get('authorization', '').partition(' ')
    if scheme.lower() != 'bearer' or not token or len(token) > 16384:
        raise Unauthorized('credential_required')
    return token
