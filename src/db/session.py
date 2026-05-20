from sqlalchemy import text
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from typing import AsyncGenerator
from contextlib import asynccontextmanager
from src.settings import get_settings

settings = get_settings()

engine_kwargs = {"future": True, "echo": False}
if settings.database_url == "sqlite+aiosqlite:///:memory:":
    engine_kwargs["poolclass"] = StaticPool
    engine_kwargs["connect_args"] = {"check_same_thread": False}


engine = create_async_engine(settings.database_url, **engine_kwargs)


@event.listens_for(engine.sync_engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    if settings.database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


AsyncSessionLocal = async_sessionmaker(
    bind=engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


@asynccontextmanager
async def aget_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


def asession_factory(func):
    async def wrapper(*args, **kwargs):
        if kwargs.get('session') is None:
            async with aget_session() as session:
                kwargs['session'] = session
                return await func(*args, **kwargs)
        else:
            return await func(*args, **kwargs)
    return wrapper


async def aping_connection():
    try:
        async with engine.connect() as con:
            await con.execute(text('SELECT 1'))
            return True
    except SQLAlchemyError:
        return False
