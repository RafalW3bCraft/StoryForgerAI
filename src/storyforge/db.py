"""SQLAlchemy connection lifecycle; one SQLite database for the one-process MVP."""

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .models import Base


def make_engine(url: str):
    kwargs: dict[str, object] = {"connect_args": {"check_same_thread": False}}
    if url.endswith(":memory:"):
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
