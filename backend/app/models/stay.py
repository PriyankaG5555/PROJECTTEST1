import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Numeric, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.trip import Trip


class Stay(UUIDPrimaryKey, Timestamps, Base):
    """Accommodation for a range of nights (accommodation-feature.md §2)."""

    __tablename__ = "stays"
    __table_args__ = (
        CheckConstraint("check_out_day > check_in_day", name="nights_positive"),
        CheckConstraint("check_in_day BETWEEN 1 AND 30", name="check_in_range"),
        CheckConstraint("check_out_day BETWEEN 2 AND 31", name="check_out_range"),
        CheckConstraint("cost_per_night >= 0", name="cost_not_negative"),
    )

    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    check_in_day: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    check_out_day: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    cost_per_night: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    place_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    kind: Mapped[str | None] = mapped_column(String(20), nullable=True)
    stars: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    address: Mapped[str | None] = mapped_column(String(200), nullable=True)
    url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)

    trip: Mapped["Trip"] = relationship(back_populates="stays")

    @property
    def nights(self) -> int:
        return self.check_out_day - self.check_in_day

    @property
    def total_cost(self) -> Decimal | None:
        return None if self.cost_per_night is None else self.cost_per_night * self.nights

    @property
    def verified(self) -> bool:
        return self.place_id is not None and self.lat is not None


class DestinationCache(Base):
    """Destination type and country from Nominatim, for telemetry (observability-spec.md §2.2)."""

    __tablename__ = "destination_cache"

    destination_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
