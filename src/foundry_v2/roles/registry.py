"""Core role identities. Extensions are deliberately outside this registry."""
from enum import StrEnum


class Role(StrEnum):
    ORCHESTRATOR = "orchestrator"
    INDEXER = "indexer"
    CARTOGRAPHER = "cartographer"
    DETECTOR = "detector"
    TRIAGER = "triager"
    VALIDATOR = "validator"
    REPORTER = "reporter"
    COVERAGE_GUIDE = "coverage-guide"


class GraphRegistry:
    """Fixed core roles; each role receives its own injected step implementation."""
    def __init__(self,bindings):
        if set(bindings)!=set(Role):
            raise ValueError('Exactly all eight core role bindings are required')
        self.bindings={Role(role):step for role,step in bindings.items()}

    def compile(self,role,saver):
        from langgraph.graph import StateGraph, START, END
        role=Role(role)
        graph=StateGraph(dict)
        graph.add_node(role.value,self.bindings[role])
        graph.add_edge(START,role.value); graph.add_edge(role.value,END)
        return graph.compile(checkpointer=saver)
