from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EnvironmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class EnvironmentUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class EnvironmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    sdk_key: str
    previous_sdk_key: str | None = None
    previous_sdk_key_expires_at: datetime | None = None
    created_at: datetime
