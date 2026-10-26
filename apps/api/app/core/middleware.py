import logging
import time
import uuid
from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import get_settings

log = logging.getLogger("saasta.http")
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}
MAX_BODY = 70 * 1024 * 1024


class SecurityMiddleware(BaseHTTPMiddleware):
    """Request id, body cap, cookie-CSRF origin check, security headers, access log."""

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id", "")[:64] or uuid.uuid4().hex
        s = get_settings()

        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > MAX_BODY:
            return JSONResponse({"detail": "Request too large"}, status_code=413)

        # Cookie-authenticated state changes must come from our own web origin.
        # API-key (widget) and bearer calls carry no ambient credentials, so they are exempt.
        if request.method in UNSAFE and request.cookies.get("saasta_session"):
            origin = request.headers.get("origin") or request.headers.get("referer") or ""
            o = urlsplit(origin)
            allowed = {urlsplit(u).netloc for u in [s.public_web_url, *s.cors_origins]}
            if o.netloc not in allowed:
                return JSONResponse({"detail": "Cross-site request blocked"}, status_code=403)

        start = time.perf_counter()
        resp = await call_next(request)
        resp.headers["X-Request-ID"] = rid
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        resp.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        resp.headers.setdefault("Cache-Control", "no-store")
        if s.is_prod:
            resp.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        log.info("%s %s %s %.0fms rid=%s", request.method, request.url.path, resp.status_code,
                 (time.perf_counter() - start) * 1000, rid)
        return resp
