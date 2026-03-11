"""add environments and flag_environments tables

Revision ID: c3d4e5f6a7b8
Revises: b7c2a1d3e4f5
Create Date: 2026-03-11 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str]] = "b7c2a1d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create environments table
    op.create_table(
        "environments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name", name="uq_environments_project_name"),
    )

    # 2. Create flag_environments table
    op.create_table(
        "flag_environments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("flag_id", sa.Uuid(), nullable=False),
        sa.Column("environment_id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("rollout_pct", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("default_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["flag_id"], ["flags.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["environment_id"], ["environments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("flag_id", "environment_id", name="uq_flag_env"),
        sa.CheckConstraint(
            "rollout_pct >= 0 AND rollout_pct <= 100",
            name="flag_environments_rollout_pct_range_check",
        ),
    )

    # 3. Data migration: create environments from existing flag data,
    #    then populate flag_environments and migrate rules
    conn = op.get_bind()

    # Get all distinct project_ids
    projects = conn.execute(sa.text("SELECT DISTINCT id FROM projects")).fetchall()

    for (project_id,) in projects:
        # Get distinct environments used by flags in this project
        envs = conn.execute(
            sa.text(
                "SELECT DISTINCT environment FROM flags WHERE project_id = :pid"
            ),
            {"pid": project_id},
        ).fetchall()

        env_names = {row[0] for row in envs}
        # Always ensure development and production exist
        env_names.add("development")
        env_names.add("production")

        for env_name in env_names:
            # Create environment row
            conn.execute(
                sa.text(
                    "INSERT INTO environments (id, project_id, name) "
                    "VALUES (gen_random_uuid(), :pid, :name)"
                ),
                {"pid": project_id, "name": env_name},
            )

    # Now create flag_environments from existing flags
    # For each flag, find or create a matching environment and create a flag_environment
    flags = conn.execute(
        sa.text(
            "SELECT id, project_id, environment, enabled, rollout_pct, default_value FROM flags"
        )
    ).fetchall()

    for flag_id, project_id, env_name, enabled, rollout_pct, default_value in flags:
        env_row = conn.execute(
            sa.text(
                "SELECT id FROM environments WHERE project_id = :pid AND name = :name"
            ),
            {"pid": project_id, "name": env_name},
        ).fetchone()

        if env_row:
            conn.execute(
                sa.text(
                    "INSERT INTO flag_environments (id, flag_id, environment_id, enabled, rollout_pct, default_value) "
                    "VALUES (gen_random_uuid(), :fid, :eid, :enabled, :rollout, :default_val)"
                ),
                {
                    "fid": flag_id,
                    "eid": env_row[0],
                    "enabled": enabled,
                    "rollout": rollout_pct,
                    "default_val": default_value,
                },
            )

    # Migrate rules: update flag_id -> flag_environment_id
    # Add the new column first
    op.add_column("rules", sa.Column("flag_environment_id", sa.Uuid(), nullable=True))

    # Populate flag_environment_id from existing flag_id
    conn.execute(
        sa.text(
            "UPDATE rules SET flag_environment_id = fe.id "
            "FROM flag_environments fe WHERE fe.flag_id = rules.flag_id"
        )
    )

    # Drop old FK and column, make new column non-nullable
    # Use raw SQL to drop constraints — op.drop_constraint() mangles names through naming conventions
    rules_fk_name = conn.execute(
        sa.text(
            "SELECT conname FROM pg_constraint "
            "WHERE conrelid = 'rules'::regclass "
            "AND contype = 'f' "
            "AND confrelid = 'flags'::regclass"
        )
    ).scalar()
    if rules_fk_name:
        conn.execute(sa.text(f'ALTER TABLE rules DROP CONSTRAINT "{rules_fk_name}"'))
    op.drop_column("rules", "flag_id")
    op.alter_column("rules", "flag_environment_id", nullable=False)
    op.create_foreign_key(
        "rules_flag_environment_id_fkey",
        "rules",
        "flag_environments",
        ["flag_environment_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Now handle duplicate flag keys within the same project (from different environments).
    # We need to merge them: keep one flag row per (project_id, key), delete duplicates.
    # The flag_environments already point to the correct environment.
    # We need to re-point flag_environments from duplicate flag rows to the "keeper" flag row.

    # Find groups of flags with the same (project_id, key)
    dupes = conn.execute(
        sa.text(
            "SELECT project_id, key, array_agg(id ORDER BY created_at) as flag_ids "
            "FROM flags "
            "GROUP BY project_id, key "
            "HAVING count(*) > 1"
        )
    ).fetchall()

    for project_id, key, flag_ids in dupes:
        keeper_id = flag_ids[0]  # Keep the oldest one
        for dup_id in flag_ids[1:]:
            # Re-point flag_environments to keeper
            conn.execute(
                sa.text(
                    "UPDATE flag_environments SET flag_id = :keeper WHERE flag_id = :dup"
                ),
                {"keeper": keeper_id, "dup": dup_id},
            )
            # Re-point audit_logs to keeper
            conn.execute(
                sa.text(
                    "UPDATE audit_logs SET flag_id = :keeper WHERE flag_id = :dup"
                ),
                {"keeper": keeper_id, "dup": dup_id},
            )
            # Delete the duplicate flag
            conn.execute(
                sa.text("DELETE FROM flags WHERE id = :dup"),
                {"dup": dup_id},
            )

    # Remove old columns from flags
    # Use raw SQL to drop constraints — op.drop_constraint() mangles names through naming conventions
    flags_uq_name = conn.execute(
        sa.text(
            "SELECT conname FROM pg_constraint "
            "WHERE conrelid = 'flags'::regclass "
            "AND contype = 'u'"
        )
    ).scalar()
    if flags_uq_name:
        conn.execute(sa.text(f'ALTER TABLE flags DROP CONSTRAINT "{flags_uq_name}"'))

    flags_check_name = conn.execute(
        sa.text(
            "SELECT conname FROM pg_constraint "
            "WHERE conrelid = 'flags'::regclass "
            "AND contype = 'c'"
        )
    ).scalar()
    if flags_check_name:
        conn.execute(sa.text(f'ALTER TABLE flags DROP CONSTRAINT "{flags_check_name}"'))
    op.drop_column("flags", "environment")
    op.drop_column("flags", "enabled")
    op.drop_column("flags", "rollout_pct")
    op.drop_column("flags", "default_value")

    # Add new unique constraint
    op.create_unique_constraint("uq_flags_project_key", "flags", ["project_id", "key"])

    # For any project that has flags but environments that don't have flag_environments,
    # create them (e.g. a flag existed only in "production" but we also created "development")
    conn.execute(
        sa.text(
            "INSERT INTO flag_environments (id, flag_id, environment_id, enabled, rollout_pct) "
            "SELECT gen_random_uuid(), f.id, e.id, false, 0 "
            "FROM flags f "
            "CROSS JOIN environments e "
            "WHERE e.project_id = f.project_id "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM flag_environments fe "
            "  WHERE fe.flag_id = f.id AND fe.environment_id = e.id"
            ")"
        )
    )


def downgrade() -> None:
    # Add back old columns to flags
    op.add_column("flags", sa.Column("environment", sa.String(50), nullable=True))
    op.add_column("flags", sa.Column("enabled", sa.Boolean(), nullable=True, server_default=sa.text("false")))
    op.add_column("flags", sa.Column("rollout_pct", sa.Integer(), nullable=True, server_default=sa.text("0")))
    op.add_column("flags", sa.Column("default_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # Restore rules.flag_id from flag_environment_id
    op.add_column("rules", sa.Column("flag_id", sa.Uuid(), nullable=True))

    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE rules SET flag_id = fe.flag_id "
            "FROM flag_environments fe WHERE fe.id = rules.flag_environment_id"
        )
    )

    op.drop_constraint("rules_flag_environment_id_fkey", "rules", type_="foreignkey")
    op.drop_column("rules", "flag_environment_id")
    op.alter_column("rules", "flag_id", nullable=False)
    op.create_foreign_key(
        "rules_flag_id_fkey", "rules", "flags", ["flag_id"], ["id"], ondelete="CASCADE"
    )

    # Note: full downgrade (splitting merged flags back) is not feasible.
    # Set environment to 'production' as default for all flags.
    conn.execute(sa.text("UPDATE flags SET environment = 'production'"))
    op.alter_column("flags", "environment", nullable=False)
    op.alter_column("flags", "enabled", nullable=False)
    op.alter_column("flags", "rollout_pct", nullable=False)

    op.drop_constraint("uq_flags_project_key", "flags", type_="unique")
    op.create_unique_constraint("uq_flags_project_key_env", "flags", ["project_id", "key", "environment"])
    op.create_check_constraint("flags_rollout_pct_range_check", "flags", "rollout_pct >= 0 AND rollout_pct <= 100")

    op.drop_table("flag_environments")
    op.drop_table("environments")
