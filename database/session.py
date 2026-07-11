"""
Настройка async-движка SQLAlchemy и фабрика сессий.
"""
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config.settings import settings
from database.models import Base

# Убедимся, что папка data/ существует
_db_path = settings.database_url.replace("sqlite+aiosqlite:///", "")
if _db_path.startswith("."):
    Path(_db_path).parent.mkdir(parents=True, exist_ok=True)
else:
    Path(_db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Создание всех таблиц (если не существуют)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """Получить новую сессию БД."""
    async with async_session() as session:
        return session
