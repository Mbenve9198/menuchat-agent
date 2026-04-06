import logging

from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.config import get_settings

logger = logging.getLogger("agent-service.db")

_pool: AsyncConnectionPool | None = None
_checkpointer: AsyncPostgresSaver | None = None


async def init_db():
    global _pool, _checkpointer
    settings = get_settings()
    _pool = AsyncConnectionPool(
        conninfo=settings.postgres_url,
        min_size=2,
        max_size=10,
        open=False,
        kwargs={"autocommit": True},
    )
    await _pool.open()
    _checkpointer = AsyncPostgresSaver(_pool)
    await _checkpointer.setup()


async def init_vector_store():
    """Initialize Qdrant collections for memory. Non-blocking on failure."""
    try:
        from app.memory.qdrant_store import init_collections
        await init_collections()
        logger.info("Qdrant vector store ready")
    except Exception as e:
        logger.warning("Qdrant init failed (memory disabled): %s", e)


async def close_db():
    global _pool, _checkpointer
    if _pool:
        await _pool.close()
    _pool = None
    _checkpointer = None

    try:
        from app.memory.qdrant_store import close_qdrant
        close_qdrant()
    except Exception:
        pass


def get_checkpointer() -> AsyncPostgresSaver:
    if _checkpointer is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _checkpointer
