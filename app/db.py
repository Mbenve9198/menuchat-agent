from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.config import get_settings

_pool: AsyncConnectionPool | None = None
_checkpointer: AsyncPostgresSaver | None = None


async def init_db():
    global _pool, _checkpointer
    settings = get_settings()
    _pool = AsyncConnectionPool(conninfo=settings.postgres_url, min_size=2, max_size=10, open=False)
    await _pool.open()
    _checkpointer = AsyncPostgresSaver(_pool)
    await _checkpointer.setup()


async def close_db():
    global _pool, _checkpointer
    if _pool:
        await _pool.close()
    _pool = None
    _checkpointer = None


def get_checkpointer() -> AsyncPostgresSaver:
    if _checkpointer is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _checkpointer
