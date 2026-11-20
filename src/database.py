"""Database layer — engines, sessions, SQL logging and health helpers.

The code mirrors the presentation:

* Slide 8  — creating an ``Engine`` with ``echo`` and pooling options.
* Slide 13 — creating tables from model metadata.
* Slide 15 — ``Session`` / ``sessionmaker`` as a unit of work.
* Slide 35 — a native async engine and ``AsyncSession``.
* Slide 36 — connection-pool configuration.
"""

from __future__ import annotations

import logging
import os
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Generator

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import QueuePool
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "blog.db"

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")
ASYNC_DATABASE_URL = os.getenv(
    "ASYNC_DATABASE_URL", f"sqlite+aiosqlite:///{DEFAULT_DB_PATH}"
)
SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() in {"1", "true", "yes", "on"}

# Keep the console useful while learning, exactly like ``echo=True`` on slide 8.
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-5.5s [%(name)s] %(message)s",
)


class SQLBufferHandler(logging.Handler):
    """Capture SQLAlchemy's echoed SQL in a small in-memory ring buffer."""

    _SQL_KEYWORDS = {
        "SELECT",
        "INSERT",
        "UPDATE",
        "DELETE",
        "CREATE",
        "DROP",
        "ALTER",
        "BEGIN",
        "COMMIT",
        "ROLLBACK",
        "SAVEPOINT",
        "RELEASE",
        "PRAGMA",
        "WITH",
    }

    def __init__(self, capacity: int = 300) -> None:
        super().__init__(level=logging.INFO)
        self.buffer: deque[dict[str, str]] = deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
        try:
            message = record.getMessage().strip()
        except Exception:  # pragma: no cover - defensive
            return
        if not message:
            return
        first_word = message.split(None, 1)[0].upper()
        if first_word not in self._SQL_KEYWORDS:
            return
        self.buffer.append(
            {
                "time": datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
                "level": record.levelname,
                "sql": message,
            }
        )


SQL_LOG = SQLBufferHandler()
_sql_logger = logging.getLogger("sqlalchemy.engine.Engine")
if not any(isinstance(handler, SQLBufferHandler) for handler in _sql_logger.handlers):
    _sql_logger.addHandler(SQL_LOG)
_sql_logger.setLevel(logging.INFO)
# Keep the terminal quiet unless SQL_ECHO=true; the UI still gets every
# statement through SQL_LOG because the logger itself is at INFO.
_sql_logger.propagate = False


# Slide 37 — a tiny event feed used by the UI to show ORM listeners firing.
EVENT_LOG: deque[dict[str, str]] = deque(maxlen=200)


def record_event(name: str, detail: str) -> None:
    EVENT_LOG.appendleft(
        {
            "time": datetime.now().strftime("%H:%M:%S"),
            "event": name,
            "detail": detail,
        }
    )


def get_event_log(limit: int = 100) -> list[dict[str, str]]:
    return list(EVENT_LOG)[:limit]


def clear_event_log() -> None:
    EVENT_LOG.clear()


# Slide 8 + slide 36 — synchronous engine with a QueuePool.
engine = create_engine(
    DATABASE_URL,
    echo=SQL_ECHO,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
)

# Slide 35 — asynchronous engine for non-blocking FastAPI routes.
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    future=True,
)


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    """SQLite does not enforce foreign keys unless the pragma is enabled."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


if engine.dialect.name == "sqlite":
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    event.listen(async_engine.sync_engine, "connect", _enable_sqlite_foreign_keys)


# Used by the "lazy vs eager" demo on the Relationships page.
QUERY_COUNTER = {"count": 0}


@event.listens_for(Engine, "before_cursor_execute")
def _count_queries(_conn, _cursor, _statement, _parameters, _context, _executemany):
    QUERY_COUNTER["count"] += 1


def reset_query_counter() -> None:
    QUERY_COUNTER["count"] = 0


def get_query_count() -> int:
    return QUERY_COUNTER["count"]


def init_db() -> None:
    """Slide 13 — create every table registered in SQLModel metadata."""
    from . import models  # noqa: F401  (register tables)

    SQLModel.metadata.create_all(engine)


def reset_db() -> None:
    """Drop and recreate every table. Handy for the demo UI."""
    from . import models  # noqa: F401

    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Slide 15/41 — one short-lived Session per request."""
    with Session(engine) as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Slide 35 — async dependency with the same per-request lifetime."""
    async with AsyncSession(async_engine) as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


def get_sql_log(limit: int = 100) -> list[dict[str, str]]:
    return list(reversed(SQL_LOG.buffer))[:limit]


def clear_sql_log() -> None:
    SQL_LOG.buffer.clear()


def get_pool_status() -> dict[str, str]:
    """Slide 36 — expose the live connection-pool status."""
    return {
        "dialect": engine.dialect.name,
        "url": engine.url.render_as_string(hide_password=True),
        "pool": engine.pool.status(),
    }
