import uuid


from app.db import async_session_factory
from app.delivery import claim_stmt
from app.models import Delivery, Endpoint, Event, Tenant


async def _seed_pending(n: int = 10) -> None:
    async with async_session_factory() as s:
        t = Tenant(name="t", api_key_hash="h" + str(uuid.uuid4()))
        s.add(t)
        await s.flush()
        ep = Endpoint(tenant_id=t.id, url="https://x.com/wh", secret="s")
        s.add(ep)
        await s.flush()
        for _ in range(n):
            ev = Event(
                tenant_id=t.id, endpoint_id=ep.id, event_type="x",
                payload={}, idempotency_key=str(uuid.uuid4()),
            )
            s.add(ev)
            await s.flush()
            s.add(Delivery(event_id=ev.id, endpoint_id=ep.id))
        await s.commit()


async def test_concurrent_claims_are_disjoint(session_factory) -> None:
    await _seed_pending(10)
    async with session_factory() as s1, session_factory() as s2:
        async with s1.begin(), s2.begin():
            claimed1 = (await s1.scalars(claim_stmt(10))).all()
            claimed2 = (await s2.scalars(claim_stmt(10))).all()
            ids1 = {d.id for d in claimed1}
            ids2 = {d.id for d in claimed2}
            assert ids1.isdisjoint(ids2)
            assert len(ids1 | ids2) <= 10
            assert len(ids1) == 10 and len(ids2) == 0
