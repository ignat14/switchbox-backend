"""drop api_key_hash from projects

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-30 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("projects_api_key_hash_key", "projects", type_="unique")
    op.drop_column("projects", "api_key_hash")


def downgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("api_key_hash", sa.String(length=255), nullable=True),
    )
    op.create_unique_constraint(
        "projects_api_key_hash_key", "projects", ["api_key_hash"]
    )
