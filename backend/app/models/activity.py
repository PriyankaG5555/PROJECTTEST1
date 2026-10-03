import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CHAR, CheckConstraint, ForeignKey, Index, Numeric, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.draft import Draft


class Activity(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "activities"
    __table_args__ = (
        CheckConstraint("day_number BETWEEN 1 AND 30", name="day_number_range"),
        CheckConstraint("time ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'", name="time_format"),
        CheckConstraint("cost >= 0", name="cost_not_negative"),
        Index("ix_activities_draft_day_time", "draft_id", "day_number", "time"),
    )

    draft_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drafts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    day_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    destination_name: Mapped[str] = mapped_column(String(100), nullable=False)
    time: Mapped[str | None] = mapped_column(CHAR(5), nullable=True)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    draft: Mapped["Draft"] = relationship(back_populates="activities")
