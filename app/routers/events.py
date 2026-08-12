import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_tenant
from app.db import get_session
from app.models import Endpoint, Event, Tenant
from app.outbox import enqueue

router = APIRouter()


class EventIn(BaseModel):
    endpoint_id: uuid.UUID
    event_type: str
    payload: dict


@router.post("/events", status_code=202, response_model=None)
async def ingest_event(
    body: EventIn,
    idempotency_key: str = Header(...),
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
) -> dict | JSONResponse:
    tenant_id = tenant.id
    endpoint = await session.scalar(
        select(Endpoint).where(
            Endpoint.id == body.endpoint_id, Endpoint.tenant_id == tenant_id
        )
    )
    if endpoint is None:
        raise HTTPException(status_code=404, detail="endpoint not found")

    event = Event(
        tenant_id=tenant_id,
        endpoint_id=endpoint.id,
        event_type=body.event_type,
        payload=body.payload,
        idempotency_key=idempotency_key,
    )
    session.add(event)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        original = await session.scalar(
            select(Event).where(
                Event.tenant_id == tenant_id,
                Event.idempotency_key == idempotency_key,
            )
        )
        return JSONResponse(
            status_code=200,
            content={"event_id": str(original.id), "replayed": True},
        )

    await enqueue(session, event)
    await session.commit()
    return {"event_id": str(event.id), "replayed": False}
