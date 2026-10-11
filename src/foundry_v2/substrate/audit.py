import time
import logging

from foundry_v2.contracts.models import new_id
from foundry_v2.substrate.transactions import canonical, mutate
from foundry_v2.workers.transcripts import Redactor


def event(db, actor, evaluation, action, resource, prior=None, version=None, reason=None, clock=time.time):
    """Append within the aggregate mutation transaction; callers never log credentials."""
    db.execute('INSERT INTO audit_events(event_id,evaluation_id,actor_kind,actor_id,action,resource,prior_version,new_version,reason,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
               (new_id(),evaluation,actor.kind,actor.subject,action,resource,prior,version,reason,clock()))


def transcript(owner,blobs,queues,actor,kind,content,key,secrets=()):
    with owner.transaction() as db:
        queues.session(db,actor)
    redacted=Redactor(secrets).redact(content)
    try:
        digest=blobs.put(canonical(redacted).encode(),media_type='application/vnd.foundry.transcript+json')
        def effect(db):
            queues.session(db,actor)
            db.execute('INSERT INTO transcript_chunks(evaluation_id,session_id,kind,content_digest,created_at) VALUES(?,?,?,?,?)',
                       (actor.evaluation_id,actor.session_id,kind,digest,time.time()))
            identity=str(db.execute('SELECT last_insert_rowid()').fetchone()[0])
            db.execute('UPDATE blobs SET ref_count=ref_count+1 WHERE digest=?',(digest,))
            db.execute('INSERT OR IGNORE INTO blob_grants VALUES(?,?,?,?)',(actor.evaluation_id,digest,actor.session_id,'checkpoint'))
            event(db,actor,actor.evaluation_id,'transcript.'+kind,identity)
            return {'request_id':new_id(),'resource_id':identity,'version':0}
        return mutate(owner,actor.subject,'POST',f'{actor.evaluation_id}/transcripts',key,{'kind':kind,'content':redacted},effect)
    except Exception:
        # Persistence failure cannot be made durable in the failed store itself.
        logging.getLogger('foundry.persistence').error('transcript_persistence_failed session=%s kind=%s',actor.session_id,kind)
        raise
