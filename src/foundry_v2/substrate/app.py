"""Authenticated owner service. Unsupported operations fail closed."""
from contextlib import asynccontextmanager
import asyncio
import hashlib
import hmac
import time

from fastapi import FastAPI, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

from foundry_v2.api.auth import Forbidden, Principal, bearer
from foundry_v2.api.common import configure, idempotency
from foundry_v2.contracts.models import Checkpoint, CheckpointWrites, Claim, ClaimRequest, ClaimWrite, ConfigUpdate, Conflict, Control, DomainError, GenerationWrite, Heartbeat, IndexQuery, Page, Receipt, SessionRegistration, StartEvaluation, TaskCreate, TaskUpdate, Unavailable, new_id
from foundry_v2.substrate.audit import event,transcript
from foundry_v2.substrate.auth import SessionAuth
from foundry_v2.substrate.claims import WorkQueues
from foundry_v2.substrate.checkpoints import Checkpoints
from foundry_v2.substrate.generations import Generations
from foundry_v2.substrate.evaluations import Evaluations
from foundry_v2.substrate.lifecycle import LifecycleRecords
from foundry_v2.indexing.service import IndexQueries
from foundry_v2.checkpoints.http_saver import decode_namespace
from foundry_v2.substrate.snapshots import require_evaluation, snapshot, sequence
from foundry_v2.substrate.transactions import mutate


class CredentialProvision(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    session_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    token: str = Field(min_length=32, max_length=256, repr=False)
    expires_at: float = Field(gt=0, allow_inf_nan=False)


class TranscriptAppend(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    kind: Literal['turn','tool-call','tool-result','usage','handoff','failure']
    content: dict


def create_app(owner, operator_auth, infrastructure_token, stale_seconds=60, release_limit=3, reaper_seconds=5, require_tls=True,local_storage=False):
    if len(infrastructure_token) < 32:
        raise ValueError('Strong dedicated infrastructure token required')
    sessions = SessionAuth(owner)
    queues = WorkQueues(owner,stale_seconds,release_limit,restart_grace=stale_seconds)
    checkpoints=Checkpoints(owner,queues)
    blobs=checkpoints.blobs
    generation_store=Generations(owner,blobs,queues)
    index_queries=IndexQueries(owner,blobs,queues)
    evaluations=Evaluations(owner,private_http=not require_tls,local_storage=local_storage)
    lifecycle=LifecycleRecords(owner)
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

    @app.post('/substrate/v1/evaluations',response_model=Receipt,status_code=202)
    def start_evaluation(payload: StartEvaluation,request: Request):
        return evaluations.start(actor(request),payload.model_dump(),idempotency(request))

    @app.get('/substrate/v1/evaluations/{evaluation_id}')
    def evaluation_metadata(evaluation_id: str,request: Request):
        principal=actor(request,evaluation_id)
        if principal.kind=='worker': raise Forbidden('control_identity_required')
        with owner.transaction() as db:
            row=require_evaluation(db,evaluation_id)
            return {'evaluation_id':evaluation_id,'state':row['state'],'version':row['version'],'config_revision':row['config_revision'],'goals_revision':row['goals_revision']}

    @app.post('/substrate/v1/evaluations/{evaluation_id}/control',response_model=Receipt)
    def control_evaluation(evaluation_id: str,payload: Control,request: Request):
        return evaluations.control(actor(request,evaluation_id),evaluation_id,payload.model_dump(),idempotency(request))

    @app.put('/substrate/v1/evaluations/{evaluation_id}/configuration',response_model=Receipt)
    def update_configuration(evaluation_id: str,payload: ConfigUpdate,request: Request):
        return evaluations.update(actor(request,evaluation_id),evaluation_id,payload.model_dump(),idempotency(request))

    @app.get('/substrate/v1/evaluations/{evaluation_id}/lifecycle')
    def lifecycle_snapshot(evaluation_id: str,request: Request):
        return lifecycle.snapshot(infrastructure(request),evaluation_id)

    @app.post('/substrate/v1/evaluations/{evaluation_id}/lifecycle/{command}')
    def lifecycle_command(evaluation_id: str,command: str,payload: dict,request: Request):
        return lifecycle.command(infrastructure(request),evaluation_id,command,payload,idempotency(request))

    @app.get('/substrate/v1/evaluations/{evaluation_id}/snapshot', operation_id='readSubstrateSnapshot')
    def read_snapshot(evaluation_id: str, request: Request):
        principal = actor(request, evaluation_id)
        # Full snapshots include other sessions and must not leak to reproduction workers.
        if principal.kind == 'worker':
            raise Forbidden('control_identity_required')
        return snapshot(owner, evaluation_id)

    @app.post('/substrate/v1/evaluations/{evaluation_id}/sessions', response_model=Receipt, operation_id='registerSession')
    def register(evaluation_id: str, payload: SessionRegistration, request: Request,purpose: Literal['role','validation-author','validation-reproduce']='role'):
        principal = infrastructure(request)
        def effect(db):
            require_evaluation(db, evaluation_id)
            existing = db.execute('SELECT * FROM sessions WHERE session_id=?', (payload.session_id,)).fetchone()
            if existing:
                raise Conflict('session_identity_conflict')
            if purpose!='role' and payload.role!='validator': raise Forbidden('invalid_session_purpose')
            db.execute('INSERT INTO sessions(session_id,evaluation_id,role,slot,incarnation,pod_name,state,heartbeat_at) VALUES(?,?,?,?,?,?,?,?)',
                       (payload.session_id,evaluation_id,payload.role,payload.slot,payload.incarnation,payload.pod_name,'registered',time.time()))
            db.execute('INSERT INTO runtime_records VALUES(?,?,?,?,0)',(evaluation_id,'session-purpose',payload.session_id,__import__('json').dumps({'purpose':purpose})))
            event(db, principal, evaluation_id, 'session.register', payload.session_id, version=0)
            return {'request_id': request.state.request_id, 'resource_id': payload.session_id, 'version': 0, 'state': 'registered'}
        return mutate(owner, principal.subject, 'POST', request.url.path, idempotency(request), dict(payload.model_dump(),purpose=purpose), effect)

    @app.post('/substrate/v1/evaluations/{evaluation_id}/credentials', response_model=Receipt)
    def provision(evaluation_id: str, payload: CredentialProvision, request: Request):
        principal=infrastructure(request)
        if hmac.compare_digest(payload.token.encode(),infrastructure_token.encode()):
            raise Forbidden('infrastructure_token_cannot_be_worker_credential')
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
        if principal.kind == 'worker' and principal.purpose == 'validation-reproduce':
            raise Forbidden('reproduction_access_denied')
        with owner.transaction() as db:
            require_evaluation(db, evaluation_id)
            items = [dict(r) for r in db.execute('SELECT generation_id,target_id,source_commit,state,parent_generation FROM index_generations WHERE evaluation_id=? AND state=\'ready\' ORDER BY generation_id', (evaluation_id,))]
            return {'items': items, 'next_cursor': None, 'snapshot_id': sequence(db)}

    @app.post('/substrate/v1/evaluations/{evaluation_id}/generations',response_model=Receipt,operation_id='commitGeneration')
    def commit_generation(evaluation_id: str,payload: GenerationWrite,request: Request):
        return generation_store.commit(actor(request,evaluation_id),evaluation_id,payload.model_dump(),idempotency(request))

    @app.post('/substrate/v1/evaluations/{evaluation_id}/index/query',response_model=Page,operation_id='queryIndex')
    def query_index(evaluation_id: str,payload: IndexQuery,request: Request):
        return index_queries.query(actor(request,evaluation_id),evaluation_id,payload.model_dump())

    @app.post('/substrate/v1/evaluations/{evaluation_id}/transcripts',response_model=Receipt)
    def append_transcript(evaluation_id: str,payload: TranscriptAppend,request: Request):
        principal=actor(request,evaluation_id)
        return transcript(owner,blobs,queues,principal,payload.kind,payload.content,idempotency(request),
                          secrets=(infrastructure_token,bearer(request,require_tls)))

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

    def checkpoint_namespace(segment):
        try:
            return decode_namespace(segment)
        except (ValueError,UnicodeError):
            raise DomainError('invalid_checkpoint_namespace') from None

    @app.get('/substrate/v1/evaluations/{evaluation_id}/checkpoints/{thread_id}/{namespace}', response_model=Page, operation_id='listCheckpoints')
    def list_checkpoints(evaluation_id: str,thread_id: str,namespace: str,request: Request,before: str | None=None,limit: int=100):
        return checkpoints.list(actor(request,evaluation_id),evaluation_id,thread_id,checkpoint_namespace(namespace),before,limit)

    @app.get('/substrate/v1/evaluations/{evaluation_id}/checkpoints/{thread_id}/{namespace}/{checkpoint_id}', response_model=Checkpoint, operation_id='getCheckpoint')
    def get_checkpoint(evaluation_id: str,thread_id: str,namespace: str,checkpoint_id: str,request: Request):
        return checkpoints.get(actor(request,evaluation_id),evaluation_id,thread_id,checkpoint_namespace(namespace),checkpoint_id)

    @app.put('/substrate/v1/evaluations/{evaluation_id}/checkpoints/{thread_id}/{namespace}/{checkpoint_id}', response_model=Receipt, operation_id='putCheckpoint')
    def put_checkpoint(evaluation_id: str,thread_id: str,namespace: str,checkpoint_id: str,payload: Checkpoint,request: Request):
        return checkpoints.put(actor(request,evaluation_id),evaluation_id,thread_id,checkpoint_namespace(namespace),checkpoint_id,payload.model_dump(),idempotency(request))

    @app.put('/substrate/v1/evaluations/{evaluation_id}/checkpoints/{thread_id}/{namespace}/{checkpoint_id}/writes', response_model=Receipt, operation_id='putCheckpointWrites')
    def checkpoint_writes(evaluation_id: str,thread_id: str,namespace: str,checkpoint_id: str,payload: CheckpointWrites,request: Request):
        return checkpoints.writes(actor(request,evaluation_id),evaluation_id,thread_id,checkpoint_namespace(namespace),checkpoint_id,payload.model_dump(),idempotency(request))

    @app.delete('/substrate/v1/evaluations/{evaluation_id}/checkpoints/{thread_id}/{namespace}', response_model=Receipt, operation_id='deleteCheckpointThread')
    def delete_checkpoint(evaluation_id: str,thread_id: str,namespace: str,request: Request,all_namespaces: bool=False):
        return checkpoints.delete(actor(request,evaluation_id),evaluation_id,thread_id,None if all_namespaces else checkpoint_namespace(namespace),idempotency(request))

    @app.put('/substrate/v1/evaluations/{evaluation_id}/blobs/{digest}',response_model=Receipt,operation_id='writeBlob')
    async def write_blob(evaluation_id: str,digest: str,request: Request):
        principal=await asyncio.to_thread(actor,request,evaluation_id)
        key=idempotency(request)
        with owner.transaction() as db:
            require_evaluation(db,evaluation_id)
            if principal.kind=='worker': queues.session(db,principal)
        chunks=[]; size=0
        async for chunk in request.stream():
            size+=len(chunk)
            if size>64*1024*1024: raise DomainError('artifact_too_large')
            chunks.append(chunk)
        try:
            await asyncio.to_thread(blobs.put,b''.join(chunks),digest)
        except ValueError:
            raise DomainError('artifact_digest_mismatch') from None
        def effect(db):
            if principal.kind=='worker': queues.session(db,principal)
            grantee=principal.session_id if principal.kind=='worker' else '*'
            db.execute('INSERT OR IGNORE INTO blob_grants VALUES(?,?,?,?)',(evaluation_id,digest,grantee,'artifact'))
            event(db,principal,evaluation_id,'artifact.commit',digest)
            return {'request_id':request.state.request_id,'resource_id':digest,'version':0}
        return await asyncio.to_thread(mutate,owner,principal.subject,'PUT',request.url.path,key,{'digest':digest,'size':size},effect)

    @app.get('/substrate/v1/evaluations/{evaluation_id}/blobs/{digest}',operation_id='readBlob')
    def read_blob(evaluation_id: str,digest: str,request: Request):
        principal=actor(request,evaluation_id)
        with owner.transaction() as db:
            require_evaluation(db,evaluation_id)
            rows=db.execute('SELECT grantee,purpose FROM blob_grants WHERE evaluation_id=? AND digest=?',(evaluation_id,digest)).fetchall()
            if not rows: raise Forbidden('artifact_scope_mismatch')
            if principal.kind=='worker':
                queues.session(db,principal)
                if not any(r['grantee']==principal.session_id or (r['grantee']=='*' and r['purpose']=='artifact' and principal.purpose!='validation-reproduce') for r in rows):
                    raise Forbidden('artifact_scope_mismatch')
            try:
                data=blobs.read_in_transaction(db,digest)
            except (ValueError,OSError):
                raise Unavailable('artifact_integrity_failed') from None
        return Response(data,media_type='application/octet-stream')

    @app.api_route('/{path:path}', methods=['GET','POST','PUT','PATCH','DELETE'])
    def unavailable(path: str, request: Request):
        actor(request)
        raise Unavailable('operation_not_ready', 'This operation is not available in the current implementation')

    return app
