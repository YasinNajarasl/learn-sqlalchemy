import logging
from typing import Generator, AsyncGenerator
from sqlalchemy.pool import QueuePool
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, create_engine, Session
from sqlmodel.ext.asyncio.session import AsyncSession

# Enable SQL debug logging during development
logging.basicConfig(level=logging.INFO)

DATABASE_URL = "sqlite:///./blog.db"
ASYNC_DATABASE_URL = "sqlite+aiosqlite:///./blog.db"

# Synchronous engine with QueuePool for concurrent web requests
engine = create_engine(
    DATABASE_URL,
    echo=True,
    connect_args={"check_same_thread": False},
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
)

# Asynchronous engine for non-blocking FastAPI routes
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    future=True,
)


def init_db() -> None:
    """Create all tables defined in SQLModel metadata."""
    from models import User, Post  # noqa: F401
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Dependency providing a scoped synchronous database session."""
    with Session(engine) as session:
        yield session


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency providing a scoped asynchronous database session."""
    async with AsyncSession(async_engine) as session:
        yield session