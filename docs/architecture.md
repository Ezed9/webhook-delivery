# Architecture

## Overview

webhook-delivery is a multi-tenant webhook delivery platform built on PostgreSQL and Redis.
It accepts events via a REST API, enqueues them via a transactional outbox, and delivers
them reliably to registered receiver URLs with HMAC-SHA256 signing.

## Schema

```
tenants
├── id (uuid, PK)
├── name
├── api_key_hash (unique, indexed)
└── created_at

endpoints
├── id (uuid, PK)
├── tenant_id (FK → tenants, indexed)
├── url
├── secret (whsec_..., stored retrievably for HMAC)
├── is_active
└── created_at

events
├── id (uuid, PK)
├── tenant_id (FK → tenants, indexed)
├── endpoint_id (FK → endpoints)
├── event_type
├── payload (JSONB)
├── idempotency_key
├── created_at
└── UNIQUE(tenant_id, idempotency_key)

deliveries
├── id (uuid, PK)
├── event_id (FK → events)
├── endpoint_id (FK → endpoints)
├── status (pending | delivering | succeeded | dead)
├── attempt_count
├── next_attempt_at
├── last_status_code
├── last_error
├── created_at
├── updated_at
└── INDEX(status, next_attempt_at)  ← the claim index

delivery_attempts
├── id (bigint, PK)
├── delivery_id (FK → deliveries)
├── attempt_number
├── status_code
├── error
├── response_ms
└── created_at
```

## Failure Mode Table

| Crash point | What happens | Mechanism | Outcome |
|---|---|---|---|
| API crashes before COMMIT | Event + Delivery both vanish | Transaction rollback | Client retries (idempotency dedup handles it) |
| API crashes after COMMIT | Event + Delivery both persisted | Outbox atomicity | Worker will deliver. No loss. |
| Worker crashes mid-POST | Claiming transaction rolls back | FOR UPDATE lock release | Row returns to `pending`, another worker claims. At-least-once duplicate possible → consumer dedup. |
| Worker crashes after POST, before COMMIT | Same as above | Transaction rollback | Redelivery. Consumer sees duplicate. |
| Redis down | Token bucket `acquire` fails | Worker skips rate limiting or defers | Deliveries still happen (Postgres is the source of truth) |
| Receiver returns 500 | DeliveryAttempt recorded, backoff scheduled | Exponential backoff + jitter | Retries up to 8×, then dead-letter |
| Receiver times out (>10s) | Treated as failure | httpx timeout | Same backoff path as 500 |

## Design Decisions

### At-least-once, by choice

Exactly-once delivery over HTTP is impossible (Two Generals problem: the receiver's ACK
can always be lost). We deliberately promise at-least-once delivery with a stable
`X-Webhook-Event-Id` header. The consumer's dedup on that ID turns duplicates into no-ops:
**at-least-once delivery + idempotent consumer = effectively-once processing.**

### Transactional outbox, not dual-write

Writing the event to the DB and then pushing to a queue (or vice versa) is the dual-write
problem: a crash between the two writes either loses the job or creates a ghost delivery.
The outbox writes the delivery row in the same Postgres transaction as the event. One
COMMIT, both or neither. Deliveries can be duplicated (worker crash after POST) but never
lost.

### Postgres as the queue (hold-lock design)

Workers claim jobs with `SELECT ... FOR UPDATE SKIP LOCKED`. The claiming transaction
stays OPEN during the HTTP delivery. This gives crash safety for free: a dead worker's
connection drops → Postgres rolls back → the row returns to `pending` with no recovery
code.

**Trade-off:** each in-flight delivery holds one DB connection. Concurrency ceiling =
connection pool size. At 100× scale, switch to lease-based claiming (claim in a short
transaction with `lease_until = now() + 60s`, deliver without holding a connection, janitor
requeues expired leases). New failure mode: the janitor must distinguish "worker is slow"
from "worker is dead."

### Full jitter

`random.uniform(0, min(cap, base * 2^attempt))` — the entire delay is random. This
breaks retry synchronization (thundering herd) more effectively than equal jitter, with
fewer total calls (AWS Architecture Blog analysis).

### Token bucket, not fixed window

Per-tenant rate limiting at delivery time (not ingestion) so one tenant's event storm
can't starve other tenants. Token bucket allows legitimate bursts up to `capacity` while
maintaining sustained rate = `refill_per_s`. Implemented as an atomic Redis Lua script
to prevent check-and-decrement races between workers.

## Scaling to 100×

1. **Lease-based claiming** — free the connection pool ceiling (see trade-off above)
2. **Partition `deliveries`** by status or time — keep the hot `pending` set small
3. **Archive terminal rows** — move `succeeded`/`dead` to a cold table
4. **Shard Redis** — per-tenant-hash buckets across Redis instances
5. **Separate ingestion and delivery** — independently scaled services
