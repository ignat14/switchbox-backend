from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EnvironmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class EnvironmentUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class EnvironmentReorder(BaseModel):
    environment_ids: list[UUID] = Field(min_length=1)


class EnvironmentConnectionResponse(BaseModel):
    status: Literal["connected", "stale", "never", "unknown"]
    last_seen_at: datetime | None = None


class EnvironmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    position: int
    sdk_key: str
    previous_sdk_key: str | None = None
    previous_sdk_key_expires_at: datetime | None = None
    created_at: datetime
