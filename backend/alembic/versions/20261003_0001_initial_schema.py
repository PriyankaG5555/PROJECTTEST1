"""Initial schema: users, trips, drafts, activities, auth_attempts (backend-spec.md §3)

Revision ID: 0001
Revises:
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

trip_type = postgresql.ENUM("solo", "couple", "family", "friends", name="trip_type")
trip_status = postgresql.ENUM("draft", "finalized", name="trip_status")
priority = postgresql.ENUM("high", "medium", "low", name="priority")


def _uuid_pk() -> sa.Column[sa.Uuid]:
    return sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def _ts(name: str) -> sa.Column[sa.DateTime]:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def upgrade() -> None:
    op.create_table(
        "users",
        _uuid_pk(),
        sa.Column("username", sa.String(30), nullable=False),
        sa.Column("username_normalized", sa.String(30), nullable=False),
        sa.Column("password_hash", sa.String(100), nullable=False),
        _ts("created_at"),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("username_normalized", name="uq_users_username_normalized"),
    )

    op.create_table(
        "trips",
        _uuid_pk(),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("destination", sa.String(100), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("trip_type", trip_type, nullable=False),
        sa.Column("status", trip_status, server_default="draft", nullable=False),
        sa.Column("finalized_draft_id", sa.UUID(), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.CheckConstraint("end_date >= start_date", name="ck_trips_end_after_start"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_trips_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_trips"),
    )
    op.create_index("ix_trips_user_id", "trips", ["user_id"])

    op.create_table(
        "drafts",
        _uuid_pk(),
        sa.Column("trip_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("name_normalized", sa.String(50), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(
            ["trip_id"], ["trips.id"], name="fk_drafts_trip_id_trips", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_drafts"),
        sa.UniqueConstraint("trip_id", "name_normalized", name="uq_drafts_trip_id_name_normalized"),
    )
    op.create_index("ix_drafts_trip_id", "drafts", ["trip_id"])

    # Added after drafts exists: trips.finalized_draft_id -> drafts.id (circular reference).
    op.create_foreign_key(
        "fk_trips_finalized_draft_id_drafts",
        "trips",
        "drafts",
        ["finalized_draft_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "activities",
        _uuid_pk(),
        sa.Column("draft_id", sa.UUID(), nullable=False),
        sa.Column("day_number", sa.SmallInteger(), nullable=False),
        sa.Column("destination_name", sa.String(100), nullable=False),
        sa.Column("time", sa.CHAR(5), nullable=True),
        sa.Column("cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("priority", priority, nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.CheckConstraint("day_number BETWEEN 1 AND 30", name="ck_activities_day_number_range"),
        sa.CheckConstraint(
            "time ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'", name="ck_activities_time_format"
        ),
        sa.CheckConstraint("cost >= 0", name="ck_activities_cost_not_negative"),
        sa.ForeignKeyConstraint(
            ["draft_id"], ["drafts.id"], name="fk_activities_draft_id_drafts", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_activities"),
    )
    op.create_index("ix_activities_draft_id", "activities", ["draft_id"])
    op.create_index(
        "ix_activities_draft_day_time", "activities", ["draft_id", "day_number", "time"]
    )

    op.create_table(
        "auth_attempts",
        sa.Column("ip", sa.String(45), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("ip", "window_start", name="pk_auth_attempts"),
    )


def downgrade() -> None:
    op.drop_table("auth_attempts")
    op.drop_table("activities")
    op.drop_constraint("fk_trips_finalized_draft_id_drafts", "trips", type_="foreignkey")
    op.drop_table("drafts")
    op.drop_table("trips")
    op.drop_table("users")
    priority.drop(op.get_bind(), checkfirst=True)
    trip_status.drop(op.get_bind(), checkfirst=True)
    trip_type.drop(op.get_bind(), checkfirst=True)
