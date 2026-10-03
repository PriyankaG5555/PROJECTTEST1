"""Trip top priority + budget, suggestion usage; drop activity priority (US-7a/b/c)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

trip_priority = postgresql.ENUM("time", "destinations", "budget", name="trip_priority")
activity_priority = postgresql.ENUM("high", "medium", "low", name="priority")


def upgrade() -> None:
    trip_priority.create(op.get_bind(), checkfirst=True)
    op.add_column("trips", sa.Column("top_priority", trip_priority, nullable=True))
    op.add_column("trips", sa.Column("budget", sa.Numeric(12, 2), nullable=True))
    op.create_check_constraint("ck_trips_budget_not_negative", "trips", "budget >= 0")

    op.drop_column("activities", "priority")
    activity_priority.drop(op.get_bind(), checkfirst=True)

    op.create_table(
        "suggestion_usage",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_suggestion_usage_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "day", name="pk_suggestion_usage"),
    )


def downgrade() -> None:
    op.drop_table("suggestion_usage")
    activity_priority.create(op.get_bind(), checkfirst=True)
    op.add_column("activities", sa.Column("priority", activity_priority, nullable=True))
    op.drop_constraint("ck_trips_budget_not_negative", "trips", type_="check")
    op.drop_column("trips", "budget")
    op.drop_column("trips", "top_priority")
    trip_priority.drop(op.get_bind(), checkfirst=True)
