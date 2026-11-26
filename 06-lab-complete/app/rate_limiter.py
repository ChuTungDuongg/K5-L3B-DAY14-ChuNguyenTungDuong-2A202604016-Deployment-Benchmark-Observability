"""Sliding window 60 giây, dùng Redis để chia sẻ giữa mọi worker."""
import hashlib
import logging
import uuid

from fastapi import HTTPException
from redis.exceptions import RedisError

from app.config import settings
from app.redis_client import r

logger = logging.getLogger("production_agent")

# Kiểm tra và ghi request trong cùng script để tránh race giữa các worker.
SLIDING_WINDOW = """
local clock = redis.call('TIME')
local now = tonumber(clock[1]) * 1000 + math.floor(tonumber(clock[2]) / 1000)
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - window)
local count = redis.call('ZCARD', KEYS[1])
if count >= limit then
    local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    local retry = math.max(1, math.ceil((tonumber(oldest[2]) + window - now) / 1000))
    return {0, 0, retry}
end
redis.call('ZADD', KEYS[1], now, ARGV[3])
redis.call('PEXPIRE', KEYS[1], window)
return {1, limit - count - 1, 0}
"""


def check_rate_limit(key: str) -> dict:
    # Không đưa API key thô vào tên key Redis.
    identity = hashlib.sha256(key.encode()).hexdigest()
    try:
        allowed, remaining, retry_after = r.eval(
            SLIDING_WINDOW, 1, f"day14:rate:{identity}",
            60_000, settings.rate_limit_per_minute, uuid.uuid4().hex,
        )
    except RedisError:
        logger.warning("redis_unavailable", extra={"component": "rate_limiter"})
        raise HTTPException(status_code=503, detail="Redis is unavailable") from None
    headers = {
        "X-RateLimit-Limit": str(settings.rate_limit_per_minute),
        "X-RateLimit-Remaining": str(remaining),
    }
    if not allowed:
        headers["Retry-After"] = str(retry_after)
        raise HTTPException(status_code=429, detail="Rate limit exceeded", headers=headers)
    return headers
