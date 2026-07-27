import uuid

from httpx import AsyncClient
from sqlalchemy import text

from app.db import async_session_factory


async def test_first_post_202(
    client: AsyncClient, auth_headers: dict, endpoint_id: str
) -> None:
    resp = await client.post(
        "/events",
        json={"endpoint_id": endpoint_id, "event_type": "test", "payload": {"k": "v"}},
        headers={**auth_headers, "Idempotency-Key": "key-1"},
    )
    assert resp.status_code == 202
    assert resp.json()["replayed"] is False


async def test_duplicate_returns_200_replayed(
    client: AsyncClient, auth_headers: dict, endpoint_id: str
) -> None:
    h = {**auth_headers, "Idempotency-Key": "dup-key"}
    body = {"endpoint_id": endpoint_id, "event_type": "test", "payload": {"k": "v"}}
    r1 = await client.post("/events", json=body, headers=h)
    r2 = await client.post("/events", json=body, headers=h)
    assert r1.status_code == 202
    assert r2.status_code == 200
    assert r2.json()["replayed"] is True
    assert r1.json()["event_id"] == r2.json()["event_id"]
    async with async_session_factory() as s:
        count = (await s.execute(text("SELECT count(*) FROM events"))).scalar()
        assert count == 1


async def test_missing_idempotency_key_422(
    client: AsyncClient, auth_headers: dict, endpoint_id: str
) -> None:
    resp = await client.post(
        "/events",
        json={"endpoint_id": endpoint_id, "event_type": "test", "payload": {}},
        headers=auth_headers,
    )
    assert resp.status_code == 422


async def test_foreign_endpoint_404(client: AsyncClient) -> None:
    r1 = await client.post("/tenants", json={"name": "own"})
    r2 = await client.post("/tenants", json={"name": "other"})
    key_own = r1.json()["api_key"]
    key_other = r2.json()["api_key"]
    ep = await client.post(
        "/endpoints",
        json={"url": "https://own.com/wh"},
        headers={"Authorization": f"Bearer {key_own}"},
    )
    resp = await client.post(
        "/events",
        json={"endpoint_id": ep.json()["id"], "event_type": "x", "payload": {}},
        headers={
            "Authorization": f"Bearer {key_other}",
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 404
