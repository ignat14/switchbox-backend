from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.rule import RuleResponse


class FlagCreate(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=255)
    name: str = Field(max_length=255)
    flag_type: str = Field(default="boolean", pattern=r"^(boolean|string|number|json)$")
    environment: str = Field(pattern=r"^(dev|staging|production)$")
    default_value: Any = None


class FlagUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    rollout_pct: int | None = Field(default=None, ge=0, le=100)
    default_value: Any = None


class FlagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    key: str
    name: str
    flag_type: str
    enabled: bool
    rollout_pct: int
    environment: str
    default_value: Any
    created_at: datetime
    updated_at: datetime
    rules: list[RuleResponse] = []
