import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_tenant
from app.db import get_session
from app.models import Delivery, Event, Tenant

router = APIRouter()


@router.get("/deliveries")
async def list_deliveries(
    status: str | None = None,
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    stmt = (
        select(Delivery)
        .join(Event, Delivery.event_id == Event.id)
        .where(Event.tenant_id == tenant.id)
    )
    if status is not None:
        stmt = stmt.where(Delivery.status == status)
    rows = (await session.scalars(stmt)).all()
    return [
        {
            "id": str(d.id),
            "status": d.status,
            "attempt_count": d.attempt_count,
            "last_status_code": d.last_status_code,
            "last_error": d.last_error,
        }
        for d in rows
    ]


@router.post("/deliveries/{delivery_id}/retry")
async def retry_delivery(
    delivery_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
) -> dict:
    delivery = await session.scalar(
        select(Delivery)
        .join(Event, Delivery.event_id == Event.id)
        .where(Delivery.id == delivery_id, Event.tenant_id == tenant.id)
    )
    if delivery is None:
        raise HTTPException(status_code=404, detail="delivery not found")
    if delivery.status != "dead":
        raise HTTPException(status_code=409, detail="only dead deliveries can be retried")
    delivery.status = "pending"
    delivery.attempt_count = 0
    delivery.next_attempt_at = datetime.now(tz=UTC)
    await session.commit()
    return {"id": str(delivery.id), "status": "pending"}
