from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel as _to_camel


def to_camel(name: str) -> str:
    """snake_case -> camelCase (JSON field names in the API contract)."""
    return _to_camel(name)


class ApiModel(BaseModel):
    """Base for all request/response bodies: Python uses snake_case, JSON uses camelCase."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra="ignore",
    )
