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

from app.db import async_session_factory  # noqa: E402
from app.main import app  # noqa: E402

TABLES = "delivery_attempts, deliveries, events, endpoints, tenants"


@pytest.fixture(scope="session")
def event_loop():
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def session_factory():
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
