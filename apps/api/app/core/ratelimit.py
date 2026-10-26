"""Fixed-window rate limiter. Redis in prod, in-memory for dev/tests."""
import time
from collections import defaultdict

from fastapi import HTTPException, Request

from app.core.config import get_settings

try:
    import redis.asyncio as aioredis
except ImportError:  # pragma: no cover
    aioredis = None

_redis = None
_mem: dict[str, tuple[int, float]] = defaultdict(lambda: (0, 0.0))


def _client():
    global _redis
    s = get_settings()
    if s.redis_url and aioredis and _redis is None:
        _redis = aioredis.from_url(s.redis_url, decode_responses=True)
    return _redis


async def hit(key: str, limit: int, window_s: int) -> tuple[bool, int]:
    """Count one hit. Returns (allowed, retry_after_seconds)."""
    now = time.time()
    bucket = int(now // window_s)
    rkey = f"rl:{key}:{window_s}:{bucket}"
    r = _client()
    if r is not None:
        pipe = r.pipeline()
        pipe.incr(rkey)
        pipe.expire(rkey, window_s + 5)
        count, _ = await pipe.execute()
    else:
        c, exp = _mem[rkey]
        if exp < now:
            c = 0
        c += 1
        _mem[rkey] = (c, (bucket + 1) * window_s)
        count = c
        if len(_mem) > 50_000:  # crude GC
            for k in [k for k, (_, e) in _mem.items() if e < now]:
                _mem.pop(k, None)
    retry = int((bucket + 1) * window_s - now) + 1
    return count <= limit, retry


def client_ip(request: Request) -> str:
    hops = get_settings().trusted_proxy_hops
    if hops > 0:
        xff = request.headers.get("x-forwarded-for", "")
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if len(parts) >= hops:
            return parts[-hops]
    return request.client.host if request.client else "unknown"


async def enforce(request: Request, name: str, limit: int, window_s: int, subject: str | None = None):
    key = f"{name}:{subject or client_ip(request)}"
    ok, retry = await hit(key, limit, window_s)
    if not ok:
        raise HTTPException(429, "Too many requests, slow down.", headers={"Retry-After": str(retry)})
