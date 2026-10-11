from concurrent.futures import ThreadPoolExecutor

import pytest

from foundry_v2.api.auth import Principal
from foundry_v2.contracts.models import Conflict
from foundry_v2.substrate.claims import WorkQueues
from foundry_v2.substrate.owner import Owner


@pytest.fixture
def queue(tmp_path):
    with Owner(tmp_path) as owner:
        evaluation = owner.reserve_evaluation(0)
        with owner.transaction() as db:
            for slot in range(2):
                db.execute('INSERT INTO sessions(session_id,evaluation_id,role,slot,incarnation,pod_name,state,heartbeat_at) VALUES(?,?,?,?,?,?,?,?)',
                           (f's{slot}',evaluation,'detector',slot,0,f'p{slot}','running',100))
        workers = [Principal(f'c{i}','worker',evaluation,f's{i}','detector') for i in range(2)]
        now = [100]
        queues = WorkQueues(owner,stale_seconds=30,release_limit=2,clock=lambda:now[0],restart_grace=10)
        yield queues,evaluation,workers,now


def test_claim_race_one_winner_and_late_write_fenced(queue):
    q,evaluation,workers,now = queue
    task = q.add(Principal('alice','operator'),evaluation,{'role':'detector','title':'test','description':'test','priority':0},'task')
    def acquire(worker):
        try:
            return q.claim(worker,'task','work',worker.subject)
        except Conflict:
            return None
    with ThreadPoolExecutor(2) as pool:
        results=list(pool.map(acquire,workers))
    assert sum(r is not None for r in results)==1
    winner=next(r for r in results if r)
    worker=next(w for w in workers if w.session_id==winner['session_id'])
    now[0]=131
    assert q.reap()==2
    with pytest.raises(Conflict):
        q.write(worker,winner['resource_id'],winner['generation'],0,'complete',{},'late')


def test_heartbeat_keeps_slow_claim_and_release_blocks(queue):
    q,evaluation,workers,now=queue
    task=q.add(Principal('alice','operator'),evaluation,{'role':'detector','title':'test','description':'test','priority':0},'task')
    held=q.claim(workers[0],'task','work','claim1')
    now[0]=1000
    q.heartbeat(workers[0],0,'heartbeat')
    assert q.reap()==1  # only the other, stale session
    q.write(workers[0],task['resource_id'],held['generation'],0,'release',{},'release1')
    held=q.claim(workers[0],'task','work','claim2')
    q.write(workers[0],task['resource_id'],held['generation'],1,'release',{},'release2')
    with q.owner.transaction() as db:
        row=db.execute('SELECT * FROM tasks WHERE task_id=?',(task['resource_id'],)).fetchone()
        assert row['state']=='blocked' and row['release_count']==2


def test_queue_identity_and_order_survive_reprioritization(queue):
    q,evaluation,workers,now=queue
    operator=Principal('alice','operator')
    first=q.add(operator,evaluation,{'role':'detector','title':'first','description':'test','priority':10},'first')
    second=q.add(operator,evaluation,{'role':'detector','title':'second','description':'test','priority':20},'second')
    q.edit(operator,evaluation,second['resource_id'],{'priority':0,'expected_version':0},'edit')
    assert q.claim(workers[0],'task','work','claim')['resource_id']==second['resource_id']
    with pytest.raises(Conflict):
        q.edit(operator,evaluation,first['resource_id'],{'priority':1,'expected_version':9},'stale')


def test_restart_grace_and_heartbeat_replay_do_not_extend_liveness(queue):
    q,evaluation,workers,now=queue
    now[0]=101
    assert q.reap()==0
    q.heartbeat(workers[0],0,'once')
    now[0]=132
    q.heartbeat(workers[0],0,'once')
    assert q.reap()==2


@pytest.mark.parametrize('kind',['finding','file'])
def test_resource_claims_share_race_fence_and_auto_block(queue,kind):
    q,evaluation,workers,now=queue
    with q.owner.transaction() as db:
        q.enqueue_resource(db,evaluation,kind,'r','detector','directed',{'path':'source.py'})
    def acquire(worker):
        try: return q.claim(worker,kind,'directed',worker.subject)
        except Conflict: return None
    with ThreadPoolExecutor(2) as pool: results=list(pool.map(acquire,workers))
    assert sum(r is not None for r in results)==1
    claim=next(r for r in results if r)
    worker=next(w for w in workers if w.session_id==claim['session_id'])
    q.write(worker,'r',claim['generation'],0,'release',{},'release')
    with pytest.raises(Conflict):
        q.write(worker,'r',claim['generation'],1,'complete',{},'late')
    held=q.claim(worker,kind,'directed','again')
    q.write(worker,'r',held['generation'],1,'release',{},'release-again')
    with pytest.raises(Conflict): q.claim(worker,kind,'directed','blocked')


def test_named_queues_do_not_cross_claim_order(queue):
    from foundry_v2.substrate.tasks import Tasks
    q,evaluation,workers,now=queue
    queue_a,queue_b=Tasks(q,'a'),Tasks(q,'b')
    operator=Principal('alice','operator')
    payload={'role':'detector','title':'test','description':'test','priority':0}
    a=queue_a.add(operator,evaluation,payload,'a')
    b=queue_b.add(operator,evaluation,payload,'b')
    assert queue_b.claim(workers[0],'claim-b')['resource_id']==b['resource_id']
    assert queue_a.claim(workers[1],'claim-a')['resource_id']==a['resource_id']
