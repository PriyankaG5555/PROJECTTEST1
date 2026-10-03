from enum import StrEnum

from sqlalchemy import Enum as SAEnum


class TripType(StrEnum):
    SOLO = "solo"
    COUPLE = "couple"
    FAMILY = "family"
    FRIENDS = "friends"


class TripStatus(StrEnum):
    DRAFT = "draft"
    FINALIZED = "finalized"


class TripPriority(StrEnum):
    TIME = "time"
    DESTINATIONS = "destinations"
    BUDGET = "budget"


def pg_enum(enum_cls: type[StrEnum], name: str) -> SAEnum:
    """PostgreSQL enum that stores the lower-case values ("solo"), not the member names."""
    return SAEnum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])


trip_type_enum = pg_enum(TripType, "trip_type")
trip_status_enum = pg_enum(TripStatus, "trip_status")
trip_priority_enum = pg_enum(TripPriority, "trip_priority")
