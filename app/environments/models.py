import secrets
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.base import Base


def generate_sdk_key() -> str:
    """Generate a fully random, opaque SDK key."""
    return secrets.token_urlsafe(32)


class Environment(Base):
    __tablename__ = "environments"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_environments_project_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    sdk_key: Mapped[str] = mapped_column(String(50), unique=True, default=generate_sdk_key)
    previous_sdk_key: Mapped[str | None] = mapped_column(String(50), nullable=True)
    previous_sdk_key_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
