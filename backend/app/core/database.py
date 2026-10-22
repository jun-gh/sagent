import logging
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.core.config import get_settings

logger = logging.getLogger("sagent.database")
settings = get_settings()

# Engine creation
# Supports Neon Serverless PostgreSQL (asyncpg or psycopg3)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=(settings.LOG_LEVEL.upper() == "DEBUG"),
    future=True,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection yield for FastAPI request lifecycle."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> bool:
    """
    Initializes PostgreSQL extensions (pgvector) and creates tables if connected.
    Returns True on success, False if database is unavailable.
    """
    try:
        async with engine.begin() as conn:
            # Enable pgvector extension in PostgreSQL
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                logger.info("Verified pgvector extension exists.")
            except Exception as e:
                logger.warning("Could not execute CREATE EXTENSION vector (might be non-superuser or SQLite): %s", e)

            # Create tables
            await conn.run_sync(Base.metadata.create_all)

            # Ensure new columns exist on existing tables
            try:
                await conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS grounding_citations JSON;"))
                await conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS agent_steps JSON;"))
                await conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS session_id VARCHAR(64);"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tickets_session_id ON tickets (session_id);"))
            except Exception as col_err:
                logger.debug("Column alter check: %s", col_err)

            logger.info("Database tables initialized successfully.")
            return True
    except Exception as e:
        logger.error("Failed to connect to database at %s: %s", settings.DATABASE_URL, e)
        return False
