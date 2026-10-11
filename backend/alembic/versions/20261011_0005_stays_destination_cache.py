"""Stays (accommodation) and destination cache for telemetry (US-14, US-15)

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stays",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("trip_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("check_in_day", sa.SmallInteger(), nullable=False),
        sa.Column("check_out_day", sa.SmallInteger(), nullable=False),
        sa.Column("cost_per_night", sa.Numeric(12, 2), nullable=True),
        sa.Column("place_id", sa.String(100), nullable=True),
        sa.Column("kind", sa.String(20), nullable=True),
        sa.Column("stars", sa.SmallInteger(), nullable=True),
        sa.Column("address", sa.String(200), nullable=True),
        sa.Column("url", sa.String(300), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("check_out_day > check_in_day", name="ck_stays_nights_positive"),
        sa.CheckConstraint("check_in_day BETWEEN 1 AND 30", name="ck_stays_check_in_range"),
        sa.CheckConstraint("check_out_day BETWEEN 2 AND 31", name="ck_stays_check_out_range"),
        sa.CheckConstraint("cost_per_night >= 0", name="ck_stays_cost_not_negative"),
        sa.ForeignKeyConstraint(
            ["trip_id"], ["trips.id"], name="fk_stays_trip_id_trips", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_stays"),
    )
    op.create_index("ix_stays_trip_id", "stays", ["trip_id"])
    op.create_table(
        "destination_cache",
        sa.Column("destination_key", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("destination_key", name="pk_destination_cache"),
    )


def downgrade() -> None:
    op.drop_table("destination_cache")
    op.drop_index("ix_stays_trip_id", table_name="stays")
    op.drop_table("stays")
