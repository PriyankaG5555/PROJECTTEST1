"""Auth request/response bodies — api-contract-spec.md §5 (auth endpoints)."""

import re
from typing import Annotated

from pydantic import AfterValidator, Field

from app.schemas import UserOut
from app.schemas.base import ApiModel

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")


def _check_username(value: str) -> str:
    value = value.strip()
    if not _USERNAME_RE.fullmatch(value):
        raise ValueError("Username must be 3–30 letters, numbers or underscores.")
    return value


def _check_new_password(value: str) -> str:
    if not 8 <= len(value) <= 128:
        raise ValueError("Password must be 8–128 characters.")
    return value


Username = Annotated[str, AfterValidator(_check_username)]
NewPassword = Annotated[str, AfterValidator(_check_new_password)]
AnyPassword = Annotated[str, Field(min_length=1, max_length=128)]


class SignupIn(ApiModel):
    username: Username
    password: NewPassword


class LoginIn(ApiModel):
    username: Annotated[str, Field(min_length=1, max_length=30)]
    password: AnyPassword


class DeleteAccountIn(ApiModel):
    password: AnyPassword


class UserResponse(ApiModel):
    user: UserOut
