import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time

import pytest

from foundry_v2.api.auth import Forbidden
from foundry_v2.workers.heartbeat import HeartbeatSender
from foundry_v2.workers.runtime import Runtime, Origin


def test_heartbeat_has_independent_process_during_cpu_work():
    receipts=[]
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            receipts.append(time.monotonic())
            self.send_response(200); self.end_headers(); self.wfile.write(b'{}')
        def log_message(self,*args): pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    sender=HeartbeatSender(f'http://127.0.0.1:{server.server_port}','fixture','s',0,0.05,allow_http=True)
    try:
        sender.start()
        deadline=time.monotonic()+8
        while len(receipts)<2 and time.monotonic()<deadline: time.sleep(0.05)
        start=len(receipts); until=time.monotonic()+0.4
        while time.monotonic()<until:
            sum(i*i for i in range(50000))
        assert len(receipts)>=start+3
        assert sender.process.pid!=__import__('os').getpid()
    finally:
        sender.close(); server.shutdown(); server.server_close()


def test_target_and_peer_cannot_spawn_or_take_operator_authority():
    class Executor:
        async def call(self,*args): raise AssertionError('Unauthorized tool reached executor')
    async def scenario():
        worker=Runtime('detector','e','s',Executor(),None,None,None)
        for operation in ('spawn','steer','publication-intent','verdict'):
            with pytest.raises(Forbidden): await worker.tool(operation,{},Origin.TARGET)
        conversational=Runtime('orchestrator','e','s',Executor(),None,None,None)
        with pytest.raises(Forbidden): await conversational.tool('steer',{},Origin.PEER)
    asyncio.run(scenario())


def test_cancelled_graph_handoff_keeps_completed_checkpoint():
    from langgraph.graph import StateGraph,START,END
    from langgraph.checkpoint.memory import InMemorySaver
    async def scenario():
        reached=asyncio.Event(); saver=InMemorySaver()
        class Heartbeat:
            def start(self): pass
            def close(self): pass
        async def wait(state):
            reached.set(); await asyncio.Event().wait(); return state
        graph=StateGraph(dict); graph.add_node('first',lambda state:{'done':True}); graph.add_node('wait',wait)
        graph.add_edge(START,'first'); graph.add_edge('first','wait'); graph.add_edge('wait',END)
        runtime=Runtime('detector','e','s',None,graph.compile(checkpointer=saver),Heartbeat(),saver)
        task=asyncio.create_task(runtime.run({}))
        await asyncio.wait_for(reached.wait(),5)
        saved=await runtime.checkpoint_handoff()
        assert saved.checkpoint['channel_values']['__root__']['done'] is True
        with pytest.raises(asyncio.CancelledError): await task
    asyncio.run(scenario())
