"""Serialized deterministic controller lane with no verdict/publication authority."""
import json
import time
from uuid import uuid5,NAMESPACE_URL

from foundry_v2.api.auth import Forbidden
from foundry_v2.contracts.models import Conflict,DomainError,new_id
from foundry_v2.roles.registry import Role
from foundry_v2.substrate.audit import event
from foundry_v2.substrate.snapshots import require_evaluation
from foundry_v2.substrate.transactions import canonical,mutate
from foundry_v2.substrate.evaluations import current_configuration


class LifecycleRecords:
    def __init__(self,owner): self.owner=owner

    def infrastructure(self,actor):
        if actor.kind!='infrastructure': raise Forbidden('infrastructure_authority_required')

    def snapshot(self,actor,evaluation):
        self.infrastructure(actor)
        with self.owner.transaction() as db:
            row=require_evaluation(db,evaluation)
            config=current_configuration(db,evaluation)
            sessions=[dict(s) for s in db.execute('SELECT * FROM sessions WHERE evaluation_id=?',(evaluation,))]
            for session in sessions:
                end=db.execute('SELECT MAX(created_at) FROM audit_events WHERE evaluation_id=? AND resource=? AND action=\'session.dead\'',(evaluation,session['session_id'])).fetchone()[0]
                if end: session['ended_at']=end
                drain_session=db.execute('SELECT payload FROM runtime_records WHERE evaluation_id=? AND kind=\'drain-session\' AND resource_id=?',(evaluation,session['session_id'])).fetchone()
                if drain_session: session['drain_deadline']=json.loads(drain_session[0])['deadline']
            targets=[dict(t) for t in db.execute('SELECT et.*,t.vcs_url,t.scope_json FROM evaluation_targets et JOIN targets t USING(target_id) WHERE evaluation_id=?',(evaluation,))]
            for target in targets:
                revision=db.execute('SELECT version FROM runtime_records WHERE evaluation_id=? AND kind=\'index-version\' AND resource_id=?',(evaluation,target['target_id'])).fetchone()
                target['index_version']=revision[0] if revision else 0
            queryable=bool(targets) and all(t['index_generation'] and db.execute('SELECT 1 FROM index_generations g JOIN code_units u USING(generation_id) WHERE g.generation_id=? AND g.source_commit=? AND g.state=\'ready\' LIMIT 1',
                                                                               (t['index_generation'],t['source_commit'])).fetchone() for t in targets)
            drain=db.execute('SELECT payload FROM runtime_records WHERE evaluation_id=? AND kind=\'drain\' AND resource_id=\'evaluation\'',(evaluation,)).fetchone()
            restart=db.execute('SELECT 1 FROM runtime_records WHERE evaluation_id=? AND kind=\'restart-request\'',(evaluation,)).fetchone()
            return {'evaluation_id':evaluation,'state':row['state'],'version':row['version'],'configuration':config,
                    'sessions':sessions,'targets':targets,'index_queryable':queryable,'drain_deadline':json.loads(drain[0])['deadline'] if drain else None,'restart_requested':bool(restart)}

    def command(self,actor,evaluation,kind,payload,key):
        self.infrastructure(actor)
        def effect(db):
            row=require_evaluation(db,evaluation)
            if kind=='reserve':
                if set(payload)!={'role','slot','incarnation','restart_count'}: raise DomainError('invalid_session_reservation')
                role=Role(payload['role']).value
                if any(type(payload[k]) is not int or payload[k]<0 for k in ('slot','incarnation','restart_count')): raise DomainError('invalid_session_reservation')
                if row['state'] not in ('indexing','running'): raise Conflict('evaluation_not_running')
                existing=db.execute('SELECT 1 FROM sessions WHERE evaluation_id=? AND role=? AND slot=? AND state IN (\'registered\',\'running\',\'draining\')',(evaluation,role,payload['slot'])).fetchone()
                if existing: raise Conflict('role_slot_occupied')
                identity=new_id(); pod='foundry-'+role+'-'+identity[:12]
                db.execute('INSERT INTO sessions(session_id,evaluation_id,role,slot,incarnation,pod_name,state,heartbeat_at,restart_count) VALUES(?,?,?,?,?,?,?,?,?)',
                           (identity,evaluation,role,payload['slot'],payload['incarnation'],pod,'registered',time.time(),payload['restart_count']))
                event(db,actor,evaluation,'session.register',identity)
                return dict(payload,session_id=identity,evaluation_id=evaluation,pod_name=pod,state='registered')
            if kind=='state':
                transitions={'preflight':{'indexing','failed'},'indexing':{'running','draining','failed'},'running':{'draining','failed'},'draining':{'stopped','failed'}}
                state=payload.get('state')
                if state not in transitions.get(row['state'],set()): raise Conflict('invalid_lifecycle_transition')
                if state=='indexing':
                    probe=db.execute('SELECT payload FROM runtime_records WHERE evaluation_id=? AND kind=\'preflight\' AND resource_id=\'evaluation\'',(evaluation,)).fetchone()
                    if not probe or json.loads(probe[0]).get('passed') is not True: raise Conflict('preflight_not_passed')
                if state=='running':
                    targets=db.execute('SELECT index_generation FROM evaluation_targets WHERE evaluation_id=?',(evaluation,)).fetchall()
                    if not targets or any(not t[0] or not db.execute('SELECT 1 FROM code_units u JOIN index_generations g USING(generation_id) JOIN evaluation_targets et ON et.evaluation_id=g.evaluation_id AND et.target_id=g.target_id WHERE g.generation_id=? AND et.source_commit=g.source_commit AND g.state=\'ready\' LIMIT 1',(t[0],)).fetchone() for t in targets): raise Conflict('index_not_queryable')
                db.execute('UPDATE evaluations SET state=?,version=version+1 WHERE evaluation_id=?',(state,evaluation))
                if state in ('stopped','failed'):
                    db.execute('UPDATE installations SET active_evaluation_id=NULL,version=version+1 WHERE active_evaluation_id=?',(evaluation,))
                event(db,actor,evaluation,'lifecycle.state',evaluation,row['version'],row['version']+1,state)
            elif kind=='drain':
                session=payload.get('session_id')
                cursor=db.execute('UPDATE sessions SET state=\'draining\',version=version+1 WHERE session_id=? AND evaluation_id=? AND state IN (\'registered\',\'running\')',(session,evaluation))
                if not cursor.rowcount: return {'resource_id':session,'version':0,'state':'already-drained'}
                config=current_configuration(db,evaluation)
                db.execute('INSERT INTO runtime_records VALUES(?,?,?, ?,0) ON CONFLICT(evaluation_id,kind,resource_id) DO NOTHING',
                           (evaluation,'drain-session',session,canonical({'deadline':time.time()+config['fleet']['drain_seconds']})))
                event(db,actor,evaluation,'session.wrap-up',session)
            elif kind=='preflight':
                required={'identity','storage','admission','policy','source','github','rules','ollama'}
                config=current_configuration(db,evaluation)
                if config.get('testbed') is not None: required.add('testbed')
                if type(payload.get('passed')) is not bool or set(payload.get('checks',{}))!=required or payload['passed']!=all(r.get('passed') is True for r in payload['checks'].values()):
                    raise DomainError('complete_preflight_report_required')
                db.execute('INSERT INTO runtime_records VALUES(?,?,?, ?,0) ON CONFLICT(evaluation_id,kind,resource_id) DO UPDATE SET payload=excluded.payload,version=runtime_records.version+1',
                           (evaluation,'preflight','evaluation',canonical(payload)))
            elif kind=='degraded':
                reason=payload.get('reason')
                if reason not in ('lifecycle_dependency_unavailable','provider_unavailable','policy_unavailable'): raise DomainError('invalid_degradation_reason')
                db.execute('UPDATE evaluations SET degraded_json=? WHERE evaluation_id=?',(canonical([reason]),evaluation))
            elif kind=='restart':
                if db.execute('SELECT 1 FROM sessions WHERE evaluation_id=? AND state IN (\'registered\',\'running\',\'draining\')',(evaluation,)).fetchone():
                    raise Conflict('sessions_not_drained')
                config=current_configuration(db,evaluation)
                retained=[]
                for target in config['target']:
                    repository=target['repository'].removesuffix('.git').rstrip('/')
                    identity=str(uuid5(NAMESPACE_URL,repository.lower())); retained.append(identity)
                    scope=canonical({'include':target['include'],'exclude':target['exclude']})
                    db.execute('INSERT INTO targets(target_id,vcs_url,repository_identity,pinned_commit,scope_json) VALUES(?,?,?,?,?) ON CONFLICT(target_id) DO UPDATE SET pinned_commit=excluded.pinned_commit,scope_json=excluded.scope_json,version=targets.version+1',
                               (identity,repository,repository.lower(),target['revision'],scope))
                    db.execute('INSERT INTO evaluation_targets(evaluation_id,target_id,source_commit) VALUES(?,?,?) ON CONFLICT(evaluation_id,target_id) DO UPDATE SET source_commit=excluded.source_commit,index_generation=NULL',
                               (evaluation,identity,target['revision']))
                for target in db.execute('SELECT target_id FROM evaluation_targets WHERE evaluation_id=?',(evaluation,)).fetchall():
                    if target[0] not in retained: db.execute('DELETE FROM evaluation_targets WHERE evaluation_id=? AND target_id=?',(evaluation,target[0]))
                db.execute('DELETE FROM runtime_records WHERE evaluation_id=? AND kind=\'restart-request\'',(evaluation,))
                db.execute('UPDATE evaluations SET state=\'preflight\',coverage_complete=0,version=version+1 WHERE evaluation_id=?',(evaluation,))
                event(db,actor,evaluation,'configuration.restart',evaluation,row['version'],row['version']+1)
            else: raise DomainError('invalid_lifecycle_command')
            return {'request_id':new_id(),'resource_id':evaluation,'version':row['version']+1}
        return mutate(self.owner,actor.subject,'POST',f'{evaluation}/lifecycle/{kind}',key,payload,effect)
