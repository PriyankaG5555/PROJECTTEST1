from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAt, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.trip import Trip


class User(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(30), nullable=False)
    username_normalized: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(100), nullable=False)

    trips: Mapped[list["Trip"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
