import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def _resolve_database_url():
    raw = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if raw:
        if raw.startswith("postgres://"):
            return "postgresql+psycopg://" + raw[len("postgres://"):]
        if raw.startswith("postgresql://") and "+psycopg" not in raw:
            return "postgresql+psycopg://" + raw[len("postgresql://"):]
        return raw
    if os.getenv("VERCEL"):
        return "sqlite:////tmp/finance-platform.db"
    return "sqlite:///./finance-platform.db"


DATABASE_URL = _resolve_database_url()
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def sqlite_constraints(connection, record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()
