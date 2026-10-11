"""Validated complete generation publication; previous pointers survive failure."""
import hashlib
import json
import re
from pathlib import PurePosixPath

from foundry_v2.api.auth import Forbidden
from foundry_v2.contracts.models import Conflict,DomainError,new_id
from foundry_v2.substrate.audit import event
from foundry_v2.substrate.snapshots import require_evaluation
from foundry_v2.substrate.transactions import assert_version,canonical,mutate
from foundry_v2.indexing.source import in_scope


class Generations:
    def __init__(self,owner,blobs,queues):
        self.owner,self.blobs,self.queues=owner,blobs,queues

    def authorize(self,db,actor,evaluation,kind,digests):
        self.queues.session(db,actor)
        if actor.evaluation_id!=evaluation: raise Forbidden('evaluation_scope_mismatch')
        allowed={'index':{'indexer'},'coverage':{'coverage-guide'},'notes':{'orchestrator','indexer','cartographer','detector','triager','validator','reporter','coverage-guide'}}
        if actor.role not in allowed.get(kind,{'cartographer'}): raise Forbidden('generation_role_not_allowed')
        for digest in digests:
            if not db.execute('SELECT 1 FROM blob_grants WHERE evaluation_id=? AND digest=? AND purpose=\'artifact\' AND grantee IN (?,\'*\')',
                              (evaluation,digest,actor.session_id)).fetchone(): raise Forbidden('artifact_scope_mismatch')
            self.blobs.read_in_transaction(db,digest)

    def commit(self,actor,evaluation,payload,key):
        kind=payload['kind']; content=payload['content']; digests=payload['blob_digests']
        def effect(db):
            self.authorize(db,actor,evaluation,kind,digests)
            require_evaluation(db,evaluation)
            if kind=='index':
                return self.index(db,actor,evaluation,payload)
            digest=content.get('content_digest')
            if digest not in digests: raise DomainError('generation_content_digest_required')
            prior=db.execute('SELECT COALESCE(MAX(generation),0) FROM security_documents WHERE evaluation_id=? AND kind=?',(evaluation,kind)).fetchone()[0]
            assert_version(prior,payload['expected_version'])
            identity=new_id(); version=prior+1
            revision=content.get('source_revision')
            if not isinstance(revision,str) or not re.fullmatch('[0-9a-f]{40}',revision) or revision=='0'*40: raise DomainError('source_revision_required')
            if kind=='notes' and len(self.blobs.read_in_transaction(db,digest))>32768: raise DomainError('notes_size_exceeded')
            db.execute('INSERT INTO security_documents VALUES(?,?,?,?,?,?,?)',(identity,evaluation,kind,version,digest,int(bool(content.get('fallback',False))),revision))
            db.execute('UPDATE blobs SET ref_count=ref_count+1 WHERE digest=?',(digest,))
            db.execute('INSERT OR IGNORE INTO blob_grants VALUES(?,?,?,?)',(evaluation,digest,'*','artifact'))
            event(db,actor,evaluation,'generation.commit',identity,prior,version)
            return {'request_id':new_id(),'resource_id':identity,'version':version,'state':'ready'}
        return mutate(self.owner,actor.subject,'POST',f'{evaluation}/generations',key,payload,effect)

    def index(self,db,actor,evaluation,payload):
        content=payload['content']; target=content.get('target_id'); commit=content.get('source_commit')
        row=db.execute('SELECT * FROM evaluation_targets WHERE evaluation_id=? AND target_id=?',(evaluation,target)).fetchone()
        if not row or row['source_commit']!=commit: raise Forbidden('target_revision_scope_mismatch')
        target_row=db.execute('SELECT scope_json FROM targets WHERE target_id=?',(target,)).fetchone()
        scope=json.loads(target_row[0])
        if 'include' not in scope or 'exclude' not in scope: raise DomainError('target_scope_required')
        record=db.execute('SELECT version,payload FROM runtime_records WHERE evaluation_id=? AND kind=\'index-version\' AND resource_id=?',(evaluation,target)).fetchone()
        input_hash=hashlib.sha256(canonical({'content':content,'scope':scope}).encode()).hexdigest()
        if record and json.loads(record['payload']).get('input_hash')==input_hash:
            db.execute('UPDATE evaluation_targets SET index_generation=? WHERE evaluation_id=? AND target_id=?',
                       (json.loads(record['payload'])['generation'],evaluation,target))
            return {'request_id':new_id(),'resource_id':json.loads(record['payload'])['generation'],'version':record['version'],'state':'ready'}
        prior=record['version'] if record else 0
        assert_version(prior,payload['expected_version'])
        units=content.get('units'); edges=content.get('edges')
        if not isinstance(units,list) or not isinstance(edges,list): raise DomainError('complete_index_required')
        identity=new_id()
        db.execute('INSERT INTO index_generations VALUES(?,?,?,?,?,?)',(identity,evaluation,target,commit,'building',row['index_generation']))
        for unit in units:
            required={'unit_id','path','symbol','language','ranges','body_digest','file_hash'}
            if set(unit)!=required: raise DomainError('invalid_code_unit')
            path=PurePosixPath(unit['path'])
            if path.is_absolute() or '..' in path.parts or '\\' in unit['path'] or unit['language'] not in ('python','go'):
                raise DomainError('invalid_code_unit_scope')
            if not in_scope(unit['path'],scope['include'],scope['exclude']): raise Forbidden('code_unit_out_of_scope')
            if unit['body_digest'] not in payload['blob_digests']: raise DomainError('code_body_digest_required')
            if not isinstance(unit['file_hash'],str) or not re.fullmatch('[0-9a-f]{64}',unit['file_hash']): raise DomainError('invalid_file_hash')
            ranges=unit['ranges']
            if not isinstance(ranges,dict) or set(ranges)!={'start_line','end_line'} or type(ranges['start_line']) is not int or type(ranges['end_line']) is not int or ranges['start_line']<1 or ranges['end_line']<ranges['start_line']:
                raise DomainError('invalid_code_unit_ranges')
            db.execute('INSERT INTO code_units VALUES(?,?,?,?,?,?,?,?)',(unit['unit_id'],identity,unit['path'],unit['symbol'],unit['language'],canonical(ranges),unit['body_digest'],unit['file_hash']))
            db.execute('UPDATE blobs SET ref_count=ref_count+1 WHERE digest=?',(unit['body_digest'],))
            db.execute('INSERT OR IGNORE INTO blob_grants VALUES(?,?,?,?)',(evaluation,unit['body_digest'],'*','artifact'))
        for edge in edges:
            if set(edge)!={'caller_id','callee_id','unresolved_name','kind'}: raise DomainError('invalid_call_edge')
            db.execute('INSERT INTO call_edges VALUES(?,?,?,?,?)',(identity,edge['caller_id'],edge['callee_id'],edge['unresolved_name'],edge['kind']))
        for file in content.get('files',[]):
            if set(file)!={'path','file_hash','digest','language'} or not in_scope(file['path'],scope['include'],scope['exclude']): raise DomainError('invalid_index_file')
            if file['digest']!=file['file_hash'] or file['digest'] not in payload['blob_digests']: raise DomainError('index_file_digest_mismatch')
            db.execute('INSERT INTO runtime_records VALUES(?,?,?, ?,0)',(evaluation,'index-files:'+identity,file['path'],canonical(file)))
            db.execute('UPDATE blobs SET ref_count=ref_count+1 WHERE digest=?',(file['digest'],))
            db.execute('INSERT OR IGNORE INTO blob_grants VALUES(?,?,?,?)',(evaluation,file['digest'],'*','artifact'))
        db.execute('INSERT INTO runtime_records VALUES(?,?,?, ?,0)',(evaluation,'index-diagnostics',identity,canonical({'skipped':content.get('skipped',[])})))
        db.execute('UPDATE index_generations SET state=\'ready\' WHERE generation_id=?',(identity,))
        db.execute('UPDATE evaluation_targets SET index_generation=? WHERE evaluation_id=? AND target_id=?',(identity,evaluation,target))
        db.execute('INSERT INTO runtime_records VALUES(?,?,?, ?,?) ON CONFLICT(evaluation_id,kind,resource_id) DO UPDATE SET payload=excluded.payload,version=excluded.version',
                   (evaluation,'index-version',target,canonical({'generation':identity,'input_hash':input_hash}),prior+1))
        event(db,actor,evaluation,'index.commit',identity,prior,prior+1)
        return {'request_id':new_id(),'resource_id':identity,'version':prior+1,'state':'ready'}
