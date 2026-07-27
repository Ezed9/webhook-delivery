from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import generate_api_key, get_current_tenant
from app.db import get_session
from app.models import Tenant

router = APIRouter()


class TenantIn(BaseModel):
    name: str


@router.post("/tenants", status_code=201)
async def create_tenant(body: TenantIn, session: AsyncSession = Depends(get_session)) -> dict:
    plaintext, key_hash = generate_api_key()
    tenant = Tenant(name=body.name, api_key_hash=key_hash)
    session.add(tenant)
    await session.commit()
    return {"id": str(tenant.id), "name": tenant.name, "api_key": plaintext}


@router.get("/whoami")
async def whoami(tenant: Tenant = Depends(get_current_tenant)) -> dict:
    return {"tenant_id": str(tenant.id)}
