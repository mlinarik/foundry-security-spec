"""Shared preflight request shape; authorization lives at the HTTP boundary."""
from pydantic import BaseModel,ConfigDict


class PreflightRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    configuration: dict
