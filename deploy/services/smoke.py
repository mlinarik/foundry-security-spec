"""Authorized live application smoke test; tokens stay in process memory."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import socket
import subprocess
import time

import httpx


def kubectl(*args):
    return subprocess.run(['kubectl',*args],text=True,capture_output=True,check=True).stdout


@contextmanager
def forward(namespace, service):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
    service_port=json.loads(kubectl('get','service',service,'-n',namespace,'-o','json'))['spec']['ports'][0]['port']
    process=subprocess.Popen(['kubectl','port-forward','-n',namespace,'service/'+service,f'{port}:{service_port}','--address','127.0.0.1'],
                             stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=15,trust_env=False) as client:
            deadline=time.monotonic()+20
            while True:
                if process.poll() is not None:
                    raise RuntimeError('Port-forward exited')
                try:
                    if client.get('/healthz').status_code==200:
                        break
                except httpx.HTTPError:
                    pass
                if time.monotonic()>deadline:
                    raise RuntimeError('Service did not become available')
                time.sleep(0.2)
            yield client
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait()


def inspect(namespace):
    token=kubectl('create','token','operator','-n',namespace,'--audience=foundry-v2','--duration=10m').strip()
    unauthorized=kubectl('create','token','substrate','-n',namespace,'--audience=foundry-v2','--duration=10m').strip()
    wrong_audience=kubectl('create','token','operator','-n',namespace,'--audience=foundry-wrong','--duration=10m').strip()
    checks={}
    with forward(namespace,'orchestrator') as client:
        checks['orchestrator_ready']=client.get('/readyz').status_code==200
        checks['dashboard_served']=client.get('/').status_code==200
        checks['anonymous_rejected']=client.get('/v1/installation').status_code==401
        checks['operator_authenticated']=client.get('/v1/installation',headers={'Authorization':'Bearer '+token}).status_code==200
        checks['nonoperator_rejected']=client.get('/v1/installation',headers={'Authorization':'Bearer '+unauthorized}).status_code==403
        checks['wrong_audience_rejected']=client.get('/v1/installation',headers={'Authorization':'Bearer '+wrong_audience}).status_code==401
        state=client.get('/v1/installation',headers={'Authorization':'Bearer '+token}).json()
        checks['no_evaluation_created']=state.get('active_evaluation_id') is None
        response=client.post('/v1/evaluations',headers={'Authorization':'Bearer '+token,'Idempotency-Key':'live-start-gate'},
                             json={'configuration':{},'expected_installation_version':state['version']})
        checks['incomplete_evaluation_blocked']=response.status_code==503 and response.json().get('code')=='evaluation_runtime_incomplete'
    with forward(namespace,'substrate') as client:
        checks['substrate_ready']=client.get('/readyz').status_code==200
        checks['substrate_anonymous_rejected']=client.get('/substrate/v1/installation').status_code==401
        response=client.get('/substrate/v1/installation',headers={'Authorization':'Bearer '+token})
        checks['substrate_operator_authenticated']=response.status_code==200
        installation=response.json()
    if not all(checks.values()):
        raise RuntimeError('Live service checks failed: '+json.dumps(checks))
    return checks,installation


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--namespace',default='foundry-v2')
    parser.add_argument('--restart-substrate',action='store_true')
    parser.add_argument('--output',default='deploy/services/live-results.json')
    args=parser.parse_args()
    checks,before=inspect(args.namespace)
    if args.restart_substrate:
        kubectl('rollout','restart','deployment/substrate','-n',args.namespace)
        kubectl('rollout','status','deployment/substrate','-n',args.namespace,'--timeout=60s')
        kubectl('rollout','status','deployment/orchestrator','-n',args.namespace,'--timeout=60s')
        _,after=inspect(args.namespace)
        checks['restart_persists_installation']=after['installation_id']==before['installation_id']
        checks['restart_advances_owner_epoch']=after['owner_epoch']==before['owner_epoch']+1
        if not all(checks.values()):
            raise RuntimeError('Restart persistence checks failed')
    deployments=json.loads(kubectl('get','deployment','-n',args.namespace,'-o','json'))
    pods=json.loads(kubectl('get','pods','-n',args.namespace,'-o','json'))
    result={'observed_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
            'namespace':args.namespace,'checks':checks,
            'deployments':{d['metadata']['name']:{'ready_replicas':d['status'].get('readyReplicas',0),
                          'image':d['spec']['template']['spec']['containers'][0]['image']} for d in deployments['items']},
            'pods':[{ 'name':p['metadata']['name'],'node':p['spec']['nodeName'],'phase':p['status']['phase'],
                      'image_id':p['status']['containerStatuses'][0]['imageID']} for p in pods['items']],
            'scope':'Foundation application services; no evaluation workers or model calls',
            'operator_overrides':{'transport':'private HTTP','storage':'node-local RWO; no CSI RWOP claim'}}
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
