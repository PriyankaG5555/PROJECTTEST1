"""Activity duration and AI day-planning tables (US-7d, F12)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("activities", sa.Column("duration_minutes", sa.SmallInteger(), nullable=True))
    op.create_check_constraint(
        "ck_activities_duration_range", "activities", "duration_minutes BETWEEN 1 AND 1440"
    )
    op.create_table(
        "ai_plan_usage",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_ai_plan_usage_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "day", name="pk_ai_plan_usage"),
    )
    op.create_table(
        "ai_plan_applications",
        sa.Column("proposal_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "applied_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_ai_plan_applications_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("proposal_id", name="pk_ai_plan_applications"),
    )


def downgrade() -> None:
    op.drop_table("ai_plan_applications")
    op.drop_table("ai_plan_usage")
    op.drop_constraint("ck_activities_duration_range", "activities", type_="check")
    op.drop_column("activities", "duration_minutes")
