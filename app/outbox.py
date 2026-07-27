from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Delivery, Event


async def enqueue(session: AsyncSession, event: Event) -> Delivery:
    await session.flush()
    delivery = Delivery(event_id=event.id, endpoint_id=event.endpoint_id)
    session.add(delivery)
    return delivery
