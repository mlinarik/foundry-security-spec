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
