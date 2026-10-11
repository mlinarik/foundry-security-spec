"""Stable work IDs, atomic claims and receipt-clock liveness."""
import time
import json

from foundry_v2.api.auth import Forbidden, Principal
from foundry_v2.contracts.models import Conflict, DomainError, new_id
from foundry_v2.substrate.audit import event
from foundry_v2.substrate.liveness import Liveness
from foundry_v2.substrate.snapshots import Missing, require_evaluation, sequence
from foundry_v2.substrate.transactions import assert_version, canonical, decode_cursor, encode_cursor, mutate


class WorkQueues(Liveness):
    def __init__(self, owner, stale_seconds, release_limit, clock=time.time, restart_grace=0):
        if stale_seconds <= 0 or release_limit <= 0 or restart_grace < 0:
            raise ValueError('Positive liveness bounds and release limit required')
        self.owner, self.clock = owner, clock
        self.stale_seconds, self.release_limit = stale_seconds, release_limit
        self.grace_until = clock() + restart_grace

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
            return self.claim_resource(actor,kind,queue,key)
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
        with self.owner.transaction() as db:
            resource=db.execute('SELECT resource_type FROM claims WHERE resource_id=? AND evaluation_id=? AND holder_session_id=?',
                                (identity,actor.evaluation_id,actor.session_id)).fetchone()
        if resource and resource[0]!='task':
            return self.write_resource(actor,resource[0],identity,generation,version,operation,payload,key)
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

    def enqueue_resource(self,db,evaluation,kind,identity,role,queue,payload,priority=0):
        if kind not in ('finding','file'):
            raise DomainError('invalid_resource_type')
        record={'state':'open','release_count':0,'role':role,'queue':queue,'priority':priority,'work':payload}
        db.execute('INSERT OR IGNORE INTO runtime_records(evaluation_id,kind,resource_id,payload) VALUES(?,?,?,?)',
                   (evaluation,f'queue:{kind}:{role}',identity,canonical(record)))

    def claim_resource(self,actor,kind,queue,key):
        if kind not in ('finding','file'): raise DomainError('invalid_resource_type')
        def effect(db):
            self.session(db,actor)
            row=db.execute('SELECT r.* FROM runtime_records r LEFT JOIN claims c ON c.resource_type=? AND c.resource_id=r.resource_id WHERE r.evaluation_id=? AND r.kind=? AND json_extract(r.payload,\'$.state\')=\'open\' AND json_extract(r.payload,\'$.queue\')=? AND c.holder_session_id IS NULL ORDER BY json_extract(r.payload,\'$.priority\'),r.resource_id LIMIT 1',
                           (kind,actor.evaluation_id,f'queue:{kind}:{actor.role}',queue)).fetchone()
            if row is None: raise Conflict('no_eligible_work')
            identity=row['resource_id']
            db.execute('INSERT INTO claims(resource_type,resource_id,evaluation_id,holder_session_id,generation,acquired_at) VALUES(?,?,?,?,1,?) ON CONFLICT(resource_type,resource_id) DO UPDATE SET evaluation_id=excluded.evaluation_id,holder_session_id=excluded.holder_session_id,generation=claims.generation+1,acquired_at=excluded.acquired_at',
                       (kind,identity,actor.evaluation_id,actor.session_id,self.clock()))
            generation=db.execute('SELECT generation FROM claims WHERE resource_type=? AND resource_id=?',(kind,identity)).fetchone()[0]
            payload=json.loads(row['payload']); payload['version']=row['version']
            event(db,actor,actor.evaluation_id,'claim.acquire',identity,version=generation)
            return {'resource_id':identity,'resource_type':kind,'session_id':actor.session_id,'generation':generation,'owner_epoch':self.owner.epoch,'payload':payload}
        result=mutate(self.owner,actor.subject,'POST',f'{actor.evaluation_id}/claims/{kind}/{queue}',key,{'kind':kind,'queue':queue},effect)
        with self.owner.transaction() as db:
            self.session(db,actor)
            row=db.execute('SELECT * FROM claims WHERE resource_type=? AND resource_id=?',(kind,result['resource_id'])).fetchone()
            if row['holder_session_id']!=actor.session_id or row['generation']!=result['generation']: raise Conflict('claim_receipt_stale')
        return result

    def write_resource(self,actor,kind,identity,generation,version,operation,payload,key):
        def effect(db):
            self.session(db,actor)
            claim=db.execute('SELECT * FROM claims WHERE resource_type=? AND resource_id=?',(kind,identity)).fetchone()
            if not claim or claim['evaluation_id']!=actor.evaluation_id or claim['holder_session_id']!=actor.session_id or claim['generation']!=generation:
                raise Conflict('claim_fenced')
            record_kind=f'queue:{kind}:{actor.role}'
            row=db.execute('SELECT * FROM runtime_records WHERE evaluation_id=? AND kind=? AND resource_id=?',(actor.evaluation_id,record_kind,identity)).fetchone()
            if row is None: raise Missing('work_resource_not_found')
            assert_version(row['version'],version)
            record=json.loads(row['payload'])
            if operation=='update':
                if set(payload)!={'description'} or not isinstance(payload['description'],str): raise DomainError('invalid_claim_update')
                record['work']['description']=payload['description']
            else:
                if payload: raise DomainError('invalid_claim_payload')
                if operation=='release': record['release_count']+=1
                record['state']='closed' if operation=='complete' else 'blocked' if record['release_count']>=self.release_limit else 'open'
                db.execute('UPDATE claims SET holder_session_id=NULL,generation=generation+1 WHERE resource_type=? AND resource_id=?',(kind,identity))
            db.execute('UPDATE runtime_records SET payload=?,version=version+1 WHERE evaluation_id=? AND kind=? AND resource_id=?',
                       (canonical(record),actor.evaluation_id,record_kind,identity))
            event(db,actor,actor.evaluation_id,'claim.'+operation,identity,version,version+1)
            return {'request_id':new_id(),'resource_id':identity,'version':version+1,'state':record['state']}
        return mutate(self.owner,actor.subject,'PATCH',f'{actor.evaluation_id}/claims/{kind}/{identity}',key,
                      {'generation':generation,'version':version,'operation':operation,'payload':payload},effect)

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
