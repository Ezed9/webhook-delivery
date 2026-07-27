import secrets

from fastapi import APIRouter, Depends
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_tenant
from app.db import get_session
from app.models import Endpoint, Tenant

router = APIRouter()


class EndpointIn(BaseModel):
    url: HttpUrl


@router.post("/endpoints", status_code=201)
async def register_endpoint(
    body: EndpointIn,
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
) -> dict:
    endpoint = Endpoint(
        tenant_id=tenant.id,
        url=str(body.url),
        secret=f"whsec_{secrets.token_urlsafe(32)}",
    )
    session.add(endpoint)
    await session.commit()
    return {"id": str(endpoint.id), "url": endpoint.url, "secret": endpoint.secret}


@router.get("/endpoints")
async def list_endpoints(
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = (
        await session.scalars(select(Endpoint).where(Endpoint.tenant_id == tenant.id))
    ).all()
    return [{"id": str(e.id), "url": e.url, "is_active": e.is_active} for e in rows]
