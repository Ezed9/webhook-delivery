import time

from redis.asyncio import Redis

_LUA = """
local capacity = tonumber(ARGV[1])
local refill = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local state = redis.call('HMGET', KEYS[1], 'tokens', 'ts')
local tokens = tonumber(state[1])
local ts = tonumber(state[2])
if tokens == nil then
  tokens = capacity
  ts = now
end

tokens = math.min(capacity, tokens + (now - ts) * refill)

local allowed = 0
if tokens >= 1 then
  tokens = tokens - 1
  allowed = 1
end

redis.call('HSET', KEYS[1], 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', KEYS[1], 3600)
return allowed
"""

_script = None


def _get_script(redis: Redis):
    global _script
    if _script is None:
        _script = redis.register_script(_LUA)
    return _script


async def acquire(
    redis: Redis, tenant_id: str, capacity: int = 10, refill_per_s: float = 5.0
) -> bool:
    result = await _get_script(redis)(
        keys=[f"rl:{tenant_id}"], args=[capacity, refill_per_s, time.time()]
    )
    return result == 1
