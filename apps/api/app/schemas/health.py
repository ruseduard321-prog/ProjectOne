"""Schemas for the health endpoint.

Every value crossing the API boundary is described by a schema, so the
response contract is explicit and validated rather than an ad-hoc dict
(CLAUDE.md 12, 14).
"""

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """The service's self-reported health."""

    status: Literal["ok"] = Field(
        description="Service status. Only 'ok' is returned; failure surfaces as a non-200 response."
    )
    service: str = Field(description="Human-readable service name.")
    version: str = Field(description="Application version.")
    environment: str = Field(description="Environment this instance is running in.")
