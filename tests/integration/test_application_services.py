from fastapi.testclient import TestClient
import time

from foundry_v2.api.auth import OperatorAuth
from foundry_v2.orchestrator.app import create_app as create_orchestrator
from foundry_v2.substrate.app import create_app as create_substrate
from foundry_v2.substrate.owner import Owner


def operators():
    return OperatorAuth(lambda t: {'authenticated': t == 'operator', 'audiences': ['foundry-v2'],
                                  'user': {'username': 'alice', 'groups': []}},
                        subjects=['alice'], groups=[], audience='foundry-v2')


def test_substrate_health_auth_scope_and_restart_persistence(tmp_path):
    with Owner(tmp_path) as owner:
        evaluation = owner.reserve_evaluation(0)
        app = create_substrate(owner, operators(), 'i' * 48)
        with TestClient(app, base_url='https://testserver') as client:
            assert client.get('/healthz').status_code == 200
            assert client.get('/substrate/v1/installation').status_code == 401
            headers = {'Authorization': 'Bearer operator'}
            state = client.get('/substrate/v1/installation', headers=headers).json()
            assert state['active_evaluation_id'] == evaluation
            snapshot = client.get(f'/substrate/v1/evaluations/{evaluation}/snapshot', headers=headers)
            assert snapshot.status_code == 200
            assert snapshot.json()['budget']['usage_status'] == 'unknown'
            assert client.get('/substrate/v1/evaluations/missing/snapshot', headers=headers).status_code == 404
            assert client.get(f'/substrate/v1/evaluations/{evaluation}/snapshot',
                              headers={'Authorization': 'Bearer ' + 'i' * 48}).status_code == 200
            assert client.post(f'/substrate/v1/evaluations/{evaluation}/sessions', headers=headers,
                               json={'session_id': 's', 'role': 'indexer', 'slot': 0, 'incarnation': 0, 'pod_name': 'p'}).status_code == 403
    with Owner(tmp_path) as owner:
        assert owner.epoch == 2
        with owner.transaction() as db:
            assert db.execute('SELECT active_evaluation_id FROM installations').fetchone()[0] == evaluation


def test_orchestrator_never_starts_an_incomplete_fleet():
    class Substrate:
        def get(self, path, bearer):
            return {'installation_id': 'i', 'active_evaluation_id': None, 'version': 0}
        def ready(self):
            return True
        def close(self):
            pass
    app = create_orchestrator(operators(), Substrate())
    with TestClient(app, base_url='https://testserver') as client:
        assert client.get('/readyz').status_code == 200
        assert client.get('/v1/installation').status_code == 401
        headers = {'Authorization': 'Bearer operator', 'Idempotency-Key': 'start'}
        response = client.post('/v1/evaluations', headers=headers,
                               json={'configuration': {}, 'expected_installation_version': 0})
        assert response.status_code == 503
        assert response.json()['code'] == 'evaluation_runtime_incomplete'
        assert 'i' not in response.json().get('details', {})


def test_http_credentials_are_rejected(tmp_path):
    with Owner(tmp_path) as owner:
        app = create_substrate(owner, operators(), 'i' * 48)
        with TestClient(app, base_url='http://testserver') as client:
            assert client.get('/substrate/v1/installation',
                              headers={'Authorization': 'Bearer operator'}).status_code == 400


def test_explicit_http_override_keeps_authorization_required(tmp_path):
    with Owner(tmp_path) as owner:
        with TestClient(create_substrate(owner,operators(),'i'*48,require_tls=False)) as client:
            assert client.get('/substrate/v1/installation').status_code==401
            assert client.get('/substrate/v1/installation',headers={'Authorization':'Bearer operator'}).status_code==200


def test_registration_provisioning_and_worker_scope_are_enforced(tmp_path):
    with Owner(tmp_path) as owner:
        evaluation=owner.reserve_evaluation(0)
        with TestClient(create_substrate(owner,operators(),'i'*48),base_url='https://testserver') as client:
            path=f'/substrate/v1/evaluations/{evaluation}'
            infrastructure={'Authorization':'Bearer '+'i'*48,'Idempotency-Key':'register'}
            payload={'session_id':'s','role':'detector','slot':0,'incarnation':0,'pod_name':'p'}
            assert client.post(path+'/sessions',json=payload,headers=infrastructure).status_code==200
            token='w'*48
            payload={'session_id':'s','role':'detector','token':token,'expires_at':time.time()+3600}
            infrastructure['Idempotency-Key']='provision'
            first=client.post(path+'/credentials',json=payload,headers=infrastructure)
            assert first.status_code==200
            assert client.post(path+'/credentials',json=payload,headers=infrastructure).json()==first.json()
            payload['token']='z'*48
            assert client.post(path+'/credentials',json=payload,headers=infrastructure).status_code==409
            worker={'Authorization':'Bearer '+token,'Idempotency-Key':'worker'}
            assert client.post(path+'/sessions',json={'session_id':'spoof','role':'reporter','slot':1,'incarnation':0,'pod_name':'spoof'},headers=worker).status_code==403
            assert client.post(path+'/sessions/heartbeat',json={'session_id':'spoof','incarnation':0,'last_event_sequence':0},headers=worker).status_code==403
            assert client.get('/substrate/v1/evaluations/other/tasks',headers=worker).status_code==403
            assert client.get(path+'/snapshot',headers=worker).status_code==403
            with owner.transaction() as db:
                stored=' '.join(str(dict(row)) for row in db.execute('SELECT * FROM credentials'))
                stored+=' '.join(str(dict(row)) for row in db.execute('SELECT * FROM idempotency_keys'))
                assert token not in stored and 'z'*48 not in stored
