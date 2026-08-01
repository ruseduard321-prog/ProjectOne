"""Schemas for the health endpoint.

Every value crossing the API boundary is described by a schema, so the
response contract is explicit and validated rather than an ad-hoc dict
(CLAUDE.md 12, 14).
"""

from typing import Literal

from pydantic import BaseModel, Field


class DependencyStatus(BaseModel):
    """Health of a single dependency the service relies on."""

    name: str = Field(description="Dependency name, e.g. 'database'.")
    healthy: bool = Field(description="Whether the dependency answered successfully.")


class HealthResponse(BaseModel):
    """The service's self-reported health.

    `status` is `"ok"` only when every dependency is healthy. When one is not,
    the endpoint answers 503 with `status: "degraded"` and the failing
    dependency named — so an orchestrator can act on it and a human can see
    which one broke without reading logs.
    """

    status: Literal["ok", "degraded"] = Field(
        description=(
            "'ok' when every dependency is healthy, otherwise 'degraded', "
            "which is returned with HTTP 503."
        )
    )
    service: str = Field(description="Human-readable service name.")
    version: str = Field(description="Application version.")
    environment: str = Field(description="Environment this instance is running in.")
    dependencies: list[DependencyStatus] = Field(
        default_factory=list,
        description="Per-dependency health. Empty until dependencies exist.",
    )
