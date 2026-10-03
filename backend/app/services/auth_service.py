"""Signup, login and account deletion (backend-spec.md §4)."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import User
from app.security import burn_password_check, hash_password, verify_password


def _invalid_credentials() -> AppError:
    return AppError("INVALID_CREDENTIALS", 401, "Incorrect username or password.")


def _normalize(username: str) -> str:
    return username.strip().lower()


def signup(db: Session, username: str, password: str) -> User:
    normalized = _normalize(username)
    taken = AppError("USERNAME_TAKEN", 409, "That username is already taken.")
    if db.scalar(select(User.id).where(User.username_normalized == normalized)):
        raise taken
    user = User(
        username=username.strip(),
        username_normalized=normalized,
        password_hash=hash_password(password),
    )
    db.add(user)
    try:
        db.flush()  # two signups racing for the same name: the unique constraint decides
    except IntegrityError:
        db.rollback()
        raise taken from None
    return user


def login(db: Session, username: str, password: str) -> User:
    user = db.scalar(select(User).where(User.username_normalized == _normalize(username)))
    if user is None:
        burn_password_check()
        raise _invalid_credentials()
    if not verify_password(password, user.password_hash):
        raise _invalid_credentials()
    return user


def delete_account(db: Session, user: User, password: str) -> None:
    if not verify_password(password, user.password_hash):
        raise AppError("INVALID_CREDENTIALS", 401, "That password is incorrect.")
    db.delete(user)  # trips, drafts and activities are removed by ON DELETE CASCADE
    db.flush()
