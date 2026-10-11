import copy
import hashlib
import sqlite3
import time

import pytest

from foundry_v2.api.auth import Principal
from foundry_v2.substrate.blobs import BlobStore
from foundry_v2.substrate.claims import WorkQueues
from foundry_v2.substrate.generations import Generations
from foundry_v2.substrate.owner import Owner


def test_bad_generation_preserves_previous_complete_index(tmp_path):
    with Owner(tmp_path) as owner:
        evaluation=owner.reserve_evaluation(0)
        actor=Principal('credential','worker',evaluation,'s','indexer')
        with owner.transaction() as db:
            db.execute('INSERT INTO sessions(session_id,evaluation_id,role,slot,incarnation,pod_name,state,heartbeat_at) VALUES(?,?,?,?,?,?,?,?)',
                       ('s',evaluation,'indexer',0,0,'p','running',time.time()))
            db.execute('INSERT INTO targets(target_id,vcs_url,repository_identity,pinned_commit,scope_json) VALUES(?,?,?,?,?)',('t','fixture','fixture','a'*40,'{}'))
            db.execute('INSERT INTO evaluation_targets(evaluation_id,target_id,source_commit) VALUES(?,?,?)',(evaluation,'t','a'*40))
        blobs=BlobStore(owner); digest=blobs.put(b'def f(): return 1')
        with owner.transaction() as db: db.execute('INSERT INTO blob_grants VALUES(?,?,?,?)',(evaluation,digest,'s','artifact'))
        store=Generations(owner,blobs,WorkQueues(owner,60,3))
        payload={'kind':'index','expected_version':0,'blob_digests':[digest],'content':{'target_id':'t','source_commit':'a'*40,
                 'units':[{'unit_id':'f','path':'source.py','symbol':'f','language':'python','ranges':{'start_line':1,'end_line':1},'body_digest':digest,'file_hash':'b'*64}], 'edges':[]}}
        first=store.commit(actor,evaluation,payload,'first')
        bad=copy.deepcopy(payload); bad['expected_version']=1
        bad['content']['edges']=[{'caller_id':'missing','callee_id':None,'unresolved_name':'dynamic','kind':'unresolved'}]
        with pytest.raises(sqlite3.IntegrityError): store.commit(actor,evaluation,bad,'failure')
        with owner.transaction() as db:
            assert db.execute('SELECT index_generation FROM evaluation_targets').fetchone()[0]==first['resource_id']
            assert db.execute('SELECT COUNT(*) FROM index_generations').fetchone()[0]==1
            assert db.execute('SELECT COUNT(*) FROM code_units').fetchone()[0]==1
