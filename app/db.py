from collections.abc import AsyncIterator
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine, AsyncEngine

from app.config import get_settings

_engine: Optional[AsyncEngine] = None
engine: Optional[AsyncEngine] = None
_session_maker: Optional[async_sessionmaker] = None


def _get_session_maker() -> async_sessionmaker:
    global _engine, engine, _session_maker
    if _session_maker is None:
        _engine = create_async_engine(get_settings().database_url)
        engine = _engine
        _session_maker = async_sessionmaker(_engine, expire_on_commit=False)
    return _session_maker

# Keep the same name/behavior tests currently use:
def async_session_factory() -> AsyncSession:
    # return an AsyncSession instance (call the maker)
    return _get_session_maker()()


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
