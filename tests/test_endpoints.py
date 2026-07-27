from httpx import AsyncClient


async def test_register_endpoint(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.post(
        "/endpoints", json={"url": "https://example.com/wh"}, headers=auth_headers
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["secret"].startswith("whsec_")
    assert data["url"] == "https://example.com/wh"


async def test_list_hides_secret(client: AsyncClient, auth_headers: dict) -> None:
    await client.post(
        "/endpoints", json={"url": "https://example.com/wh"}, headers=auth_headers
    )
    resp = await client.get("/endpoints", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert "secret" not in items[0]


async def test_cross_tenant_404(client: AsyncClient) -> None:
    r1 = await client.post("/tenants", json={"name": "a"})
    r2 = await client.post("/tenants", json={"name": "b"})
    key_a = r1.json()["api_key"]
    key_b = r2.json()["api_key"]
    await client.post(
        "/endpoints",
        json={"url": "https://a.com/wh"},
        headers={"Authorization": f"Bearer {key_a}"},
    )
    resp = await client.get("/endpoints", headers={"Authorization": f"Bearer {key_b}"})
    assert resp.json() == []


async def test_invalid_url_422(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.post("/endpoints", json={"url": "not-a-url"}, headers=auth_headers)
    assert resp.status_code == 422
