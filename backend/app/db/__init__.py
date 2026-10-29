from collections.abc import Generator
from urllib.parse import quote, unquote

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


def normalize_database_url(database_url: str) -> str:
    """Select psycopg 3 and safely encode a raw password for SQLAlchemy."""
    if database_url.startswith("postgres://"):
        database_url = f"postgresql://{database_url[len('postgres://'):]}"

    if database_url.startswith("postgresql://"):
        database_url = f"postgresql+psycopg://{database_url[len('postgresql://'):]}"

    if "://" not in database_url or "@" not in database_url:
        return database_url

    scheme, remainder = database_url.split("://", 1)
    userinfo, host_and_options = remainder.rsplit("@", 1)
    if ":" not in userinfo:
        return database_url
    username, password = userinfo.split(":", 1)
    encoded_password = quote(unquote(password), safe="")
    return f"{scheme}://{username}:{encoded_password}@{host_and_options}"


DATABASE_URL = normalize_database_url(settings.database_url)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
