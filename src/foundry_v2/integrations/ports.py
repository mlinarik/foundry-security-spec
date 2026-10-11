"""Explicit integration contracts; role graphs do not import deployment clients."""
from typing import Any, AsyncIterator, Protocol


class Provider(Protocol):
    async def chat(self, *, role: str, messages: list[dict], tools: list[dict], schema: dict | None=None) -> dict: ...


class Index(Protocol):
    async def query(self, evaluation: str, target: str, generation: str, operation: str, arguments: dict) -> dict: ...


class Substrate(Protocol):
    async def request(self, method: str, path: str, payload: dict | None=None, key: str | None=None) -> dict: ...


class Publisher(Protocol):
    async def reconcile(self, publication_id: str) -> dict: ...


class Deployment(Protocol):
    async def list_jobs(self, evaluation: str) -> list[dict]: ...
    async def create_job(self, session: dict) -> dict: ...
    async def stop_job(self, session: dict) -> None: ...


class Clock(Protocol):
    def utc(self) -> float: ...
    def monotonic(self) -> float: ...


class ToolExecutor(Protocol):
    """An infrastructure-isolated tool endpoint, never an in-process shell."""
    async def call(self, role: str, operation: str, arguments: dict) -> dict: ...
