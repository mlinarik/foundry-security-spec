"""Owner-transaction checkpoint visibility and session-exclusive threads."""
import json

from foundry_v2.api.auth import Forbidden
from foundry_v2.checkpoints.codec import SafeCodec
from foundry_v2.contracts.models import Conflict, DomainError, new_id
from foundry_v2.substrate.audit import event
from foundry_v2.substrate.blobs import BlobStore
from foundry_v2.substrate.snapshots import Missing, require_evaluation, sequence
from foundry_v2.substrate.transactions import canonical, mutate


class Checkpoints:
    def __init__(self,owner,queues):
        self.owner,self.queues=owner,queues
        self.blobs=BlobStore(owner)
        self.codec=SafeCodec()

    def authorize(self,db,actor,evaluation,thread,create=False):
        require_evaluation(db,evaluation)
        if actor.kind=='operator':
            if create: raise Forbidden('worker_checkpoint_identity_required')
            return
        self.queues.session(db,actor)
        if actor.evaluation_id!=evaluation or not thread.startswith(actor.session_id+':'):
            raise Forbidden('checkpoint_thread_scope_mismatch')
        row=db.execute('SELECT session_id FROM checkpoint_threads WHERE evaluation_id=? AND thread_id=?',(evaluation,thread)).fetchone()
        if row is not None and row[0]!=actor.session_id:
            raise Forbidden('checkpoint_thread_scope_mismatch')
        if row is None and create:
            db.execute('INSERT INTO checkpoint_threads VALUES(?,?,?)',(evaluation,thread,actor.session_id))

    def validate(self,payload):
        if payload['codec_version']!=self.codec.version:
            raise DomainError('unsupported_checkpoint_codec')
        try:
            channels=self.codec.decode(payload['channel_values'])
            if not isinstance(channels,dict): raise ValueError()
            data=canonical(payload).encode()
            if len(data)>self.codec.maximum_bytes: raise ValueError()
        except (ValueError,TypeError,KeyError):
            raise DomainError('invalid_checkpoint_encoding') from None
        if payload['pending_writes']:
            raise DomainError('use_pending_write_endpoint')
        return data

    def put(self,actor,evaluation,thread,namespace,identity,payload,key):
        if payload['checkpoint_id']!=identity:
            raise DomainError('checkpoint_identity_mismatch')
        data=self.validate(payload)
        with self.owner.transaction() as db:
            self.authorize(db,actor,evaluation,thread)
        digest=self.blobs.put(data,media_type='application/vnd.foundry.checkpoint+json')
        def effect(db):
            self.authorize(db,actor,evaluation,thread,True)
            previous=db.execute('SELECT channels_digest FROM checkpoint_tuples WHERE evaluation_id=? AND thread_id=? AND namespace=? AND checkpoint_id=?',(evaluation,thread,namespace,identity)).fetchone()
            if previous and previous[0]!=digest:
                raise Conflict('checkpoint_immutable')
            if payload['parent_id'] and not db.execute('SELECT 1 FROM checkpoint_tuples WHERE evaluation_id=? AND thread_id=? AND namespace=? AND checkpoint_id=?',(evaluation,thread,namespace,payload['parent_id'])).fetchone():
                raise Conflict('checkpoint_parent_missing')
            if not previous:
                db.execute('INSERT INTO checkpoint_tuples VALUES(?,?,?,?,?,?,?,?,?)',
                           (evaluation,thread,namespace,identity,payload['parent_id'],canonical(payload['metadata']),digest,
                            canonical({'channel_versions':payload['channel_versions'],'versions_seen':payload['versions_seen']}),payload['codec_version']))
                db.execute('UPDATE blobs SET ref_count=ref_count+1 WHERE digest=?',(digest,))
                db.execute('INSERT OR IGNORE INTO blob_grants VALUES(?,?,?,?)',(evaluation,digest,actor.session_id,'checkpoint'))
                db.execute('INSERT INTO checkpoint_writes SELECT * FROM checkpoint_pending WHERE evaluation_id=? AND thread_id=? AND namespace=? AND checkpoint_id=?',(evaluation,thread,namespace,identity))
                db.execute('DELETE FROM checkpoint_pending WHERE evaluation_id=? AND thread_id=? AND namespace=? AND checkpoint_id=?',(evaluation,thread,namespace,identity))
                event(db,actor,evaluation,'checkpoint.put',identity)
            return {'request_id':new_id(),'resource_id':identity,'version':0}
        return mutate(self.owner,actor.subject,'PUT',f'{evaluation}/checkpoints/{thread}/{namespace}/{identity}',key,payload,effect)

    def read_in_transaction(self,db,evaluation,thread,namespace,identity):
        row=db.execute('SELECT channels_digest FROM checkpoint_tuples WHERE evaluation_id=? AND thread_id=? AND namespace=? AND checkpoint_id=?',(evaluation,thread,namespace,identity)).fetchone()
        if row is None: raise Missing('checkpoint_not_found')
        payload=json.loads(self.blobs.read_in_transaction(db,row[0]))
        payload['pending_writes']=[{'task_id':r['task_id'],'channel':r['channel'],'value':json.loads(self.blobs.read_in_transaction(db,r['value_digest'])),'task_path':r['task_path'],'write_index':r['write_index']}
                                  for r in db.execute('SELECT * FROM checkpoint_writes WHERE evaluation_id=? AND thread_id=? AND namespace=? AND checkpoint_id=? ORDER BY task_id,write_index',(evaluation,thread,namespace,identity))]
        return payload

    def get(self,actor,evaluation,thread,namespace,identity):
        with self.owner.transaction() as db:
            self.authorize(db,actor,evaluation,thread)
            return self.read_in_transaction(db,evaluation,thread,namespace,identity)

    def list(self,actor,evaluation,thread,namespace,before=None,limit=100):
        if not 1<=limit<=100: raise DomainError('invalid_page_size')
        with self.owner.transaction() as db:
            self.authorize(db,actor,evaluation,thread)
            rows=db.execute('SELECT checkpoint_id FROM checkpoint_tuples WHERE evaluation_id=? AND thread_id=? AND namespace=? AND (? IS NULL OR checkpoint_id<?) ORDER BY checkpoint_id DESC LIMIT ?',
                            (evaluation,thread,namespace,before,before,limit+1)).fetchall()
            return {'items':[self.read_in_transaction(db,evaluation,thread,namespace,r[0]) for r in rows[:limit]],
                    'next_cursor':rows[limit-1][0] if len(rows)>limit else None,'snapshot_id':sequence(db)}

    def writes(self,actor,evaluation,thread,namespace,identity,payload,key):
        with self.owner.transaction() as db:
            self.authorize(db,actor,evaluation,thread)
        digests=[]
        for write in payload['writes']:
            try:
                self.codec.decode(write['value'])
                data=canonical(write['value']).encode()
                if len(data)>self.codec.maximum_bytes: raise ValueError()
            except (ValueError,TypeError,KeyError):
                raise DomainError('invalid_checkpoint_encoding') from None
            digests.append(self.blobs.put(data))
        def effect(db):
            self.authorize(db,actor,evaluation,thread,True)
            ready=db.execute('SELECT 1 FROM checkpoint_tuples WHERE evaluation_id=? AND thread_id=? AND namespace=? AND checkpoint_id=?',(evaluation,thread,namespace,identity)).fetchone()
            table='checkpoint_writes' if ready else 'checkpoint_pending'
            for write,digest in zip(payload['writes'],digests):
                previous=db.execute(f'SELECT value_digest FROM {table} WHERE evaluation_id=? AND thread_id=? AND namespace=? AND checkpoint_id=? AND task_id=? AND write_index=?',
                                    (evaluation,thread,namespace,identity,payload['task_id'],write['write_index'])).fetchone()
                if previous and write['write_index']>=0: continue
                if previous:
                    db.execute('UPDATE blobs SET ref_count=ref_count-1 WHERE digest=?',(previous[0],))
                db.execute(f'INSERT INTO {table} VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(evaluation_id,thread_id,namespace,checkpoint_id,task_id,write_index) DO UPDATE SET value_digest=excluded.value_digest,channel=excluded.channel,task_path=excluded.task_path',
                           (evaluation,thread,namespace,identity,payload['task_id'],write['write_index'],payload['task_path'],write['channel'],digest))
                db.execute('UPDATE blobs SET ref_count=ref_count+1 WHERE digest=?',(digest,))
                db.execute('INSERT OR IGNORE INTO blob_grants VALUES(?,?,?,?)',(evaluation,digest,actor.session_id,'checkpoint'))
            return {'request_id':new_id(),'resource_id':identity,'version':0}
        return mutate(self.owner,actor.subject,'PUT',f'{evaluation}/checkpoints/{thread}/{namespace}/{identity}/writes',key,payload,effect)

    def delete(self,actor,evaluation,thread,namespace,key):
        def effect(db):
            self.authorize(db,actor,evaluation,thread)
            params=(evaluation,thread,namespace,namespace)
            digests=[r[0] for r in db.execute('SELECT channels_digest FROM checkpoint_tuples WHERE evaluation_id=? AND thread_id=? AND (? IS NULL OR namespace=?)',params)]
            digests += [r[0] for r in db.execute('SELECT value_digest FROM checkpoint_writes WHERE evaluation_id=? AND thread_id=? AND (? IS NULL OR namespace=?)',params)]
            digests += [r[0] for r in db.execute('SELECT value_digest FROM checkpoint_pending WHERE evaluation_id=? AND thread_id=? AND (? IS NULL OR namespace=?)',params)]
            db.execute('DELETE FROM checkpoint_pending WHERE evaluation_id=? AND thread_id=? AND (? IS NULL OR namespace=?)',params)
            db.execute('DELETE FROM checkpoint_writes WHERE evaluation_id=? AND thread_id=? AND (? IS NULL OR namespace=?)',params)
            db.execute('DELETE FROM checkpoint_tuples WHERE evaluation_id=? AND thread_id=? AND (? IS NULL OR namespace=?)',params)
            for digest in digests: db.execute('UPDATE blobs SET ref_count=ref_count-1 WHERE digest=?',(digest,))
            event(db,actor,evaluation,'checkpoint.delete',thread)
            return {'request_id':new_id(),'resource_id':thread,'version':0}
        return mutate(self.owner,actor.subject,'DELETE',f'{evaluation}/checkpoints/{thread}/{namespace}',key,{},effect)
