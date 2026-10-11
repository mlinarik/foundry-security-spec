"""Authenticated installation reservation and versioned operator configuration."""
import json
import time
from uuid import uuid5,NAMESPACE_URL

from foundry_v2.api.auth import Forbidden
from foundry_v2.config import ConfigurationError,validate
from foundry_v2.contracts.models import Conflict,DomainError,new_id
from foundry_v2.substrate.audit import event
from foundry_v2.substrate.snapshots import require_evaluation
from foundry_v2.substrate.transactions import assert_version,canonical,mutate


def current_configuration(db,evaluation):
    pointer=db.execute('SELECT payload FROM runtime_records WHERE evaluation_id=? AND kind=\'config-current\' AND resource_id=\'evaluation\'',(evaluation,)).fetchone()
    if pointer:
        identity=json.loads(pointer[0])['revision_id']
        row=db.execute('SELECT validated_json FROM config_revisions WHERE evaluation_id=? AND revision_id=?',(evaluation,identity)).fetchone()
    else:
        row=db.execute('SELECT validated_json FROM config_revisions WHERE evaluation_id=? ORDER BY created_at DESC,revision_id DESC LIMIT 1',(evaluation,)).fetchone()
    if row is None: raise Conflict('evaluation_configuration_missing')
    return json.loads(row[0])


def publish_configuration(db,evaluation,configuration,subject,revision):
    identity=new_id()
    db.execute('INSERT INTO config_revisions VALUES(?,?,?,?,?)',(identity,evaluation,canonical(configuration),subject,time.time()))
    db.execute('INSERT INTO runtime_records VALUES(?,?,?, ?,?) ON CONFLICT(evaluation_id,kind,resource_id) DO UPDATE SET payload=excluded.payload,version=excluded.version',
               (evaluation,'config-current','evaluation',canonical({'revision_id':identity}),revision))


class Evaluations:
    def __init__(self,owner,private_http=False,local_storage=False):
        self.owner=owner; self.private_http=private_http; self.local_storage=local_storage

    def configuration(self,value):
        try: return validate(value,private_http=self.private_http,local_storage=self.local_storage)
        except ConfigurationError as error: raise DomainError('invalid_configuration',str(error)) from None

    def start(self,actor,payload,key):
        if actor.kind!='operator': raise Forbidden('operator_authority_required')
        config=self.configuration(payload['configuration'])
        def effect(db):
            installation=db.execute('SELECT * FROM installations').fetchone()
            assert_version(installation['version'],payload['expected_installation_version'])
            if installation['active_evaluation_id']: raise Conflict('active_evaluation')
            identity=new_id()
            db.execute('INSERT INTO evaluations(evaluation_id,installation_id,state,config_revision,started_at) VALUES(?,?,?,?,?)',
                       (identity,self.owner.installation_id,'preflight',1,time.time()))
            db.execute('UPDATE installations SET active_evaluation_id=?,version=version+1',(identity,))
            publish_configuration(db,identity,config,actor.subject,1)
            for target in config['target']:
                repository=target['repository'].removesuffix('.git').rstrip('/')
                target_id=str(uuid5(NAMESPACE_URL,repository.lower()))
                scope=canonical({'include':target['include'],'exclude':target['exclude']})
                db.execute('INSERT INTO targets(target_id,vcs_url,repository_identity,pinned_commit,scope_json) VALUES(?,?,?,?,?) ON CONFLICT(target_id) DO UPDATE SET pinned_commit=excluded.pinned_commit,scope_json=excluded.scope_json,version=targets.version+1',
                           (target_id,repository,repository.lower(),target['revision'],scope))
                db.execute('INSERT INTO evaluation_targets(evaluation_id,target_id,source_commit) VALUES(?,?,?)',(identity,target_id,target['revision']))
            event(db,actor,identity,'evaluation.start',identity,version=0)
            return {'request_id':new_id(),'resource_id':identity,'version':0,'state':'preflight'}
        return mutate(self.owner,actor.subject,'POST','/evaluations',key,payload,effect,status=202)

    def control(self,actor,evaluation,payload,key):
        if actor.kind!='operator': raise Forbidden('operator_authority_required')
        def effect(db):
            row=require_evaluation(db,evaluation); assert_version(row['version'],payload['expected_version'])
            action=payload['action']
            if action=='resume':
                if row['state'] not in ('stopped','failed'): raise Conflict('evaluation_not_stopped')
                installation=db.execute('SELECT active_evaluation_id FROM installations').fetchone()
                if installation[0] and installation[0]!=evaluation: raise Conflict('active_evaluation')
                halt=db.execute('SELECT payload FROM runtime_records WHERE evaluation_id=? AND kind=\'budget-halt\' AND resource_id=\'installation\'',(evaluation,)).fetchone()
                if halt and json.loads(halt[0]).get('requires_cap_raise'): raise Conflict('cap_raise_required')
                state='preflight'; db.execute('UPDATE installations SET active_evaluation_id=?,version=version+1',(evaluation,))
            elif action=='stop':
                state='stopped'; db.execute('UPDATE installations SET active_evaluation_id=NULL,version=version+1 WHERE active_evaluation_id=?',(evaluation,))
                db.execute('UPDATE credentials SET revoked_at=? WHERE evaluation_id=? AND revoked_at IS NULL',(time.time(),evaluation))
            else:
                if row['state'] in ('stopped','failed'): raise Conflict('evaluation_not_active')
                state='draining'
            db.execute('UPDATE evaluations SET state=?,stop_reason=?,stopped_at=?,version=version+1 WHERE evaluation_id=?',
                       (state,payload['reason'],time.time() if state=='stopped' else None,evaluation))
            event(db,actor,evaluation,'evaluation.'+action,evaluation,row['version'],row['version']+1,payload['reason'])
            return {'request_id':new_id(),'resource_id':evaluation,'version':row['version']+1,'state':state}
        return mutate(self.owner,actor.subject,'POST',f'{evaluation}/control',key,payload,effect)

    def update(self,actor,evaluation,payload,key):
        if actor.kind!='operator': raise Forbidden('operator_authority_required')
        config=self.configuration(payload['configuration'])
        def effect(db):
            row=require_evaluation(db,evaluation); assert_version(row['version'],payload['expected_version'])
            previous=current_configuration(db,evaluation)
            restart=any(previous[field]!=config[field] for field in ('target','sandbox','integrations'))
            publish_configuration(db,evaluation,config,actor.subject,row['config_revision']+1)
            db.execute('UPDATE evaluations SET config_revision=config_revision+1,version=version+1,coverage_complete=CASE WHEN ? THEN 0 ELSE coverage_complete END,goals_revision=goals_revision+? WHERE evaluation_id=?',
                       (previous['goals']!=config['goals'],int(previous['goals']!=config['goals']),evaluation))
            if restart:
                db.execute('INSERT INTO runtime_records VALUES(?,?,?, ?,0) ON CONFLICT(evaluation_id,kind,resource_id) DO UPDATE SET payload=excluded.payload,version=runtime_records.version+1',
                           (evaluation,'restart-request','configuration',canonical({'reason':'controlled_config_restart','config_revision':row['config_revision']+1})))
            event(db,actor,evaluation,'configuration.update',evaluation,row['version'],row['version']+1)
            return {'request_id':new_id(),'resource_id':evaluation,'version':row['version']+1,'state':'restart-required' if restart else row['state']}
        return mutate(self.owner,actor.subject,'PUT',f'{evaluation}/configuration',key,payload,effect)
