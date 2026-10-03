import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPrimaryKey
from app.models.enums import TripStatus, TripType, trip_status_enum, trip_type_enum

if TYPE_CHECKING:
    from app.models.draft import Draft
    from app.models.user import User


class Trip(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "trips"
    __table_args__ = (CheckConstraint("end_date >= start_date", name="end_after_start"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    destination: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    trip_type: Mapped[TripType] = mapped_column(trip_type_enum, nullable=False)
    status: Mapped[TripStatus] = mapped_column(
        trip_status_enum, nullable=False, default=TripStatus.DRAFT, server_default="draft"
    )
    # Circular reference (drafts → trips → drafts): the FK is added after both tables exist.
    finalized_draft_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("drafts.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )

    user: Mapped["User"] = relationship(back_populates="trips")
    drafts: Mapped[list["Draft"]] = relationship(
        back_populates="trip",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="Draft.trip_id",
        order_by="Draft.created_at",
    )

    @property
    def day_count(self) -> int:
        return (self.end_date - self.start_date).days + 1
