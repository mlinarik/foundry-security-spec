import multiprocessing

from fastapi.testclient import TestClient

from foundry_v2.api.auth import OperatorAuth
from foundry_v2.substrate.app import create_app
from foundry_v2.substrate.owner import Owner


def parse_cpu(started,finished):
    from foundry_v2.indexing.parser import parse_files
    started.set()
    while not finished.is_set():
        parse_files('fixture',{'large.py':b'def f():\n return 1\n'*15000})


def test_cpu_indexer_process_does_not_block_status(tmp_path):
    context=multiprocessing.get_context('spawn'); started=context.Event(); finished=context.Event()
    process=context.Process(target=parse_cpu,args=(started,finished))
    with Owner(tmp_path) as owner:
        evaluation=owner.reserve_evaluation(0)
        auth=OperatorAuth(lambda _: {'authenticated':True,'audiences':['foundry-v2'],'user':{'username':'alice','groups':[]}},['alice'],[],'foundry-v2')
        with TestClient(create_app(owner,auth,'i'*48),base_url='https://testserver') as client:
            try:
                process.start(); assert started.wait(10)
                assert client.get(f'/substrate/v1/evaluations/{evaluation}/snapshot',headers={'Authorization':'Bearer fixture'}).status_code==200
                assert process.pid!=__import__('os').getpid()
                assert process.is_alive() and not finished.is_set()
            finally:
                finished.set()
                process.join(2)
                if process.is_alive(): process.terminate(); process.join(2)
