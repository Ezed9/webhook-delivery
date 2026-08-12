import pytest
from httpx import Response
from sqlalchemy.ext.asyncio import AsyncSession
from respx import MockRouter

from app.delivery import deliver_one
from app.models import Delivery

pytestmark = pytest.mark.asyncio

async def test_delivery_success(
    client, respx_mock: MockRouter, session_factory, endpoint_id
) -> None:
    respx_mock.post("https://example.com/webhook").mock(return_value=Response(200))
    async with session_factory() as session:
        # Assuming there is a delivery in DB from ingestion tests
        # or we just mock a delivery. We can test the failure/retry paths.
        pass
