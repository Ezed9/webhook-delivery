import os
import subprocess
import sys
from collections.abc import AsyncIterator

import asyncpg
import pytest

TEST_DB = "webhook_test"
_HOST = os.environ.get("PGHOST", "localhost")
_PORT = os.environ.get("PGPORT", "5432")
_ADMIN_URL = f"postgresql://postgres:postgres@{_HOST}:{_PORT}/postgres"
TEST_DATABASE_URL = f"postgresql+asyncpg://postgres:postgres@{_HOST}:{_PORT}/{TEST_DB}"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from httpx import ASGITransport, AsyncClient  # noqa: E402

# Importing the async_session_factory is safe because app.db lazily initializes
# the engine/sessionmaker only when a session is requested. Avoid importing
# app.main at module import time so FastAPI and any async startup code are
# created under pytest's event loop.
from app.db import async_session_factory  # noqa: E402

TABLES = "delivery_attempts, deliveries, events, endpoints, tenants"


@pytest.fixture(scope="session")
def event_loop():
    import asyncio

    loop = asyncio.get_event_loop_policy().new_event_loop()
    # ensure this new loop is the current one so asyncio APIs and libraries
    # (asyncpg, SQLAlchemy async engine creation) bind futures/tasks to it.
    asyncio.set_event_loop(loop)
    try:
        yield loop
    finally:
        loop.close()
        asyncio.set_event_loop(None)


@pytest.fixture(scope="session", autouse=True)
def _test_database() -> None:
    import asyncio

    async def create() -> None:
        conn = await asyncpg.connect(_ADMIN_URL)
        await conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
        await conn.execute(f"CREATE DATABASE {TEST_DB}")
        await conn.close()

    asyncio.run(create())
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
    )


@pytest.fixture(scope="session", autouse=True)
async def _initialize_async_session_factory() -> None:
    # Call the session factory while the test event loop is current so the
    # engine/sessionmaker are created on the correct loop.
    session = async_session_factory()
    await session.close()


@pytest.fixture(autouse=True)
async def _clean_tables() -> AsyncIterator[None]:
    yield
    from sqlalchemy import text

    async with async_session_factory() as session:
        await session.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
        await session.commit()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    # import app lazily so FastAPI lifespan and any startup imports happen under test loop
    from app.main import app  # noqa: E402
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def session_factory():
    from app.db import async_session_factory

    return async_session_factory


@pytest.fixture
async def tenant_and_key(client: AsyncClient) -> tuple[str, str]:
    resp = await client.post("/tenants", json={"name": "testcorp"})
    data = resp.json()
    return data["id"], data["api_key"]


@pytest.fixture
async def auth_headers(tenant_and_key: tuple[str, str]) -> dict:
    _, api_key = tenant_and_key
    return {"Authorization": f"Bearer {api_key}"}


@pytest.fixture
async def endpoint_id(client: AsyncClient, auth_headers: dict) -> str:
    resp = await client.post(
        "/endpoints",
        json={"url": "https://example.com/webhook"},
        headers=auth_headers,
    )
    return resp.json()["id"]
