import asyncio

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from foundry_v2.roles.registry import GraphRegistry,Role
from foundry_v2.workers.transcripts import Redactor


def test_fixed_registry_keeps_eight_distinct_graph_bindings():
    async def scenario():
        bindings={}
        for role in Role:
            async def step(state,role=role): return {'role':role.value}
            bindings[role]=step
        registry=GraphRegistry(bindings)
        for role in Role:
            graph=registry.compile(role,InMemorySaver())
            assert await graph.ainvoke({}, {'configurable':{'thread_id':role.value}})=={'role':role.value}
        with pytest.raises(ValueError): GraphRegistry({})
    asyncio.run(scenario())


def test_transcripts_redact_secrets_without_changing_literal_authority():
    redactor=Redactor(['private-fixture'])
    data=redactor.redact({'origin':'peer-advisory','token':'secret','body':'private-fixture Bearer abc123 ghp_abc123',
                          'nested':[{'password':'sensitive'}]})
    assert data['origin']=='peer-advisory'
    assert data['token']=='[REDACTED]'
    assert 'private-fixture' not in data['body'] and 'abc123' not in data['body']
    assert data['nested'][0]['password']=='[REDACTED]'
