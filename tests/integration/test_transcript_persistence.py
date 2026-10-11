import json
import time

from foundry_v2.api.auth import Principal
from foundry_v2.substrate.audit import transcript
from foundry_v2.substrate.blobs import BlobStore
from foundry_v2.substrate.claims import WorkQueues
from foundry_v2.substrate.owner import Owner


def test_transcript_redaction_receipt_and_durable_sequence(tmp_path):
    with Owner(tmp_path) as owner:
        evaluation=owner.reserve_evaluation(0)
        with owner.transaction() as db:
            db.execute('INSERT INTO sessions(session_id,evaluation_id,role,slot,incarnation,pod_name,state,heartbeat_at) VALUES(?,?,?,?,?,?,?,?)',
                       ('s',evaluation,'detector',0,0,'p','running',time.time()))
        actor=Principal('credential','worker',evaluation,'s','detector')
        blobs=BlobStore(owner); queues=WorkQueues(owner,60,3)
        content={'body':'known-private Bearer abc123','token':'sensitive','origin':'target'}
        first=transcript(owner,blobs,queues,actor,'turn',content,'once',['known-private'])
        assert transcript(owner,blobs,queues,actor,'turn',content,'once',['known-private'])==first
        with owner.transaction() as db:
            rows=db.execute('SELECT content_digest FROM transcript_chunks').fetchall()
            assert len(rows)==1
            encoded=blobs.read_in_transaction(db,rows[0][0])
            assert b'known-private' not in encoded and b'abc123' not in encoded and b'sensitive' not in encoded
            assert json.loads(encoded)['origin']=='target'
            assert db.execute('SELECT COUNT(*) FROM audit_events').fetchone()[0]==1
