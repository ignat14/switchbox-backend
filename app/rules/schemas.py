from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


_OPERATOR_PATTERN = r"^(equals|not_equals|contains|ends_with|in_list|gt|lt)$"


class RuleCreate(BaseModel):
    attribute: str = Field(max_length=255)
    operator: str = Field(pattern=_OPERATOR_PATTERN)
    value: Any


class RuleUpdate(BaseModel):
    attribute: str | None = Field(default=None, max_length=255)
    operator: str | None = Field(default=None, pattern=_OPERATOR_PATTERN)
    value: Any = None


class RuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    attribute: str
    operator: str
    value: Any
    created_at: datetime
