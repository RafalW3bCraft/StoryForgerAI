"""SQLAlchemy connection lifecycle; one SQLite database for the one-process MVP."""

import os
import stat

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .models import Base


def secure_sqlite_file(database: str) -> None:
    """Create or restrict a file-backed SQLite database to its owner on POSIX."""
    if os.name == "nt" or not database or database == ":memory:":
        return

    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(database, flags, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("SQLite database path must be a regular file")
        os.fchmod(descriptor, 0o600)
    finally:
        os.close(descriptor)


def make_engine(url: str):
    kwargs: dict[str, object] = {"connect_args": {"check_same_thread": False}}
    parsed_url = make_url(url)
    if parsed_url.drivername.startswith("sqlite") and parsed_url.database:
        secure_sqlite_file(parsed_url.database)
    if parsed_url.database == ":memory:":
        kwargs["poolclass"] = StaticPool
    engine = create_engine(url, **kwargs)

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    Base.metadata.create_all(engine)
    # ``create_all`` does not alter existing SQLite tables.  Keep the one
    # migration needed by the voting-state invariant safe for the MVP's
    # existing databases, and always ensure the partial unique index exists.
    columns = {column["name"] for column in inspect(engine).get_columns("story_sessions")}
    if "paused_from_stage" not in columns:
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE story_sessions ADD COLUMN paused_from_stage VARCHAR(24)")
            )
    columns = {column["name"] for column in inspect(engine).get_columns("story_sessions")}
    if "generation_status" not in columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE story_sessions ADD COLUMN generation_status "
                    "VARCHAR(24) NOT NULL DEFAULT 'UNKNOWN'"
                )
            )
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_open_voting_round_per_session "
                "ON voting_rounds (session_id) WHERE status = 'OPEN'"
            )
        )
    return engine


def factory(engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
