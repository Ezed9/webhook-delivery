from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.logging import configure
from app.routers import deliveries, endpoints, events, metrics, tenants


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure(json_logs=True)
    yield


app = FastAPI(title="webhook-delivery", lifespan=lifespan)
app.include_router(tenants.router)
app.include_router(endpoints.router)
app.include_router(events.router)
app.include_router(deliveries.router)
app.include_router(metrics.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}