"""Scoped graph execution and explicit authority/tool boundaries."""
from dataclasses import dataclass, field
from enum import StrEnum
import asyncio

from foundry_v2.api.auth import Forbidden


class Origin(StrEnum):
    OPERATOR='operator'
    PEER='peer-advisory'
    TARGET='untrusted-target'


ROLE_TOOLS={
    'orchestrator':{'status','tasks','ask','steer'},
    'indexer':{'source','publish-index','index-query'},
    'cartographer':{'source','index-query','goals','publish-map'},
    'detector':{'source','index-query','map','rules','candidate','attempt','queue-task','scanner'},
    'triager':{'source','index-query','map','claimed-finding','evidence','verdict','queue-task'},
    'validator':{'claimed-finding','artifact','testbed','validation','queue-task'},
    'reporter':{'confirmed-reports','render-report','publication-intent','rollup'},
    'coverage-guide':{'goals','map','attempts','coverage','queue-task','edit-task'},
}


@dataclass
class Runtime:
    role: str
    evaluation: str
    session: str
    executor: object
    graph: object
    heartbeat: object
    saver: object
    cancelled: bool=False
    active: object=field(default=None,init=False,repr=False)

    async def tool(self,operation,arguments,origin=Origin.TARGET):
        if operation not in ROLE_TOOLS[self.role]:
            raise Forbidden('tool_not_allowed_for_role')
        # Target/peer text cannot acquire lifecycle or operator authority.
        if operation in ('steer','edit-task') and origin!=Origin.OPERATOR:
            if operation=='steer': raise Forbidden('operator_authority_required')
        return await self.executor.call(self.role,operation,arguments)

    async def run(self,initial,thread='main'):
        self.heartbeat.start()
        try:
            config={'configurable':{'thread_id':self.session+':'+thread,'checkpoint_ns':''}}
            if self.cancelled: return None
            self.active=asyncio.create_task(self.graph.ainvoke(initial,config))
            return await self.active
        finally:
            self.heartbeat.close()

    async def checkpoint_handoff(self,thread='main'):
        self.cancelled=True
        if self.active and not self.active.done():
            self.active.cancel()
            try:
                await self.active
            except asyncio.CancelledError:
                pass
        return await self.saver.aget_tuple({'configurable':{'thread_id':self.session+':'+thread,'checkpoint_ns':''}})

    async def close(self):
        self.heartbeat.close()
        await self.saver.aclose()
