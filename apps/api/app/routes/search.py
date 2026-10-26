import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from io import BytesIO
from urllib.parse import quote, urlsplit

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi import Query as Q
from fastapi.responses import FileResponse, RedirectResponse
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import jobs
from app.core.config import get_settings
from app.core.ratelimit import client_ip, enforce
from app.core.security import hash_ip
from app.db import SessionLocal, get_db
from app.deps import optional_user
from app.media import video
from app.media.storage import store
from app.media.validate import MediaError, clean_image, sniff
from app.models import Click, Search, User
from app.net.safe_fetch import UnsafeURL, safe_outbound
from app.search import from_url, pipeline
from app.search.types import Query

router = APIRouter(prefix="/v1", tags=["search"])
READ_CHUNK = 1024 * 1024
CACHE_HOURS = 24


async def read_capped(f: UploadFile, cap: int) -> bytes:
    buf = bytearray()
    while chunk := await f.read(READ_CHUNK):
        buf.extend(chunk)
        if len(buf) > cap:
            raise HTTPException(413, "File too large")
    return bytes(buf)


def media_url(key: str) -> str:
    return f"{get_settings().public_api_url}/v1/media/{key}"


def sign_out(search_id: str, url: str) -> str:
    return hmac.new(get_settings().secret_key.encode(), f"{search_id}|{url}".encode(),
                    hashlib.sha256).hexdigest()[:32]


def out_link(search_id: str, url: str) -> str:
    return f"/v1/out?s={search_id}&u={quote(url, safe='')}&sig={sign_out(search_id, url)}"


@router.post("/searches", status_code=202)
async def create_search(
    request: Request,
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None, max_length=2048),
    text: str | None = Form(default=None, max_length=300),
    country: str = Form(default="pk", pattern=r"^[a-z]{2}$"),
    currency: str = Form(default="PKR", pattern=r"^[A-Z]{3}$"),
    user: User | None = Depends(optional_user),
    db: AsyncSession = Depends(get_db),
):
    s = get_settings()
    subject = user.id if user else None
    await enforce(request, "search-min", s.rl_search_per_min, 60, subject)
    await enforce(request, "search-day", s.rl_search_per_day, 86400, subject)

    if not (file or url or (text and text.strip())):
        raise HTTPException(422, "Upload a photo/video, paste a link, or type what you want")

    search = Search(user_id=subject, country=country, query_text=(text or None),
                    ip_hash=hash_ip(client_ip(request)), kind="text")
    payload: dict = {"text": text, "country": country, "currency": currency}

    try:
        if file:
            raw = await read_capped(file, max(s.max_image_bytes, s.max_video_bytes))
            kind = sniff(raw)
            if kind in ("mp4", "webm"):
                search.kind = "video"
                payload["video"] = raw
            else:
                search.kind = "image"
                jpeg, _ = clean_image(raw)
                search.media_key = store().put_jpeg(jpeg)
        elif url:
            if not safe_outbound(url):
                raise HTTPException(422, "Paste a valid http(s) link")
            search.kind = "url"
            payload["url"] = url
    except MediaError as e:
        raise HTTPException(422, str(e))

    # Same image + same refinement recently? Reuse it: instant for the shopper, no provider cost.
    if search.media_key:
        since = datetime.now(timezone.utc) - timedelta(hours=CACHE_HOURS)
        prev = (await db.execute(
            select(Search).where(Search.media_key == search.media_key, Search.status == "done",
                                 Search.query_text.is_(None) if search.query_text is None
                                 else Search.query_text == search.query_text,
                                 Search.country == country, Search.merchant_id.is_(None),
                                 Search.created_at >= since)
            .order_by(Search.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        if prev and prev.result and (prev.result.get("currency") in (None, currency)):
            search.status, search.result = "done", prev.result
            search.category, search.best_price = prev.category, prev.best_price
            search.finished_at = datetime.now(timezone.utc)

    db.add(search)
    await db.commit()
    if search.status != "done":
        jobs.spawn(_run(search.id, payload))
    return {"id": search.id, "status": search.status}


async def _run(search_id: str, payload: dict) -> None:
    s = get_settings()
    async with SessionLocal() as db:
        search = await db.get(Search, search_id)
        search.status = "running"
        await db.commit()
        try:
            q = Query(text=payload.get("text"), country=payload["country"], currency=payload["currency"])
            if "video" in payload:
                frames = await video.keyframes(payload["video"], max_frames=4)
                looks = []
                for fr in frames:
                    key = store().put_jpeg(fr["jpeg"])
                    img = Image.open(BytesIO(fr["jpeg"]))
                    fq = Query(text=q.text, country=q.country, currency=q.currency, image_url=media_url(key))
                    res = await pipeline.search_one(fq, img)
                    looks.append({"t": fr["t"], "image": key, **res})
                search.media_key = looks[0]["image"]
                result = {"kind": "video", "looks": looks}
            else:
                img = None
                if search.kind == "url":
                    data, title = await from_url.resolve(payload["url"], s.max_image_bytes)
                    if data:
                        jpeg, _ = clean_image(data)
                        search.media_key = store().put_jpeg(jpeg)
                    if title and not q.text:
                        q.text = title
                    if not data and not q.text:
                        raise MediaError("Could not find a product image on that page")
                if search.media_key:
                    img = Image.open(BytesIO(store().get(search.media_key)))
                    q.image_url = media_url(search.media_key)
                res = await pipeline.search_one(q, img)
                result = {"kind": search.kind, "image": search.media_key, **res}
            search.result = result
            first = result if result["kind"] != "video" else result["looks"][0]
            search.category = first["understanding"]["category"]
            search.best_price = (first.get("price") or {}).get("min")
            search.status = "done"
        except (MediaError, UnsafeURL) as e:
            search.status, search.error = "failed", str(e)[:300]
        except Exception:
            search.status, search.error = "failed", "Something went wrong, please try again"
            raise
        finally:
            search.finished_at = datetime.now(timezone.utc)
            await db.commit()


def _with_links(search_id: str, result: dict) -> dict:
    def walk(node):
        if isinstance(node, dict):
            if "url" in node and "source" in node and isinstance(node["url"], str):
                node = {**node, "out": out_link(search_id, node["url"])}
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node
    return walk(result)


@router.get("/searches/{search_id}")
async def get_search(search_id: str, db: AsyncSession = Depends(get_db)):
    if len(search_id) != 32 or not search_id.isalnum():
        raise HTTPException(404, "Not found")
    search = await db.get(Search, search_id)
    if not search:
        raise HTTPException(404, "Not found")
    return {
        "id": search.id, "status": search.status, "error": search.error, "kind": search.kind,
        "image": search.media_key, "created_at": search.created_at,
        "result": _with_links(search.id, search.result) if search.result else None,
    }


@router.get("/media/{key}")
async def media(key: str):
    path = store().path(key)
    if not path:
        raise HTTPException(404, "Not found")
    return FileResponse(path, media_type="image/jpeg", headers={
        "Cache-Control": "public, max-age=86400, immutable",
        "Cross-Origin-Resource-Policy": "cross-origin",
    })


@router.get("/out")
async def outbound(request: Request, s: str = Q(max_length=32), u: str = Q(max_length=2048),
                   sig: str = Q(max_length=64), db: AsyncSession = Depends(get_db)):
    """Signed click-out: only links we generated can redirect (no open redirect)."""
    if not hmac.compare_digest(sig, sign_out(s, u)) or not (safe := safe_outbound(u)):
        raise HTTPException(400, "Invalid link")
    search = await db.get(Search, s)
    host = (urlsplit(safe).hostname or "").removeprefix("www.")
    merchant_id = None
    if search and search.result:
        for bucket in ("exact", "similar", "dupes"):
            for o in search.result.get(bucket, []):
                if o.get("url") == u and o.get("merchant_id"):
                    merchant_id = o["merchant_id"]
    db.add(Click(search_id=s, merchant_id=merchant_id, url=safe, domain=host,
                 ip_hash=hash_ip(client_ip(request))))
    await db.commit()
    return RedirectResponse(safe, status_code=302, headers={"Referrer-Policy": "origin"})
