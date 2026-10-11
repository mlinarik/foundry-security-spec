"""Stable work IDs, atomic claims and receipt-clock liveness."""
import time

from foundry_v2.api.auth import Forbidden, Principal
from foundry_v2.contracts.models import Conflict, DomainError, new_id
from foundry_v2.substrate.audit import event
from foundry_v2.substrate.snapshots import Missing, require_evaluation, sequence
from foundry_v2.substrate.transactions import assert_version, decode_cursor, encode_cursor, mutate


class WorkQueues:
    def __init__(self, owner, stale_seconds, release_limit, clock=time.time, restart_grace=0):
        if stale_seconds <= 0 or release_limit <= 0 or restart_grace < 0:
            raise ValueError('Positive liveness bounds and release limit required')
        self.owner, self.clock = owner, clock
        self.stale_seconds, self.release_limit = stale_seconds, release_limit
        self.grace_until = clock() + restart_grace

    def session(self, db, actor, allow_stale=False):
        if actor.kind != 'worker':
            raise Forbidden('worker_identity_required')
        row = db.execute('SELECT * FROM sessions WHERE session_id=?', (actor.session_id,)).fetchone()
        if not row or row['evaluation_id'] != actor.evaluation_id or row['role'] != actor.role:
            raise Forbidden('session_scope_mismatch')
        if row['state'] not in ('registered','running','draining'):
            raise Conflict('session_not_live')
        if not allow_stale and self.clock() > self.grace_until and (row['heartbeat_at'] is None or row['heartbeat_at'] < self.clock() - self.stale_seconds):
            raise Conflict('session_heartbeat_stale')
        return row

    def add(self, actor, evaluation, payload, key, queue='work'):
        if actor.kind not in ('operator','worker') or (actor.kind == 'worker' and actor.evaluation_id != evaluation):
            raise Forbidden('task_authority_required')
        def effect(db):
            require_evaluation(db,evaluation)
            if actor.kind == 'worker':
                self.session(db,actor)
            target = payload.get('target_id')
            if target and not db.execute('SELECT 1 FROM evaluation_targets WHERE evaluation_id=? AND target_id=?', (evaluation,target)).fetchone():
                raise Forbidden('target_scope_mismatch')
            identity=new_id()
            db.execute('INSERT INTO tasks(task_id,evaluation_id,target_id,queue_name,role,title,description,priority) VALUES(?,?,?,?,?,?,?,?)',
                       (identity,evaluation,target,queue,payload['role'],payload['title'],payload['description'],payload['priority']))
            event(db,actor,evaluation,'task.add',identity,version=0)
            return {'request_id':new_id(),'resource_id':identity,'version':0,'state':'open'}
        return mutate(self.owner,actor.subject,'POST',f'{evaluation}/tasks/{queue}',key,payload,effect)

    def edit(self,actor,evaluation,identity,payload,key):
        if actor.kind != 'operator' and not (actor.kind == 'worker' and actor.role == 'coverage-guide' and actor.evaluation_id == evaluation):
            raise Forbidden('task_edit_authority_required')
        def effect(db):
            if actor.kind == 'worker':
                self.session(db,actor)
                if payload.get('state') == 'closed':
                    raise Forbidden('coverage_guide_cannot_close_tasks')
            row=db.execute('SELECT * FROM tasks WHERE task_id=? AND evaluation_id=?',(identity,evaluation)).fetchone()
            if row is None:
                raise Missing('task_not_found')
            assert_version(row['version'],payload['expected_version'])
            if payload.get('state') and db.execute('SELECT 1 FROM claims WHERE resource_type=\'task\' AND resource_id=? AND holder_session_id IS NOT NULL',(identity,)).fetchone():
                raise Conflict('task_is_claimed')
            db.execute('UPDATE tasks SET state=?,description=?,priority=?,version=version+1 WHERE task_id=?',
                       (payload.get('state',row['state']),payload.get('description',row['description']),payload.get('priority',row['priority']),identity))
            event(db,actor,evaluation,'task.edit',identity,row['version'],row['version']+1)
            return {'request_id':new_id(),'resource_id':identity,'version':row['version']+1}
        return mutate(self.owner,actor.subject,'PATCH',f'{evaluation}/tasks/{identity}',key,payload,effect)

    def claim(self,actor,kind,queue,key):
        if kind != 'task':
            raise DomainError('claim_type_not_ready','Finding and file claims await their domain implementation')
        def effect(db):
            self.session(db,actor)
            existing=db.execute('SELECT * FROM claims WHERE evaluation_id=? AND resource_type=? AND holder_session_id=?',(actor.evaluation_id,kind,actor.session_id)).fetchone()
            if existing:
                raise Conflict('session_already_holds_claim')
            row=db.execute('SELECT t.* FROM tasks t LEFT JOIN claims c ON c.resource_type=\'task\' AND c.resource_id=t.task_id WHERE t.evaluation_id=? AND t.role=? AND t.queue_name=? AND t.state=\'open\' AND c.holder_session_id IS NULL ORDER BY t.priority,t.task_id LIMIT 1',
                           (actor.evaluation_id,actor.role,queue)).fetchone()
            if row is None:
                raise Conflict('no_eligible_work')
            identity=row['task_id']
            db.execute('INSERT INTO claims(resource_type,resource_id,evaluation_id,holder_session_id,generation,acquired_at) VALUES(?,?,?,?,1,?) ON CONFLICT(resource_type,resource_id) DO UPDATE SET holder_session_id=excluded.holder_session_id,generation=claims.generation+1,acquired_at=excluded.acquired_at',
                       (kind,identity,actor.evaluation_id,actor.session_id,self.clock()))
            generation=db.execute('SELECT generation FROM claims WHERE resource_type=? AND resource_id=?',(kind,identity)).fetchone()[0]
            event(db,actor,actor.evaluation_id,'claim.acquire',identity,version=generation)
            return {'resource_id':identity,'resource_type':kind,'session_id':actor.session_id,'generation':generation,'owner_epoch':self.owner.epoch,'payload':dict(row)}
        result=mutate(self.owner,actor.subject,'POST',f'{actor.evaluation_id}/claims/{kind}/{queue}',key,{'kind':kind,'queue':queue},effect)
        # A retried receipt must not revive a dead/reassigned claim.
        with self.owner.transaction() as db:
            self.session(db,actor)
            row=db.execute('SELECT * FROM claims WHERE resource_type=? AND resource_id=?',(kind,result['resource_id'])).fetchone()
            if row['holder_session_id'] != actor.session_id or row['generation'] != result['generation']:
                raise Conflict('claim_receipt_stale')
        return result

    def write(self,actor,identity,generation,version,operation,payload,key):
        if operation not in ('complete','release','update'):
            raise DomainError('invalid_claim_operation')
        def effect(db):
            self.session(db,actor)
            claim=db.execute('SELECT * FROM claims WHERE resource_type=\'task\' AND resource_id=?',(identity,)).fetchone()
            if not claim or claim['evaluation_id'] != actor.evaluation_id or claim['holder_session_id'] != actor.session_id or claim['generation'] != generation:
                raise Conflict('claim_fenced')
            row=db.execute('SELECT * FROM tasks WHERE task_id=?',(identity,)).fetchone()
            assert_version(row['version'],version)
            if actor.role=='coverage-guide' and operation=='complete':
                raise Forbidden('coverage_guide_cannot_close_tasks')
            if operation=='update':
                if set(payload) != {'description'} or not isinstance(payload['description'],str) or not payload['description']:
                    raise DomainError('invalid_claim_update')
                state,releases='open',row['release_count']
            else:
                if payload:
                    raise DomainError('invalid_claim_payload')
                releases=row['release_count']+(operation=='release')
                state='closed' if operation=='complete' else 'blocked' if releases>=self.release_limit else 'open'
                db.execute('UPDATE claims SET holder_session_id=NULL,generation=generation+1 WHERE resource_type=\'task\' AND resource_id=?',(identity,))
            db.execute('UPDATE tasks SET state=?,release_count=?,description=?,version=version+1 WHERE task_id=?',
                       (state,releases,payload.get('description',row['description']),identity))
            event(db,actor,actor.evaluation_id,'claim.'+operation,identity,version,version+1)
            return {'request_id':new_id(),'resource_id':identity,'version':version+1,'state':state}
        return mutate(self.owner,actor.subject,'PATCH',f'{actor.evaluation_id}/claims/{identity}',key,
                      {'generation':generation,'version':version,'operation':operation,'payload':payload},effect)

    def heartbeat(self,actor,incarnation,key,last_event_sequence=0):
        def effect(db):
            session=self.session(db,actor,allow_stale=True)
            if session['incarnation'] != incarnation:
                raise Conflict('incarnation_fenced')
            db.execute('UPDATE sessions SET heartbeat_at=?,state=CASE WHEN state=\'registered\' THEN \'running\' ELSE state END WHERE session_id=?',(self.clock(),actor.session_id))
            return {'request_id':new_id(),'resource_id':actor.session_id,'version':session['version']}
        return mutate(self.owner,actor.subject,'POST',f'{actor.evaluation_id}/heartbeat',key,
                      {'incarnation':incarnation,'last_event_sequence':last_event_sequence},effect)

    def reap(self):
        if self.clock()<self.grace_until:
            return 0
        with self.owner.transaction() as db:
            stale=db.execute('SELECT * FROM sessions WHERE state IN (\'registered\',\'running\',\'draining\') AND (heartbeat_at IS NULL OR heartbeat_at<?)',(self.clock()-self.stale_seconds,)).fetchall()
            infrastructure=Principal('heartbeat-reaper','infrastructure')
            for session in stale:
                tasks=db.execute('SELECT resource_id FROM claims WHERE resource_type=\'task\' AND holder_session_id=?',(session['session_id'],)).fetchall()
                for task in tasks:
                    db.execute('UPDATE tasks SET release_count=release_count+1,state=CASE WHEN release_count+1>=? THEN \'blocked\' ELSE state END,version=version+1 WHERE task_id=?',(self.release_limit,task[0]))
                db.execute('UPDATE claims SET holder_session_id=NULL,generation=generation+1 WHERE holder_session_id=?',(session['session_id'],))
                db.execute('UPDATE credentials SET revoked_at=? WHERE session_id=? AND revoked_at IS NULL',(self.clock(),session['session_id']))
                db.execute('UPDATE sessions SET state=\'dead\',version=version+1 WHERE session_id=?',(session['session_id'],))
                event(db,infrastructure,session['evaluation_id'],'session.dead',session['session_id'],session['version'],session['version']+1)
            return len(stale)

    def list(self,actor,evaluation,cursor=None,limit=100):
        if not 1<=limit<=100:
            raise DomainError('invalid_page_size')
        if actor.kind not in ('operator','worker') or (actor.kind=='worker' and actor.evaluation_id!=evaluation):
            raise Forbidden('task_read_authority_required')
        try:
            after=decode_cursor(cursor) if cursor else ''
        except ValueError:
            raise DomainError('invalid_cursor') from None
        with self.owner.transaction() as db:
            require_evaluation(db,evaluation)
            if actor.kind=='worker':
                self.session(db,actor)
                rows=db.execute('SELECT * FROM tasks WHERE evaluation_id=? AND role=? AND task_id>? ORDER BY task_id LIMIT ?', (evaluation,actor.role,after,limit+1)).fetchall()
            else:
                rows=db.execute('SELECT * FROM tasks WHERE evaluation_id=? AND task_id>? ORDER BY task_id LIMIT ?', (evaluation,after,limit+1)).fetchall()
            return {'items':[dict(row) for row in rows[:limit]],'next_cursor':encode_cursor(rows[limit-1]['task_id']) if len(rows)>limit else None,'snapshot_id':sequence(db)}
