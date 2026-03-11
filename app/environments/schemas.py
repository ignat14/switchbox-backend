from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EnvironmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_-]*$")


class EnvironmentUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_-]*$")


class EnvironmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    created_at: datetime
