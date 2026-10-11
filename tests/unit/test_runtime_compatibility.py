"""Exercise the interfaces used by the design, rather than imports alone."""
import subprocess
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient
from cvss import CVSS4
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from ollama import Client
from tree_sitter import Language, Parser
import tree_sitter_go
import tree_sitter_python
from foundry_v2.roles.registry import Role


def test_required_interpreter_and_role_identities():
    assert sys.version_info[:2] == (3, 12)
    assert len(Role) == 8
    result = subprocess.run([sys.executable, "-m", "foundry_v2.cli", "roles"], capture_output=True, text=True, check=True)
    assert set(result.stdout.splitlines()) == set(Role)


def test_fastapi_transport():
    app = FastAPI()
    @app.get("/health")
    def health():
        return {"ready": True}
    assert TestClient(app).get("/health").json() == {"ready": True}


def test_langgraph_checkpoint_roundtrip():
    graph = StateGraph(dict)
    graph.add_node("step", lambda state: {"completed": state.get("completed", 0) + 1})
    graph.add_edge(START, "step")
    graph.add_edge("step", END)
    saver = InMemorySaver()
    compiled = graph.compile(checkpointer=saver)
    config = {"configurable": {"thread_id": "compatibility-fixture"}}
    assert compiled.invoke({"completed": 0}, config) == {"completed": 1}
    assert saver.get_tuple(config).checkpoint["channel_values"]


def test_supported_source_grammars():
    for grammar, source in [(tree_sitter_python, b"def f():\n return 1\n"),
                             (tree_sitter_go, b"package fixture\nfunc f() int { return 1 }\n")]:
        tree = Parser(Language(grammar.language())).parse(source)
        assert not tree.root_node.has_error
        assert tree.root_node.children


def test_cvss4_zero_impact():
    vector = "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:N/SC:N/SI:N/SA:N"
    assert CVSS4(vector).scores()[0] == 0


def test_ollama_native_client_is_configurable_without_network():
    client = Client(host="http://127.0.0.1:11434")
    assert callable(client.chat)


def test_unimplemented_control_entrypoints_fail_closed():
    for service in ("orchestrator", "substrate", "workers"):
        result = subprocess.run([sys.executable, "-m", f"foundry_v2.{service}"], capture_output=True, text=True)
        assert result.returncode != 0
        assert "not implemented" in result.stderr
