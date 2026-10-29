import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User, normalize_email


def get_user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    """Fetch user by primary key UUID."""
    return db.get(User, user_id)


def get_user_by_email(db: Session, email: str) -> User | None:
    """Fetch user by normalized email."""
    normalized = normalize_email(email)
    statement = select(User).where(User.email == normalized)
    return db.execute(statement).scalar_one_or_none()


def create_user(db: Session, email: str, hashed_password: str, role: str = "student") -> User:
    """Create and persist a new user."""
    user = User(
        email=normalize_email(email),
        hashed_password=hashed_password,
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
