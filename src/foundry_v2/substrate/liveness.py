"""Receipt-clock liveness shared by task, finding and file claims."""
import json
from foundry_v2.api.auth import Forbidden, Principal
from foundry_v2.contracts.models import Conflict, new_id
from foundry_v2.substrate.audit import event
from foundry_v2.substrate.transactions import canonical, mutate


class Liveness:
    def session(self, db, actor, allow_stale=False):
        if actor.kind != 'worker':
            raise Forbidden('worker_identity_required')
        row = db.execute('SELECT * FROM sessions WHERE session_id=?', (actor.session_id,)).fetchone()
        if not row or row['evaluation_id'] != actor.evaluation_id or row['role'] != actor.role:
            raise Forbidden('session_scope_mismatch')
        evaluation=db.execute('SELECT state FROM evaluations WHERE evaluation_id=?',(actor.evaluation_id,)).fetchone()
        if not evaluation or evaluation[0] in ('stopped','failed'):
            raise Conflict('evaluation_not_active')
        if row['state'] not in ('registered','running','draining'):
            raise Conflict('session_not_live')
        if not allow_stale and self.clock() > self.grace_until and (row['heartbeat_at'] is None or row['heartbeat_at'] < self.clock() - self.stale_seconds):
            raise Conflict('session_heartbeat_stale')
        return row

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
                resources=db.execute('SELECT resource_type,resource_id FROM claims WHERE resource_type<>\'task\' AND holder_session_id=?',(session['session_id'],)).fetchall()
                for resource in resources:
                    kind=f'queue:{resource["resource_type"]}:{session["role"]}'
                    row=db.execute('SELECT payload FROM runtime_records WHERE evaluation_id=? AND kind=? AND resource_id=?',(session['evaluation_id'],kind,resource['resource_id'])).fetchone()
                    if row:
                        record=json.loads(row[0]); record['release_count']+=1
                        if record['release_count']>=self.release_limit: record['state']='blocked'
                        db.execute('UPDATE runtime_records SET payload=?,version=version+1 WHERE evaluation_id=? AND kind=? AND resource_id=?',(canonical(record),session['evaluation_id'],kind,resource['resource_id']))
                tasks=db.execute('SELECT resource_id FROM claims WHERE resource_type=\'task\' AND holder_session_id=?',(session['session_id'],)).fetchall()
                for task in tasks:
                    db.execute('UPDATE tasks SET release_count=release_count+1,state=CASE WHEN release_count+1>=? THEN \'blocked\' ELSE state END,version=version+1 WHERE task_id=?',(self.release_limit,task[0]))
                db.execute('UPDATE claims SET holder_session_id=NULL,generation=generation+1 WHERE holder_session_id=?',(session['session_id'],))
                db.execute('UPDATE credentials SET revoked_at=? WHERE session_id=? AND revoked_at IS NULL',(self.clock(),session['session_id']))
                db.execute('UPDATE sessions SET state=\'dead\',version=version+1 WHERE session_id=?',(session['session_id'],))
                event(db,infrastructure,session['evaluation_id'],'session.dead',session['session_id'],session['version'],session['version']+1)
            return len(stale)

