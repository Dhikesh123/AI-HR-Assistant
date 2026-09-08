"""Authentication service: registration, login and token issuance."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging_config import get_logger
from backend.core.security import create_access_token, hash_password, verify_password
from backend.models.user import User, UserRole

logger = get_logger(__name__)


class EmailAlreadyRegisteredError(ValueError):
    """Raised when the email is already present in the users table."""


class InvalidCredentialsError(ValueError):
    """Raised when login fails."""


def normalise_email(email: str) -> str:
    return (email or "").strip().lower()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == normalise_email(email)))


def register_user(
    db: Session,
    *,
    name: str,
    email: str,
    password: str,
    role: UserRole = UserRole.employee,
) -> User:
    """Create a new user with a hashed password."""
    email = normalise_email(email)
    if get_user_by_email(db, email):
        raise EmailAlreadyRegisteredError("An account with this email already exists")

    user = User(
        name=name.strip(),
        email=email,
        password_hash=hash_password(password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Registered new user id=%s role=%s", user.id, user.role.value)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    """Verify credentials and return the user, or raise on failure."""
    email = normalise_email(email)
    user = get_user_by_email(db, email)
    # Never log the email or password itself.
    if user is None or not verify_password(password, user.password_hash):
        logger.warning("Failed login attempt (email_known=%s)", user is not None)
        raise InvalidCredentialsError("Invalid email or password")
    logger.info("Successful login for user id=%s role=%s", user.id, user.role.value)
    return user


def issue_token(user: User) -> str:
    """Create a signed access token for a user."""
    return create_access_token(subject=str(user.id), role=user.role.value)
