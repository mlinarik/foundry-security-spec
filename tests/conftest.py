"""Live environments are opt-in, never accidentally used by structural tests."""
import pytest


def pytest_addoption(parser):
    parser.addoption("--live-cluster", action="store_true", help="Run authorized cluster tests")
    parser.addoption("--live-model", action="store_true", help="Run authorized model tests")


def pytest_collection_modifyitems(config, items):
    for item in items:
        for marker, option in [("live_cluster", "--live-cluster"), ("live_model", "--live-model")]:
            if marker in item.keywords and not config.getoption(option):
                item.add_marker(pytest.mark.skip(reason=f"Requires explicit {option}"))
