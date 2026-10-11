"""Scoped committed-generation queries and independently executable index construction."""
import json

from foundry_v2.api.auth import Forbidden
from foundry_v2.contracts.models import Conflict,DomainError,new_id
from foundry_v2.indexing.parser import parse_files
from foundry_v2.indexing.source import discover
from foundry_v2.substrate.snapshots import Missing,sequence


class IndexQueries:
    def __init__(self,owner,blobs,queues):
        self.owner,self.blobs,self.queues=owner,blobs,queues

    def query(self,actor,evaluation,payload):
        with self.owner.transaction() as db:
            if actor.kind=='worker':
                self.queues.session(db,actor)
                if actor.evaluation_id!=evaluation or actor.purpose=='validation-reproduce': raise Forbidden('index_scope_mismatch')
            elif actor.kind not in ('operator','infrastructure'): raise Forbidden('index_scope_mismatch')
            generation=payload['generation_id']; target=payload['target_id']
            row=db.execute('SELECT 1 FROM index_generations WHERE generation_id=? AND evaluation_id=? AND target_id=? AND state=\'ready\'',(generation,evaluation,target)).fetchone()
            if not row: raise Missing('committed_index_not_found')
            arguments=payload['arguments']; operation=payload['operation']
            units=[dict(u) for u in db.execute('SELECT * FROM code_units WHERE generation_id=? ORDER BY path,symbol',(generation,))]
            for unit in units:
                unit['ranges']=json.loads(unit['ranges'])
            items=[]
            if operation=='list-functions': items=units
            elif operation in ('function-body','callers','callees'):
                identity=arguments.get('unit_id'); matches=[u for u in units if u['unit_id']==identity]
                if not matches: raise Missing('code_unit_not_found')
                if operation=='function-body':
                    items=[dict(matches[0],body=self.blobs.read_in_transaction(db,matches[0]['body_digest']).decode('utf-8'))]
                else:
                    direction='callee_id' if operation=='callers' else 'caller_id'
                    edges=[dict(r) for r in db.execute(f'SELECT * FROM call_edges WHERE generation_id=? AND {direction}=?',(generation,identity))]
                    for edge in edges:
                        other=edge['caller_id'] if operation=='callers' else edge['callee_id']
                        edge['unit']=next((u for u in units if u['unit_id']==other),None)
                    items=edges
            elif operation=='find-symbol':
                symbol=arguments.get('symbol')
                if not isinstance(symbol,str): raise DomainError('symbol_required')
                items=[u for u in units if u['symbol']==symbol]
            elif operation=='full-text':
                text=arguments.get('text')
                if not isinstance(text,str) or not text or len(text)>1024: raise DomainError('bounded_search_text_required')
                file_records=db.execute('SELECT payload FROM runtime_records WHERE evaluation_id=? AND kind=?',(evaluation,'index-files:'+generation)).fetchall()
                if file_records:
                    for record in file_records:
                        file=json.loads(record[0]); body=self.blobs.read_in_transaction(db,file['digest']).decode('utf-8',errors='replace')
                        if text in body: items.append(dict(file,body=body))
                else:
                    for unit in units:
                        body=self.blobs.read_in_transaction(db,unit['body_digest']).decode('utf-8')
                        if text in body: items.append(dict(unit,body=body))
            else: raise DomainError('invalid_index_operation')
            return {'items':items,'next_cursor':None,'snapshot_id':sequence(db)}


def build_index(target,root,scope):
    sources,skipped=discover(root,scope['include'],scope['exclude'])
    result=parse_files(target,sources); result['skipped'].extend(skipped)
    result['source_files']=sorted(sources)
    # This executes in the Indexer worker process, never the Orchestrator web lane.
    return result


def publish_index(client,evaluation,target,commit,index,expected_version):
    for digest,body in index['bodies'].items():
        client.write_blob(evaluation,body,'index-body:'+digest)
    payload={'kind':'index','expected_version':expected_version,'blob_digests':sorted(index['bodies']),
             'content':{'target_id':target,'source_commit':commit,'units':index['units'],'edges':index['edges'],'files':index['files'],'skipped':index['skipped']}}
    receipt=client.request('POST',f'/substrate/v1/evaluations/{evaluation}/generations',payload=payload,key='index-generation:'+target+':'+commit+':'+str(expected_version))
    for operation,arguments in [('list-functions',{}),('function-body',{'unit_id':index['units'][0]['unit_id']}),
                                ('callers',{'unit_id':index['units'][0]['unit_id']}),('callees',{'unit_id':index['units'][0]['unit_id']}),
                                ('find-symbol',{'symbol':index['units'][0]['symbol']}),('full-text',{'text':index['units'][0]['symbol'].split('.')[-1]})] if index['units'] else []:
        result=client.request('POST',f'/substrate/v1/evaluations/{evaluation}/index/query',payload={'target_id':target,'generation_id':receipt['resource_id'],'operation':operation,'arguments':arguments},key=new_id())
        if operation in ('list-functions','function-body','find-symbol') and not result['items']:
            raise Conflict('index_readiness_failed')
    return dict(receipt,queryable=bool(index['units']),skipped=index['skipped'])
