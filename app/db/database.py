"""
Async database connection manager using SQLAlchemy 2.0 + asyncpg.
"""
import os
import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


# Default to local dev postgres; overridden by DATABASE_URL env var
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://leads_user:leads_password_dev@localhost:5434/unicorn_brigade"
)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncSession:
    """Get an async database session."""
    async with async_session() as session:
        yield session


async def init_db():
    """Create all tables (skips existing ones)."""
    async with engine.begin() as conn:
        # checkfirst=True prevents errors when indexes/tables already exist
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, checkfirst=True))
    logger.info("Database tables created/verified")


async def close_db():
    """Close the database engine."""
    await engine.dispose()
    logger.info("Database engine closed")
