# webhook-delivery

A multi-tenant webhook delivery service — the infrastructure that sits between "an event
happened" and "the customer's server heard about it, reliably."

**Status: in active development (Jul 2026).** Architecture is locked; build is in progress
with daily commits. See the roadmap below for what's done vs. next.

## Why this exists

Delivering webhooks sounds trivial (just POST the payload) until receivers are slow, down,
or flaky. Then you need durable queueing, retries that don't DDoS the recovering receiver,
deduplication, authentication of the sender, and per-tenant isolation. This project builds
that infrastructure from first principles on PostgreSQL and Redis — no Kafka, no managed
queue — to show exactly where each guarantee comes from.

## Design

- **At-least-once delivery, by choice.** Exactly-once delivery over HTTP is not a real
  thing; the honest contract is at-least-once delivery + idempotent consumers
  (an example consumer proving this ships in `examples/`).
- **Transactional outbox.** The delivery job is written in the same PostgreSQL transaction
  as the event, so an accepted event can never be silently lost to the dual-write problem.
- **Postgres as the queue.** Workers claim jobs with
  `SELECT … FOR UPDATE SKIP LOCKED` — concurrent workers never grab the same row, and a
  crashed worker's claim rolls back automatically, requeueing the job.
- **HMAC-SHA256 signing.** Every delivery carries `X-Webhook-Signature` (over
  timestamp + body) so receivers can authenticate the sender and reject replays.
- **Exponential backoff with full jitter**, dead-letter state after max attempts, with a
  retry endpoint for operators.
- **Per-tenant token buckets in Redis** so one tenant's event storm can't starve everyone
  else's deliveries.
- **Idempotent ingestion.** `Idempotency-Key` header deduplicated by a database unique
  constraint, not an application-level check.

## Stack

Python 3.12 · FastAPI · PostgreSQL (SQLAlchemy 2.0 async + Alembic) · Redis · httpx ·
structlog · pytest · Locust · Docker Compose · GitHub Actions

## Roadmap

- [ ] Compose stack (Postgres, Redis, API, worker) with health-check driven startup + CI
- [ ] Multi-tenant auth (hashed API keys) + endpoint registration
- [ ] Event ingestion with Idempotency-Key dedup
- [ ] Transactional-outbox enqueueing
- [ ] Worker pool over `FOR UPDATE SKIP LOCKED`
- [ ] HMAC-SHA256 payload signing
- [ ] Backoff + jitter retries, dead-letter queue
- [ ] Per-tenant Redis token-bucket rate limiting
- [ ] Structured logging + `/metrics` (queue depth, retry/DLQ rates, delivery latency)
- [ ] Flaky-receiver demo proving idempotent consumption
- [ ] Locust load test with published numbers

## Deliberately out of scope

UI, Kafka/RabbitMQ, OAuth, payload transformation, exactly-once claims, Kubernetes.
Each exclusion is a decision, not an omission — rationale in `docs/architecture.md`
(coming with the build).
