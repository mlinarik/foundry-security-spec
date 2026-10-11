import copy
import json
from pathlib import Path

import pytest
import asyncio

from foundry_v2.config import ConfigurationError,validate


def fixture_config():
    path=Path(__file__).resolve().parents[2]/'specs/001-foundry/contracts/example-config.json'
    value=json.loads(path.read_text())
    value['target'][0].update(repository='https://github.com/fixture/source',revision='a'*40)
    value['sandbox']['storage_class']='fixture-csi-block'
    value['sandbox']['external_allowlist'][0]['cidr']='10.50.0.10/32'
    value['integrations']['ollama']['base_url']='http://10.50.0.10:11434'
    value['integrations']['github']['report_repository']='fixture/reports'
    value['integrations']['operator_auth'].update(allowed_subjects=['fixture-operator'],ingress_host='foundry.fixture',tls_secret_ref='fixture-tls')
    return value


def test_configuration_rejects_every_missing_field_and_placeholders():
    with pytest.raises(ConfigurationError) as failure: validate({})
    assert 'configuration.target: required' in failure.value.errors
    assert 'configuration.integrations: required' in failure.value.errors
    value=fixture_config(); assert validate(value)==value
    value['target'][0]['revision']='0'*40
    value['fleet']['stale_seconds']=value['fleet']['heartbeat_seconds']
    value['integrations']['ollama']['base_url']='http://10.50.0.11:11434'
    with pytest.raises(ConfigurationError) as failure: validate(value)
    assert len(failure.value.errors)>=3


def test_configuration_private_http_local_storage_override_is_explicit():
    value=fixture_config(); value['sandbox']['storage_class']='local-storage'
    with pytest.raises(ConfigurationError): validate(value)
    assert validate(value,private_http=True,local_storage=True)==value


def test_lifecycle_starts_indexer_first_and_adopts_persisted_jobs():
    from foundry_v2.orchestrator.lifecycle import Lifecycle
    class Clock:
        def utc(self): return 100
        def monotonic(self): return 100
    class Store:
        def __init__(self): self.state_value='indexing'; self.sessions=[]; self.queryable=False
        async def snapshot(self,e): return {'configuration':fixture_config(),'state':self.state_value,'sessions':self.sessions,'index_queryable':self.queryable}
        async def reserve(self,e,role,slot,incarnation,restarts):
            session={'session_id':role+':'+str(slot),'role':role,'slot':slot,'incarnation':incarnation,'state':'registered','restart_count':restarts}
            self.sessions.append(session); return session
        async def state(self,e,state): self.state_value=state
        async def wrap_up(self,s): pass
    class Deployment:
        def __init__(self): self.jobs=[]; self.created=[]
        async def list_jobs(self,e): return self.jobs
        async def create_job(self,s): self.jobs.append(s); self.created.append(s['role'])
    async def scenario():
        store,deploy=Store(),Deployment(); lifecycle=Lifecycle(store,deploy,None,Clock())
        await lifecycle.reconcile('e'); assert deploy.created==['indexer']
        await lifecycle.reconcile('e'); assert deploy.created==['indexer']
        store.queryable=True; await lifecycle.reconcile('e')
        assert set(deploy.created)=={'orchestrator','indexer','cartographer','detector','triager','validator','reporter','coverage-guide'}
        assert store.state_value=='running'
    asyncio.run(scenario())


def test_model_protocol_probes_and_missing_bindings_fail_closed():
    from foundry_v2.integrations.preflight import probe_ollama,Preflight
    class Client:
        async def list(self): return {'models':[{'model':'qwen3-coder:30b','digest':'a'*64}]}
        async def chat(self,**kwargs):
            marker=kwargs['messages'][0]['content'].split()[-1]
            if kwargs.get('tools'):
                return {'message':{'tool_calls':[{'function':{'name':'foundry_probe','arguments':{'marker':marker}}}]}}
            return {'message':{'content':marker},'prompt_eval_count':10,'eval_count':1}
    async def scenario():
        assert (await probe_ollama(Client()))['passed']
        report=await Preflight({}).run(fixture_config())
        assert report['passed'] is False and len(report['checks'])==8
    asyncio.run(scenario())


def test_start_race_and_cap_exhaustion_resume_guard(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from foundry_v2.api.auth import Principal
    from foundry_v2.contracts.models import Conflict
    from foundry_v2.substrate.owner import Owner
    from foundry_v2.substrate.evaluations import Evaluations
    with Owner(tmp_path) as owner:
        evaluations=Evaluations(owner); actor=Principal('fixture-operator','operator')
        def start(key):
            try: return evaluations.start(actor,{'configuration':fixture_config(),'expected_installation_version':0},key)
            except Conflict: return None
        with ThreadPoolExecutor(2) as pool: results=list(pool.map(start,['one','two']))
        assert sum(r is not None for r in results)==1
        identity=next(r['resource_id'] for r in results if r)
        evaluations.control(actor,identity,{'action':'stop','reason':'fixture','expected_version':0},'stop')
        with owner.transaction() as db:
            db.execute('INSERT INTO runtime_records VALUES(?,?,?, ?,0)',(identity,'budget-halt','installation','{"requires_cap_raise":true}'))
        with pytest.raises(Conflict,match='cap_raise_required'):
            evaluations.control(actor,identity,{'action':'resume','reason':'fixture','expected_version':1},'resume')


def test_crash_loop_backoff_caps_delay_without_capping_attempts():
    from foundry_v2.orchestrator.lifecycle import Lifecycle
    class Clock:
        now=1799
        def utc(self): return self.now
        def monotonic(self): return self.now
    class Store:
        def __init__(self): self.reservations=[]
        async def snapshot(self,e): return {'state':'indexing','configuration':fixture_config(),'index_queryable':False,
            'sessions':[{'session_id':'old','role':'indexer','slot':0,'incarnation':500,'restart_count':500,'state':'dead','ended_at':0}]}
        async def reserve(self,e,role,slot,inc,restarts):
            self.reservations.append((inc,restarts)); return {'session_id':'new'}
    class Deployment:
        async def list_jobs(self,e): return []
        async def create_job(self,s): pass
    async def scenario():
        clock,store=Clock(),Store(); lifecycle=Lifecycle(store,Deployment(),None,clock)
        await lifecycle.reconcile('e'); assert not store.reservations
        clock.now=1800; await lifecycle.reconcile('e'); assert store.reservations==[(501,501)]
    asyncio.run(scenario())


def test_critical_configuration_change_invalidates_index_and_goals(tmp_path):
    from foundry_v2.api.auth import Principal
    from foundry_v2.substrate.owner import Owner
    from foundry_v2.substrate.evaluations import Evaluations
    from foundry_v2.substrate.lifecycle import LifecycleRecords
    with Owner(tmp_path) as owner:
        evaluations=Evaluations(owner); actor=Principal('fixture-operator','operator'); config=fixture_config()
        identity=evaluations.start(actor,{'configuration':config,'expected_installation_version':0},'start')['resource_id']
        updated=copy.deepcopy(config); updated['target'][0]['revision']='b'*40; updated['goals']='New explicit operator goal'
        assert evaluations.update(actor,identity,{'configuration':updated,'expected_version':0},'update')['state']=='restart-required'
        controller=LifecycleRecords(owner); infrastructure=Principal('controller','infrastructure')
        controller.command(infrastructure,identity,'restart',{},'restart')
        snapshot=controller.snapshot(infrastructure,identity)
        assert snapshot['state']=='preflight' and not snapshot['index_queryable'] and not snapshot['restart_requested']
        assert snapshot['targets'][0]['source_commit']=='b'*40
