"""OpenStreetMap place cache (ai-feature.md §5)

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "place_cache",
        sa.Column("destination_key", sa.String(100), nullable=False),
        sa.Column("places", postgresql.JSONB(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("destination_key", name="pk_place_cache"),
    )


def downgrade() -> None:
    op.drop_table("place_cache")
