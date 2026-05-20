import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.routes.work import router as work_router
from src.db.models import Base
from src.db.session import engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Creating database tables if they do not exist")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Hitalent Departments API",
        version="0.1.0",
        description="Departments and employees test task API.",
        lifespan=lifespan,
    )
    app.include_router(work_router)
    return app
