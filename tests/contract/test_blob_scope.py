import hashlib
import time

from fastapi.testclient import TestClient

from foundry_v2.api.auth import OperatorAuth
from foundry_v2.substrate.app import create_app
from foundry_v2.substrate.auth import SessionAuth
from foundry_v2.substrate.owner import Owner


def test_blob_api_checks_evaluation_and_session_grants(tmp_path):
    with Owner(tmp_path) as owner:
        evaluation=owner.reserve_evaluation(0)
        with owner.transaction() as db:
            for slot,role in enumerate(('detector','validator')):
                db.execute('INSERT INTO sessions(session_id,evaluation_id,role,slot,incarnation,pod_name,state,heartbeat_at) VALUES(?,?,?,?,?,?,?,?)',
                           (role,evaluation,role,slot,0,role,'running',time.time()))
        auth=SessionAuth(owner)
        for role in ('detector','validator'):
            auth.issue(evaluation,role,role,role*16,time.time()+3600)
        operators=OperatorAuth(lambda _: {},[],[],'foundry-v2')
        with TestClient(create_app(owner,operators,'i'*48),base_url='https://testserver') as client:
            data=b'private author conversation'
            digest=hashlib.sha256(data).hexdigest()
            path=f'/substrate/v1/evaluations/{evaluation}/blobs/{digest}'
            author={'Authorization':'Bearer '+'detector'*16,'Idempotency-Key':'blob'}
            assert client.put(path,headers=author,content=data).status_code==200
            assert client.get(path,headers=author).content==data
            reproducer={'Authorization':'Bearer '+'validator'*16}
            assert client.get(path,headers=reproducer).status_code==403
            assert client.get(path.replace(evaluation,'other'),headers=author).status_code==403
            assert client.put(path,headers=dict(author,**{'Idempotency-Key':'wrong'}),content=b'changed').status_code==400
