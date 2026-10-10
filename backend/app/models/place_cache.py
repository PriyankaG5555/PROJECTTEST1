from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PlaceCache(Base):
    """OpenStreetMap places per destination, refreshed after 7 days (fair use)."""

    __tablename__ = "place_cache"

    destination_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    places: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
