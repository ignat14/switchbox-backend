"""add users table and project user_id fk

Revision ID: b7c2a1d3e4f5
Revises: 05a4b0e3d1ed
Create Date: 2026-03-11 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b7c2a1d3e4f5"
down_revision: Union[str, Sequence[str], None] = "05a4b0e3d1ed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("github_id", sa.Integer(), nullable=False),
        sa.Column("github_login", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("github_id"),
    )
    op.create_index("users_github_id_idx", "users", ["github_id"])
    op.add_column("projects", sa.Column("user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "projects_user_id_fkey", "projects", "users", ["user_id"], ["id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("projects_user_id_fkey", "projects", type_="foreignkey")
    op.drop_column("projects", "user_id")
    op.drop_index("users_github_id_idx", table_name="users")
    op.drop_table("users")
