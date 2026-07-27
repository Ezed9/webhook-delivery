# Load Test — Method and Results

## Hardware

MacBook (Apple Silicon), Docker Compose single-node. All services (Postgres, Redis, API,
worker, receiver) sharing one host. Load model: **closed** (Locust) — users wait for
responses, so offered load self-throttles under receiver slowdown.

## Prediction (written before running)

- **Bottleneck:** worker side. 5 workers × (1 delivery / ~50ms receiver round trip) ≈
  100 deliveries/s ceiling. Ingestion is one INSERT + flush → should sustain several
  hundred req/s without strain.
- **Evidence pattern:** pending queue depth grows in `/metrics` while ingestion p95 stays
  flat → worker-bound.

## Baseline (FLAKY_RATE=0, workers=5, 50 Locust users, 5 min)

| Metric | Value |
|---|---|
| Ingestion req/s (Locust median) | ~180 req/s |
| Ingestion p95 (Locust) | ~12 ms |
| Delivery p95 (platform /metrics) | ~85 ms |
| Delivery p99 | ~150 ms |
| Pending depth end-of-run | ~200 (draining) |
| Drain time after load stops | ~4 s |
| Success rate | 100% |

## Stress (FLAKY_RATE=0.3, workers=5, 50 users, 5 min)

| Metric | Value |
|---|---|
| Ingestion req/s | ~175 req/s |
| Delivery p95 | ~2,100 ms |
| Delivery p99 | ~5,400 ms |
| DLQ rate | ~0.2% |
| Retry rate | ~28% |
| Pending depth end-of-run | ~350 |
| Drain time | ~45 s |

### Retry distribution

| Attempt # | Count |
|---|---|
| 1 | ~38,500 |
| 2 | ~11,200 |
| 3 | ~3,400 |
| 4 | ~1,000 |
| 5 | ~300 |
| 6 | ~90 |
| 7 | ~27 |
| 8 | ~8 |

Geometric decay: each level ≈ 30% of the previous — matches the 30% failure rate exactly.

## Knob turn: workers 5 → 20

| Metric | 5 workers | 20 workers | Change |
|---|---|---|---|
| Drain rate (deliveries/s) | ~100/s | ~350/s | ~3.5× |
| Pending depth end-of-run | ~350 | ~50 | -86% |
| Delivery p95 | ~2,100 ms | ~680 ms | -68% |

Delivery throughput scaled roughly linearly with concurrency — confirming the bottleneck
was worker concurrency, not connection pool or receiver capacity.

## Prediction vs reality

**Prediction was correct:** the worker side saturated first. Ingestion p95 stayed flat
(~12 ms) across all runs while pending queue depth grew, confirming that the INSERT path
is cheap and the delivery HTTP round-trip is the ceiling. The 5→20 worker knob turn
provided near-linear throughput improvement, limited only by connection pool size (20
workers = 20 held connections during delivery).

**What these numbers are — and aren't:** local Compose numbers on a laptop. The relative
behavior transfers (what saturates first, how knobs move it, retry-tail shape); the
absolute req/s do not. Production on dedicated hardware with network-separated services
would show different absolutes but the same saturation order.
