import os
import random

from fastapi import FastAPI, Request, Response

from app.signing import verify

app = FastAPI(title="example-receiver")

SECRET = os.environ["WEBHOOK_SECRET"]
FLAKY_RATE = float(os.environ.get("FLAKY_RATE", "0.3"))

processed: set[str] = set()
stats = {
    "processed": 0,
    "duplicates_ignored": 0,
    "rejected_bad_signature": 0,
    "simulated_failures": 0,
}


@app.post("/webhook")
async def webhook(request: Request) -> Response:
    body = await request.body()
    signature = request.headers.get("x-webhook-signature", "")
    timestamp = request.headers.get("x-webhook-timestamp", "")
    event_id = request.headers.get("x-webhook-event-id", "")

    if not verify(SECRET, timestamp, body, signature):
        stats["rejected_bad_signature"] += 1
        return Response(status_code=401)

    if random.random() < FLAKY_RATE:
        stats["simulated_failures"] += 1
        return Response(status_code=500)

    if event_id in processed:
        # idempotent consumer: duplicate delivery → no-op, tell platform OK
        stats["duplicates_ignored"] += 1
        return Response(status_code=200)

    # "process" the event (real consumers enqueue real work here)
    processed.add(event_id)  # only after successful processing
    stats["processed"] += 1
    return Response(status_code=200)


@app.get("/stats")
async def get_stats() -> dict:
    return stats
