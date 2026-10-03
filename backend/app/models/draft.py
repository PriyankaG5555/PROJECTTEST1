import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.activity import Activity
    from app.models.trip import Trip


class Draft(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "drafts"
    __table_args__ = (
        UniqueConstraint("trip_id", "name_normalized", name="uq_drafts_trip_id_name_normalized"),
    )

    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(50), nullable=False)

    trip: Mapped["Trip"] = relationship(back_populates="drafts", foreign_keys=[trip_id])
    activities: Mapped[list["Activity"]] = relationship(
        back_populates="draft", cascade="all, delete-orphan", passive_deletes=True
    )
