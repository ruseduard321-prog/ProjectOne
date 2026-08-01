"""Response contracts for workspace endpoints."""

from pydantic import BaseModel


class WorkspaceResponse(BaseModel):
    """A workspace the caller belongs to."""

    id: str
    name: str
    owner_id: str
