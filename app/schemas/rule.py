from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RuleCreate(BaseModel):
    attribute: str = Field(max_length=255)
    operator: str = Field(pattern=r"^(equals|not_equals|contains|ends_with|in_list|gt|lt)$")
    value: Any


class RuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    attribute: str
    operator: str
    value: Any
    created_at: datetime
