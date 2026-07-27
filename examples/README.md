# Example: Flaky Receiver — Idempotent Consumer Demo

This standalone FastAPI app proves the core thesis of the project:

> **at-least-once delivery + idempotent consumer = effectively-once processing**

## How it works

1. **Verify signature** — rejects forged requests at the door
2. **Simulate failures** — 30% of requests return 500 (configurable via `FLAKY_RATE`)
3. **Dedup on event ID** — duplicate deliveries become no-ops
4. **Track stats** — `/stats` shows processed vs duplicates vs failures

## Running the demo

```bash
# 1. Start the stack
docker compose up --build -d

# 2. Create a tenant
export API_KEY=$(curl -s -X POST localhost:8000/tenants \
  -H 'Content-Type: application/json' \
  -d '{"name": "demo"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['api_key'])")

# 3. Register endpoint pointing at the receiver
export ENDPOINT_DATA=$(curl -s -X POST localhost:8000/endpoints \
  -H "Authorization: Bearer $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"url": "http://receiver:9000/webhook"}')
export ENDPOINT_ID=$(echo $ENDPOINT_DATA | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
export WEBHOOK_SECRET=$(echo $ENDPOINT_DATA | python3 -c "import sys,json; print(json.load(sys.stdin)['secret'])")

# 4. Restart receiver with the correct secret
RECEIVER_SECRET=$WEBHOOK_SECRET docker compose up -d receiver

# 5. Fire 50 events
for i in $(seq 1 50); do
  curl -s -X POST localhost:8000/events \
    -H "Authorization: Bearer $API_KEY" \
    -H "Idempotency-Key: $(uuidgen)" \
    -H 'Content-Type: application/json' \
    -d "{\"endpoint_id\": \"$ENDPOINT_ID\", \"event_type\": \"demo.fired\", \"payload\": {\"n\": $i}}" > /dev/null
done

# 6. Wait for delivery, then check
sleep 30
curl -s localhost:9000/stats | python3 -m json.tool
curl -s localhost:8000/metrics | python3 -m json.tool
```

## Expected result

With `FLAKY_RATE=0.3` and 50 events:

- `processed: 50` — every event processed exactly once at the business level
- `duplicates_ignored: ≥0` — proof that retries happened and dedup absorbed them
- `simulated_failures: ≥0` — proof the receiver was genuinely unreliable
- Platform `/metrics` shows retry attempts > 50 — the delivery system retried failures

**This is the effectively-once equation in action.**
