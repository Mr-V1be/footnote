from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    """Response and request bodies use camelCase on the wire."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, frozen=True)


class Problem(ApiModel):
    """RFC 9457 problem details with a stable machine-readable ``code``."""

    type: str = "about:blank"
    title: str
    status: int
    code: str
    detail: str | None = None
