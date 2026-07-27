from httpx import AsyncClient


async def test_health(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_create_tenant(client: AsyncClient) -> None:
    resp = await client.post("/tenants", json={"name": "acme"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "acme"
    assert data["api_key"].startswith("whsk_")
    assert "id" in data


async def test_whoami(client: AsyncClient, tenant_and_key: tuple[str, str]) -> None:
    tenant_id, api_key = tenant_and_key
    resp = await client.get("/whoami", headers={"Authorization": f"Bearer {api_key}"})
    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == tenant_id


async def test_wrong_key_401(client: AsyncClient) -> None:
    resp = await client.get("/whoami", headers={"Authorization": "Bearer whsk_invalid"})
    assert resp.status_code == 401


async def test_missing_auth_401(client: AsyncClient) -> None:
    resp = await client.get("/whoami")
    assert resp.status_code == 401


async def test_api_key_not_in_other_responses(
    client: AsyncClient, tenant_and_key: tuple[str, str]
) -> None:
    _, api_key = tenant_and_key
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = await client.get("/whoami", headers=headers)
    assert api_key not in resp.text