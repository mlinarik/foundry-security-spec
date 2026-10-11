"""Indexer role uses deterministic source parsing, never model-authored inventories."""
import asyncio

from foundry_v2.indexing.service import build_index,publish_index


class Indexer:
    def __init__(self,client):
        self.client=client

    async def __call__(self,state):
        results=[]
        for target in state['targets']:
            index=await asyncio.to_thread(build_index,target['target_id'],target['root'],target['scope'])
            result=await asyncio.to_thread(publish_index,self.client,state['evaluation_id'],target['target_id'],target['commit'],index,target.get('index_version',0))
            results.append(dict(result,target_id=target['target_id']))
        return dict(state,index_results=results,index_queryable=bool(results) and all(r['queryable'] for r in results))
