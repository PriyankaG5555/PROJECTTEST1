from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuthAttempt(Base):
    """Per-IP counter for rate limiting auth endpoints (works across serverless instances)."""

    __tablename__ = "auth_attempts"

    ip: Mapped[str] = mapped_column(String(45), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
