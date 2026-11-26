"""Agent Part 6: health, readiness, API key và state dùng chung trong Redis."""
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, get_usage, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import r, redis_healthy
from utils.mock_llm import ask as llm_ask


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        for field in ("method", "path", "status", "ms", "component", "environment"):
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


logger = logging.getLogger("production_agent")
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.handlers.clear()
logger.addHandler(handler)
logger.setLevel(settings.log_level)
logger.propagate = False
START_TIME = time.monotonic()


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.shutting_down = False
    logger.info("startup", extra={"environment": settings.environment})
    try:
        yield
    finally:
        # Uvicorn xử lý SIGTERM, ngừng nhận kết nối và chờ các request
        # trước khi gọi cleanup. Không thay signal handler của Uvicorn.
        application.state.shutting_down = True
        r.close()
        logger.info("shutdown_complete")


app = FastAPI(title="Production AI Agent", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def log_request(request: Request, call_next):
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        logger.info("http_request", extra={
            "method": request.method,
            "path": request.url.path,
            "status": status,
            "ms": round((time.perf_counter() - started) * 1000, 3),
        })


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


@app.get("/health")
def health():
    # Liveness không phụ thuộc Redis.
    return {
        "status": "ok",
        "uptime_seconds": round(time.monotonic() - START_TIME, 2),
        "environment": settings.environment,
    }


@app.get("/ready")
def ready():
    healthy = redis_healthy()
    if not healthy or app.state.shutting_down:
        return JSONResponse(status_code=503, content={"ready": False, "redis": healthy})
    return {"ready": True, "redis": True}


@app.post("/ask")
def ask(body: AskRequest, response: Response, api_key: str = Depends(verify_api_key)):
    rate_headers = check_rate_limit(api_key)
    check_budget()
    answer = llm_ask(body.question)
    input_tokens = max(1, len(body.question.split()) * 2)
    output_tokens = max(1, len(answer.split()) * 2)
    cost = record_cost(input_tokens, output_tokens)
    response.headers.update(rate_headers)
    return {
        "question": body.question,
        "answer": answer,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
            "budgets": get_usage(),
        },
    }


@app.get("/usage")
def usage(api_key: str = Depends(verify_api_key)):
    return get_usage()
