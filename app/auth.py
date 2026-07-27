import hashlib
import secrets

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Tenant

_bearer = HTTPBearer(auto_error=False)


def generate_api_key() -> tuple[str, str]:
    plaintext = f"whsk_{secrets.token_urlsafe(32)}"
    return plaintext, hashlib.sha256(plaintext.encode()).hexdigest()


async def get_current_tenant(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> Tenant:
    if credentials is None:
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Bearer"})
    key_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()
    tenant = await session.scalar(select(Tenant).where(Tenant.api_key_hash == key_hash))
    if tenant is None:
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Bearer"})
    return tenant
