import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db import init_db, close_db
from app.api.routes import router

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("agent-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Agent Service — initializing databases")
    await init_db()
    logger.info("PostgreSQL checkpointer ready")
    yield
    logger.info("Shutting down Agent Service")
    await close_db()


app = FastAPI(
    title="MenuChat Agent Service",
    description="Compound AI System SOTA 2026 — SDR Sales Agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)
