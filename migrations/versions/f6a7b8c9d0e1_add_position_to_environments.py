"""add position to environments

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-04 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "environments",
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )

    # Backfill positions per project, ordered by creation time so existing
    # environments keep their current display order.
    conn = op.get_bind()
    projects = conn.execute(
        sa.text("SELECT DISTINCT project_id FROM environments")
    ).fetchall()
    for (project_id,) in projects:
        rows = conn.execute(
            sa.text(
                "SELECT id FROM environments WHERE project_id = :pid "
                "ORDER BY created_at"
            ),
            {"pid": project_id},
        ).fetchall()
        for position, (env_id,) in enumerate(rows):
            conn.execute(
                sa.text("UPDATE environments SET position = :pos WHERE id = :id"),
                {"pos": position, "id": env_id},
            )


def downgrade() -> None:
    op.drop_column("environments", "position")
