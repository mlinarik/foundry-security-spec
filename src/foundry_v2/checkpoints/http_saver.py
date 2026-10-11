"""LangGraph saver backed only by authenticated substrate HTTP."""
import asyncio
import base64
from urllib.parse import quote

import httpx
from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple, WRITES_IDX_MAP, get_checkpoint_metadata

from foundry_v2.checkpoints.codec import SafeCodec
from foundry_v2.contracts.models import new_id


def namespace_segment(namespace):
    # Empty namespace is the specified _root sentinel. Encoded nonempty namespaces
    # avoid ASGI's decoding of escaped slashes before route matching.
    return '_root' if namespace=='' else 'n-'+base64.urlsafe_b64encode(namespace.encode()).decode().rstrip('=')


def decode_namespace(segment):
    if segment=='_root': return ''
    if not segment.startswith('n-'): raise ValueError('Invalid checkpoint namespace segment')
    return base64.urlsafe_b64decode(segment[2:]+'='*(-len(segment[2:])%4)).decode()


class HttpSaver(BaseCheckpointSaver):
    def __init__(self,url,evaluation,session,token,ca_file=True,transport=None,allow_http=False):
        super().__init__(serde=SafeCodec())
        if not url.startswith('https://') and not (allow_http and url.startswith('http://')):
            raise ValueError('TLS required unless the operator enabled private HTTP')
        self.url=url.rstrip('/'); self.evaluation=evaluation; self.session=session; self.token=token
        self.transport=transport
        self.client=None if transport else httpx.AsyncClient(verify=ca_file,timeout=30,trust_env=False)

    def path(self,config):
        state=config['configurable']; thread=state['thread_id']
        namespace=namespace_segment(state.get('checkpoint_ns',''))
        return '/substrate/v1/evaluations/'+quote(self.evaluation,safe='')+'/checkpoints/'+quote(thread,safe='')+'/'+namespace

    async def request(self,method,path,payload=None,missing=False):
        headers={'Authorization':'Bearer '+self.token}
        if method in ('PUT','DELETE'): headers['Idempotency-Key']=new_id()
        if self.transport:
            response=await asyncio.to_thread(self.transport.request,method,path,json=payload,headers=headers)
        else:
            response=await self.client.request(method,self.url+path,json=payload,headers=headers)
        if missing and response.status_code==404: return None
        response.raise_for_status()
        return response.json()

    def tuple(self,config,body):
        state=dict(config['configurable'],checkpoint_id=body['checkpoint_id'])
        header=body['metadata']['checkpoint_header']
        checkpoint=dict(header,id=body['checkpoint_id'],channel_values=self.serde.decode(body['channel_values']),
                        channel_versions=body['channel_versions'],versions_seen=body['versions_seen'])
        parent={'configurable':dict(state,checkpoint_id=body['parent_id'])} if body['parent_id'] else None
        return CheckpointTuple(config={'configurable':state},checkpoint=checkpoint,
                               metadata=body['metadata']['user_metadata'],parent_config=parent,
                               pending_writes=[(w['task_id'],w['channel'],self.serde.decode(w['value'])) for w in body['pending_writes']])

    async def aget_tuple(self,config):
        identity=config['configurable'].get('checkpoint_id')
        if identity:
            body=await self.request('GET',self.path(config)+'/'+quote(identity,safe=''),missing=True)
        else:
            page=await self.request('GET',self.path(config)+'?limit=1')
            body=page['items'][0] if page['items'] else None
        return self.tuple(config,body) if body else None

    async def alist(self,config,*,filter=None,before=None,limit=None):
        if config is None: raise ValueError('Explicit session-scoped thread configuration required')
        remaining=limit; cursor=before['configurable'].get('checkpoint_id') if before else None
        identity=config['configurable'].get('checkpoint_id')
        while remaining is None or remaining>0:
            params='?limit=100'+('&before='+quote(cursor,safe='') if cursor else '')
            page=await self.request('GET',self.path(config)+params)
            for body in page['items']:
                if identity and body['checkpoint_id']!=identity: continue
                metadata=body['metadata']['user_metadata']
                if filter and not all(metadata.get(k)==v for k,v in filter.items()): continue
                yield self.tuple(config,body)
                if remaining is not None:
                    remaining-=1
                    if remaining<=0: return
            cursor=page['next_cursor']
            if not cursor: return

    async def aput(self,config,checkpoint,metadata,new_versions):
        header={k:v for k,v in checkpoint.items() if k not in ('id','channel_values','channel_versions','versions_seen')}
        payload={'checkpoint_id':checkpoint['id'],'parent_id':config['configurable'].get('checkpoint_id'),
                 'channel_values':self.serde.encode(checkpoint['channel_values']),
                 'channel_versions':checkpoint['channel_versions'],'versions_seen':checkpoint['versions_seen'],
                 'metadata':{'checkpoint_header':header,'user_metadata':get_checkpoint_metadata(config,metadata)},
                 'pending_writes':[],'codec_version':self.serde.version}
        await self.request('PUT',self.path(config)+'/'+quote(checkpoint['id'],safe=''),payload)
        return {'configurable':dict(config['configurable'],checkpoint_id=checkpoint['id'])}

    async def aput_writes(self,config,writes,task_id,task_path=''):
        payload={'task_id':task_id,'task_path':task_path or '_root',
                 'writes':[{'write_index':WRITES_IDX_MAP.get(channel,index),'channel':channel,'value':self.serde.encode(value)} for index,(channel,value) in enumerate(writes)]}
        await self.request('PUT',self.path(config)+'/'+quote(config['configurable']['checkpoint_id'],safe='')+'/writes',payload)

    async def adelete_thread(self,thread_id):
        config={'configurable':{'thread_id':thread_id,'checkpoint_ns':''}}
        await self.request('DELETE',self.path(config)+'?all_namespaces=true')

    async def aclose(self):
        if self.client: await self.client.aclose()

    def get_next_version(self,current,channel):
        return (int(current) if current is not None else 0)+1
