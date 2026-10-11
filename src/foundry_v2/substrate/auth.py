"""Hashed session credentials; a worker can never authenticate as an operator."""
import hashlib
import math
import time

from foundry_v2.api.auth import Forbidden, Principal, Unauthorized
from foundry_v2.contracts.models import Conflict, new_id


class SessionAuth:
    def __init__(self, owner, clock=time.time):
        self.owner = owner
        self.clock = clock

    def issue(self, evaluation, session, role, token, expires_at):
        if len(token) < 32 or not math.isfinite(expires_at) or expires_at <= self.clock():
            raise ValueError('A strong token and future expiry are required')
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.owner.transaction() as db:
            return self.issue_in_transaction(db,evaluation,session,role,digest,expires_at)

    def issue_in_transaction(self,db,evaluation,session,role,digest,expires_at):
        if not math.isfinite(expires_at) or expires_at <= self.clock():
            raise ValueError('A future expiry is required')
        row = db.execute('SELECT evaluation_id,role,state FROM sessions WHERE session_id=?', (session,)).fetchone()
        if not row or row['evaluation_id'] != evaluation or row['role'] != role or row['state'] not in ('registered','running'):
            raise Forbidden('session_scope_mismatch')
        existing = db.execute('SELECT * FROM credentials WHERE token_hash=?', (digest,)).fetchone()
        if existing:
            if (existing['evaluation_id'],existing['session_id'],existing['role'],existing['expires_at']) != (evaluation,session,role,expires_at) or existing['revoked_at'] is not None:
                raise Conflict('credential_identity_conflict')
            return existing['credential_id']
        identity = new_id()
        db.execute('INSERT INTO credentials(credential_id,evaluation_id,session_id,role,token_hash,expires_at) VALUES(?,?,?,?,?,?)',
                   (identity,evaluation,session,role,digest,expires_at))
        return identity

    def authenticate(self, token, evaluation):
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.owner.transaction() as db:
            row = db.execute('SELECT c.*,s.state FROM credentials c JOIN sessions s USING(session_id) WHERE token_hash=?', (digest,)).fetchone()
            if not row or row['revoked_at'] is not None or row['expires_at'] <= self.clock() or row['state'] not in ('registered','running','draining'):
                raise Unauthorized('invalid_session_credential')
            if row['evaluation_id'] != evaluation:
                raise Forbidden('evaluation_scope_mismatch')
            return Principal(row['credential_id'], 'worker', evaluation, row['session_id'], row['role'])

    def has_token(self, token):
        with self.owner.transaction() as db:
            return db.execute('SELECT 1 FROM credentials WHERE token_hash=?',
                              (hashlib.sha256(token.encode()).hexdigest(),)).fetchone() is not None

    def revoke_session(self, session):
        with self.owner.transaction() as db:
            db.execute('UPDATE credentials SET revoked_at=? WHERE session_id=? AND revoked_at IS NULL', (self.clock(),session))
