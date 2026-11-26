"""Ngân sách ngày/tháng theo API key, lưu bộ đếm chi phí trong Redis."""
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from redis.exceptions import RedisError

from app.config import settings
from app.redis_client import r

# Đơn giá minh hoạ của bài lab, USD / 1.000 token.
PRICE_INPUT_PER_1K = Decimal("0.00015")
PRICE_OUTPUT_PER_1K = Decimal("0.0006")
UNITS_PER_USD = 1_000_000_000
logger = logging.getLogger("production_agent")


def budget_scopes() -> list[tuple[str, str, float, int]]:
    now = datetime.now(timezone.utc)
    day_end = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    month_end = (now.replace(day=28) + timedelta(days=4)).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0,
    )
    identity = hashlib.sha256(settings.agent_api_key.encode()).hexdigest()
    scopes = [
        ("daily", f"day14:cost:{identity}:day:{now:%Y-%m-%d}",
         settings.daily_budget_usd, int(day_end.timestamp())),
    ]
    if settings.monthly_budget_usd is not None:
        scopes.append(
            ("monthly", f"day14:cost:{identity}:month:{now:%Y-%m}",
             settings.monthly_budget_usd, int(month_end.timestamp())),
        )
    return scopes


def get_usage() -> dict:
    scopes = budget_scopes()
    try:
        totals = r.mget([key for _, key, _, _ in scopes])
    except RedisError:
        logger.warning("redis_unavailable", extra={"component": "cost_guard"})
        raise HTTPException(status_code=503, detail="Redis is unavailable") from None
    result = {}
    for (period, _, limit, resets_at), total in zip(scopes, totals):
        used = int(total or 0) / UNITS_PER_USD
        result[period] = {
            "used_usd": used,
            "budget_usd": limit,
            "remaining_usd": max(0.0, round(limit - used, 9)),
            "resets_at": datetime.fromtimestamp(resets_at, timezone.utc).isoformat(),
        }
    return result


def check_budget() -> None:
    for period, usage in get_usage().items():
        if Decimal(str(usage["used_usd"])) >= Decimal(str(usage["budget_usd"])):
            raise HTTPException(
                status_code=402,
                detail={"error": "Budget exceeded", "period": period, **usage},
            )


def record_cost(input_tokens: int, output_tokens: int) -> float:
    # Dùng số nguyên nanodollar để tránh cộng dồn sai số số thực.
    cost = (
        Decimal(input_tokens) * PRICE_INPUT_PER_1K
        + Decimal(output_tokens) * PRICE_OUTPUT_PER_1K
    ) / 1000
    units = int(cost * UNITS_PER_USD)
    try:
        with r.pipeline(transaction=True) as pipe:
            for _, key, _, expiry in budget_scopes():
                pipe.incrby(key, units)
                pipe.expireat(key, expiry)
            pipe.execute()
    except RedisError:
        logger.warning("redis_unavailable", extra={"component": "cost_guard"})
        raise HTTPException(status_code=503, detail="Redis is unavailable") from None
    return float(cost)
