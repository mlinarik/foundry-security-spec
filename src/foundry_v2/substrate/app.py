"""Authenticated owner service. Unsupported operations fail closed."""
from contextlib import asynccontextmanager
import asyncio
import hashlib
import hmac
import time

from fastapi import FastAPI, Request
from pydantic import BaseModel, ConfigDict, Field

from foundry_v2.api.auth import Forbidden, Principal, bearer
from foundry_v2.api.common import configure, idempotency
from foundry_v2.contracts.models import Claim, ClaimRequest, ClaimWrite, Conflict, Heartbeat, Page, Receipt, SessionRegistration, TaskCreate, TaskUpdate, Unavailable, new_id
from foundry_v2.substrate.audit import event
from foundry_v2.substrate.auth import SessionAuth
from foundry_v2.substrate.claims import WorkQueues
from foundry_v2.substrate.snapshots import require_evaluation, snapshot, sequence
from foundry_v2.substrate.transactions import mutate


class CredentialProvision(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    session_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    token: str = Field(min_length=32, max_length=256, repr=False)
    expires_at: float = Field(gt=0, allow_inf_nan=False)


def create_app(owner, operator_auth, infrastructure_token, stale_seconds=60, release_limit=3, reaper_seconds=5, require_tls=True):
    if len(infrastructure_token) < 32:
        raise ValueError('Strong dedicated infrastructure token required')
    sessions = SessionAuth(owner)
    queues = WorkQueues(owner,stale_seconds,release_limit,restart_grace=stale_seconds)
    if not 0 < reaper_seconds < stale_seconds:
        raise ValueError('Reaper interval must be positive and below stale threshold')

    @asynccontextmanager
    async def lifespan(app):
        async def reap():
            while True:
                await asyncio.sleep(reaper_seconds)
                try:
                    await asyncio.to_thread(queues.reap)
                    app.state.reaper_failed=False
                except Exception:
                    app.state.reaper_failed=True
        app.state.reaper_failed=False
        task=asyncio.create_task(reap())
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    app = FastAPI(title='Foundry-v2 substrate', lifespan=lifespan, docs_url=None, redoc_url=None)
    configure(app)

    def actor(request, evaluation=None):
        token = bearer(request,require_tls)
        if hmac.compare_digest(token.encode(), infrastructure_token.encode()):
            return Principal('orchestrator-lifecycle', 'infrastructure')
        if sessions.has_token(token):
            if evaluation is None:
                raise Forbidden('worker_scope_required')
            return sessions.authenticate(token, evaluation)
        return operator_auth.authenticate(token)

    def infrastructure(request):
        principal = actor(request)
        if principal.kind != 'infrastructure':
            raise Forbidden('infrastructure_authority_required')
        return principal

    @app.get('/healthz')
    def health():
        return {'status': 'alive'}

    @app.get('/readyz')
    def ready():
        if app.state.reaper_failed:
            raise Unavailable('heartbeat_reaper_unavailable')
        with owner.transaction() as db:
            db.execute('SELECT 1').fetchone()
        return {'status': 'ready'}

    @app.get('/substrate/v1/installation')
    def installation(request: Request):
        principal = actor(request)
        if principal.kind not in ('operator','infrastructure'):
            raise Forbidden('control_identity_required')
        with owner.transaction() as db:
            return dict(db.execute('SELECT installation_id,active_evaluation_id,owner_epoch,version FROM installations').fetchone())

    @app.get('/substrate/v1/evaluations/{evaluation_id}/snapshot', operation_id='readSubstrateSnapshot')
    def read_snapshot(evaluation_id: str, request: Request):
        principal = actor(request, evaluation_id)
        # Full snapshots include other sessions and must not leak to reproduction workers.
        if principal.kind == 'worker':
            raise Forbidden('control_identity_required')
        return snapshot(owner, evaluation_id)

    @app.post('/substrate/v1/evaluations/{evaluation_id}/sessions', response_model=Receipt, operation_id='registerSession')
    def register(evaluation_id: str, payload: SessionRegistration, request: Request):
        principal = infrastructure(request)
        def effect(db):
            require_evaluation(db, evaluation_id)
            existing = db.execute('SELECT * FROM sessions WHERE session_id=?', (payload.session_id,)).fetchone()
            if existing:
                raise Conflict('session_identity_conflict')
            db.execute('INSERT INTO sessions(session_id,evaluation_id,role,slot,incarnation,pod_name,state,heartbeat_at) VALUES(?,?,?,?,?,?,?,?)',
                       (payload.session_id,evaluation_id,payload.role,payload.slot,payload.incarnation,payload.pod_name,'registered',time.time()))
            event(db, principal, evaluation_id, 'session.register', payload.session_id, version=0)
            return {'request_id': request.state.request_id, 'resource_id': payload.session_id, 'version': 0, 'state': 'registered'}
        return mutate(owner, principal.subject, 'POST', request.url.path, idempotency(request), payload.model_dump(), effect)

    @app.post('/substrate/v1/evaluations/{evaluation_id}/credentials', response_model=Receipt)
    def provision(evaluation_id: str, payload: CredentialProvision, request: Request):
        principal=infrastructure(request)
        safe_payload=payload.model_dump(exclude={'token'})
        safe_payload['token_hash']=hashlib.sha256(payload.token.encode()).hexdigest()
        def effect(db):
            try:
                identity=sessions.issue_in_transaction(db,evaluation_id,payload.session_id,payload.role,safe_payload['token_hash'],payload.expires_at)
            except ValueError:
                from foundry_v2.contracts.models import DomainError
                raise DomainError('invalid_credential_expiry') from None
            event(db,principal,evaluation_id,'credential.issue',identity)
            return {'request_id':request.state.request_id,'resource_id':identity,'version':0}
        return mutate(owner,principal.subject,'POST',request.url.path,idempotency(request),safe_payload,effect)

    @app.delete('/substrate/v1/evaluations/{evaluation_id}/sessions/{session_id}/credentials', response_model=Receipt)
    def revoke(evaluation_id: str, session_id: str, request: Request):
        principal=infrastructure(request)
        def effect(db):
            row = db.execute('SELECT evaluation_id FROM sessions WHERE session_id=?', (session_id,)).fetchone()
            if row is None or row[0] != evaluation_id:
                raise Forbidden('session_scope_mismatch')
            db.execute('UPDATE credentials SET revoked_at=? WHERE session_id=? AND revoked_at IS NULL',(time.time(),session_id))
            event(db,principal,evaluation_id,'credential.revoke',session_id)
            return {'request_id':request.state.request_id,'resource_id':session_id,'version':0}
        return mutate(owner,principal.subject,'DELETE',request.url.path,idempotency(request),{},effect)

    @app.get('/substrate/v1/evaluations/{evaluation_id}/generations', operation_id='readGenerations')
    def generations(evaluation_id: str, request: Request):
        principal = actor(request, evaluation_id)
        if principal.kind == 'worker' and principal.role == 'validator':
            raise Forbidden('reproduction_access_denied')
        with owner.transaction() as db:
            require_evaluation(db, evaluation_id)
            items = [dict(r) for r in db.execute('SELECT generation_id,target_id,source_commit,state,parent_generation FROM index_generations WHERE evaluation_id=? AND state=\'ready\' ORDER BY generation_id', (evaluation_id,))]
            return {'items': items, 'next_cursor': None, 'snapshot_id': sequence(db)}

    @app.post('/substrate/v1/evaluations/{evaluation_id}/sessions/heartbeat', response_model=Receipt, operation_id='heartbeat')
    def heartbeat(evaluation_id: str, payload: Heartbeat, request: Request):
        principal=actor(request,evaluation_id)
        if principal.session_id != payload.session_id:
            raise Forbidden('session_scope_mismatch')
        return queues.heartbeat(principal,payload.incarnation,idempotency(request),payload.last_event_sequence)

    @app.post('/substrate/v1/evaluations/{evaluation_id}/tasks', response_model=Receipt, operation_id='submitTask')
    def submit_task(evaluation_id: str, payload: TaskCreate, request: Request):
        return queues.add(actor(request,evaluation_id),evaluation_id,payload.model_dump(exclude_none=True),idempotency(request))

    @app.get('/substrate/v1/evaluations/{evaluation_id}/tasks', response_model=Page, operation_id='readTasks')
    def read_tasks(evaluation_id: str, request: Request, cursor: str | None=None, limit: int=100):
        return queues.list(actor(request,evaluation_id),evaluation_id,cursor,limit)

    @app.patch('/substrate/v1/evaluations/{evaluation_id}/tasks/{task_id}', response_model=Receipt, operation_id='updateTask')
    def edit_task(evaluation_id: str, task_id: str, payload: TaskUpdate, request: Request):
        return queues.edit(actor(request,evaluation_id),evaluation_id,task_id,payload.model_dump(exclude_none=True),idempotency(request))

    @app.post('/substrate/v1/evaluations/{evaluation_id}/claims', response_model=Claim, operation_id='claimWork')
    def claim(evaluation_id: str, payload: ClaimRequest, request: Request):
        principal=actor(request,evaluation_id)
        if payload.role != principal.role:
            raise Forbidden('role_scope_mismatch')
        return queues.claim(principal,payload.resource_type,'work',idempotency(request))

    @app.patch('/substrate/v1/evaluations/{evaluation_id}/claims/{resource_id}', response_model=Receipt, operation_id='writeClaimedWork')
    def write_claim(evaluation_id: str, resource_id: str, payload: ClaimWrite, request: Request):
        return queues.write(actor(request,evaluation_id),resource_id,payload.claim_generation,payload.expected_version,payload.operation,payload.payload,idempotency(request))

    @app.api_route('/{path:path}', methods=['GET','POST','PUT','PATCH','DELETE'])
    def unavailable(path: str, request: Request):
        actor(request)
        raise Unavailable('operation_not_ready', 'This operation is not available in the current implementation')

    return app
