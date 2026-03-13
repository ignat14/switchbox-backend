"""add sdk_key to environments

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-13 12:00:00.000000

"""

from typing import Sequence, Union

import secrets

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _generate_sdk_key() -> str:
    return secrets.token_urlsafe(32)


def upgrade() -> None:
    # Add columns as nullable first
    op.add_column("environments", sa.Column("sdk_key", sa.String(50), nullable=True))
    op.add_column("environments", sa.Column("previous_sdk_key", sa.String(50), nullable=True))
    op.add_column(
        "environments",
        sa.Column("previous_sdk_key_expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Backfill existing rows with unique SDK keys
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id FROM environments")).fetchall()
    for row in rows:
        sdk_key = _generate_sdk_key()
        conn.execute(
            sa.text("UPDATE environments SET sdk_key = :sdk_key WHERE id = :id"),
            {"sdk_key": sdk_key, "id": row[0]},
        )

    # Now make sdk_key non-nullable and add unique constraints
    op.alter_column("environments", "sdk_key", nullable=False)
    op.create_unique_constraint("uq_environments_sdk_key", "environments", ["sdk_key"])


def downgrade() -> None:
    op.drop_constraint("uq_environments_sdk_key", "environments", type_="unique")
    op.drop_column("environments", "previous_sdk_key_expires_at")
    op.drop_column("environments", "previous_sdk_key")
    op.drop_column("environments", "sdk_key")
