"""HTTP lifecycle persistence adapter; the controller never opens SQLite."""
import json
from urllib.parse import quote

from foundry_v2.contracts.models import new_id


class LifecycleStore:
    def __init__(self,client): self.client=client

    def base(self,evaluation): return '/substrate/v1/evaluations/'+quote(evaluation,safe='')+'/lifecycle'

    async def call(self,method,path,payload=None):
        import asyncio
        return await asyncio.to_thread(self.client.request,method,path,payload=payload,key=new_id() if method!='GET' else None)

    async def snapshot(self,evaluation): return await self.call('GET',self.base(evaluation))
    async def preflight_result(self,evaluation,result): return await self.call('POST',self.base(evaluation)+'/preflight',result)
    async def state(self,evaluation,state): return await self.call('POST',self.base(evaluation)+'/state',{'state':state})
    async def degraded(self,evaluation,reason): return await self.call('POST',self.base(evaluation)+'/degraded',{'reason':reason})
    async def restart(self,evaluation): return await self.call('POST',self.base(evaluation)+'/restart',{})
    async def wrap_up(self,session): return await self.call('POST',self.base(session['evaluation_id'])+'/drain',{'session_id':session['session_id']})
    async def reserve(self,evaluation,role,slot,incarnation,restarts):
        return await self.call('POST',self.base(evaluation)+'/reserve',{'role':role,'slot':slot,'incarnation':incarnation,'restart_count':restarts})
