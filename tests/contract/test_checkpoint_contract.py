import asyncio

import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from fastapi.testclient import TestClient

from foundry_v2.api.auth import OperatorAuth, Principal
from foundry_v2.checkpoints.codec import SafeCodec
from foundry_v2.checkpoints.http_saver import HttpSaver
from foundry_v2.substrate.app import create_app
from foundry_v2.substrate.owner import Owner
from foundry_v2.substrate.auth import SessionAuth


def test_codec_rejects_executable_formats_and_preserves_literal_tags():
    codec=SafeCodec()
    value={'literal':{'$type':'pickle','value':'ignored'},'bytes':b'abc','tuple':(1,2),'set':{3,4}}
    assert codec.loads_typed(codec.dumps_typed(value))==value
    with pytest.raises(ValueError):
        codec.loads_typed(('pickle',b'unsafe'))
    with pytest.raises(ValueError):
        codec.loads_typed(('foundry-json-v1',b'{"type":"object","module":"os","method":"system"}'))
    with pytest.raises(ValueError):
        codec.dumps_typed(object())


def test_remote_saver_matches_reference_resume_and_pending_writes(tmp_path):
    async def scenario():
        with Owner(tmp_path) as owner:
            evaluation=owner.reserve_evaluation(0)
            with owner.transaction() as db:
                db.execute('INSERT INTO sessions(session_id,evaluation_id,role,slot,incarnation,pod_name,state,heartbeat_at) VALUES(?,?,?,?,?,?,?,?)',
                           ('s',evaluation,'detector',0,0,'p','running',__import__('time').time()))
            SessionAuth(owner).issue(evaluation,'s','detector','w'*48,__import__('time').time()+3600)
            auth=OperatorAuth(lambda _: {},[],[],'foundry-v2')
            app=create_app(owner,auth,'i'*48)
            with TestClient(app,base_url='https://testserver') as client:
                remote=HttpSaver('https://testserver',evaluation,'s','w'*48,transport=client)
                for saver in (InMemorySaver(),remote):
                    graph=StateGraph(dict)
                    attempts=[0]
                    def second(state):
                        attempts[0]+=1
                        if attempts[0]==1: raise RuntimeError('fixture failure')
                        return state
                    graph.add_node('increment',lambda state:{'value':state.get('value',0)+1})
                    graph.add_node('retry',second)
                    graph.add_edge(START,'increment'); graph.add_edge('increment','retry'); graph.add_edge('retry',END)
                    compiled=graph.compile(checkpointer=saver)
                    config={'configurable':{'thread_id':'s:main','checkpoint_ns':''}}
                    with pytest.raises(RuntimeError): await compiled.ainvoke({'value':0},config)
                    assert await compiled.ainvoke(None,config)=={'value':1}
                    saved=await saver.aget_tuple(config)
                    assert saved.checkpoint['channel_values']['__root__']=={'value':1}
                    await saver.aput_writes(saved.config,[('channel',b'first')],'task')
                    await saver.aput_writes(saved.config,[('channel',b'second')],'task')
                    assert ('task','channel',b'first') in (await saver.aget_tuple(config)).pending_writes
                    rows=[row async for row in saver.alist(config)]
                    assert len(rows)>=3
                    nested={'configurable':{'thread_id':'s:main','checkpoint_ns':'author/child:_root'}}
                    await saver.aput(nested,saved.checkpoint,{'fixture':'nested'},saved.checkpoint['channel_versions'])
                    assert (await saver.aget_tuple(nested)).checkpoint==saved.checkpoint
                    assert len([row async for row in saver.alist(nested,filter={'fixture':'nested'})])==1
                    await saver.adelete_thread('s:main')
                    assert await saver.aget_tuple(nested) is None
                    assert await saver.aget_tuple(config) is None
                bad={'configurable':{'thread_id':'other:author','checkpoint_ns':''}}
                with pytest.raises(Exception):
                    await remote.aget_tuple(bad)
    asyncio.run(scenario())
