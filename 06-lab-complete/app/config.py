"""Cấu hình từ environment; .env chỉ bổ sung biến chưa được đặt."""
import math
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv(override=False)


def optional_monthly_budget() -> float | None:
    value = os.getenv("MONTHLY_BUDGET_USD", "").strip()
    return float(value) if value else None


@dataclass(frozen=True)
class Settings:
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    agent_api_key: str = field(default_factory=lambda: os.getenv("AGENT_API_KEY", ""))
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))
    rate_limit_per_minute: int = field(default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MINUTE", "10")))
    daily_budget_usd: float = field(default_factory=lambda: float(os.getenv("DAILY_BUDGET_USD", "1.0")))
    monthly_budget_usd: float | None = field(default_factory=optional_monthly_budget)
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper())

    def __post_init__(self):
        if not 1 <= self.port <= 65535:
            raise ValueError("PORT must be between 1 and 65535")
        if self.rate_limit_per_minute < 1:
            raise ValueError("RATE_LIMIT_PER_MINUTE must be positive")
        for budget in (self.daily_budget_usd, self.monthly_budget_usd):
            if budget is not None and (not math.isfinite(budget) or budget < 0):
                raise ValueError("Budgets must be finite, non-negative numbers")
        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("Invalid LOG_LEVEL")


settings = Settings()
