import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.middleware import SecurityMiddleware
from app.db import init_db
from app.routes import auth, me, merchants, search, tryon, widget

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("saasta")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="Saasta API", version="1.0.0", lifespan=lifespan,
        docs_url=None if s.is_prod else "/docs", redoc_url=None,
        openapi_url=None if s.is_prod else "/openapi.json",
    )
    app.add_middleware(SecurityMiddleware)

    # Widget is called from partner store sites: open CORS, no cookies, API-key auth only.
    # Everything else only accepts our own web origin with credentials.
    widget_app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    widget_app.include_router(widget.router)
    app.mount("/w", widget_app)

    for r in (auth.router, search.router, merchants.router, me.router, me.public, tryon.router):
        app.include_router(r)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        # Don't echo submitted values back (could contain passwords).
        errs = [{"field": ".".join(str(x) for x in e["loc"][1:]), "msg": e["msg"]} for e in exc.errors()]
        return JSONResponse({"detail": "Invalid input", "errors": errs}, status_code=422)

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception):
        log.exception("unhandled error")
        return JSONResponse({"detail": "Internal error"}, status_code=500)

    @app.get("/health")
    async def health():
        return {"ok": True}

    strict = CORSMiddleware(
        app, allow_origins=s.cors_origins, allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type", "X-Request-ID"],
        max_age=600,
    )
    open_ = CORSMiddleware(app, allow_origins=["*"], allow_credentials=False, allow_methods=["POST"],
                           allow_headers=["X-API-Key", "Content-Type"], max_age=600)

    async def asgi(scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith("/w/"):
            return await open_(scope, receive, send)
        return await strict(scope, receive, send)

    asgi.fastapi = app  # handy for tests
    return asgi


app = create_app()
