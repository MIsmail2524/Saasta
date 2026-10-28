"""Virtual try-on on Saasta's own models (apps/ml). Nothing leaves our infrastructure."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import jobs, ml_client
from app.core.config import get_settings
from app.core.ratelimit import enforce
from app.db import SessionLocal, get_db
from app.deps import current_user
from app.media.storage import store
from app.media.validate import MediaError, clean_image
from app.models import TryOn, User
from app.net.safe_fetch import UnsafeURL, safe_get, safe_outbound
from app.routes.search import read_capped

router = APIRouter(prefix="/v1/tryon", tags=["tryon"])
GARMENT = {"auto", "tops", "bottoms", "one-pieces"}
ACCESSORY = {"shoes", "bags", "jewellery", "watches", "eyewear", "necklace", "earrings"}
MAX_RUNNING_PER_USER = 2


async def _run(tryon_id: str, person: bytes, product: bytes, category: str) -> None:
    async with SessionLocal() as db:
        t = await db.get(TryOn, tryon_id)
        try:
            if category in ACCESSORY:
                out = await ml_client.place(person, product, category)
            else:
                out = await ml_client.tryon(person, product, "tops" if category == "auto" else category)
            jpeg, _ = clean_image(out, max_side=1536)
            # The result is the user's own image: stored under an unguessable key, deleted with their account.
            t.output_key, t.status = store().put_jpeg(jpeg), "done"
        except ml_client.MLUnavailable:
            t.status, t.error = "failed", "Try-on is busy right now, please try again in a minute"
        except (ValueError, MediaError) as e:
            t.status, t.error = "failed", str(e)[:300]
        await db.commit()


@router.post("", status_code=202)
async def start_tryon(
    request: Request,
    photo: UploadFile = File(...),
    garment_url: str = Form(max_length=2048),
    category: str = Form(default="auto", pattern=r"^(auto|tops|bottoms|one-pieces|shoes|bags|jewellery|watches|eyewear|necklace|earrings)$"),
    consent: bool = Form(...),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    s = get_settings()
    if not consent:
        raise HTTPException(422, "Please confirm this is your photo and you agree to processing")
    await enforce(request, "tryon", s.rl_tryon_per_day, 86400, subject=user.id)
    running = await db.scalar(select(func.count()).select_from(TryOn).where(
        TryOn.user_id == user.id, TryOn.status == "running",
        TryOn.created_at > datetime.now(timezone.utc) - timedelta(minutes=15)))
    if running >= MAX_RUNNING_PER_USER:
        raise HTTPException(429, "Wait for your current try-on to finish")
    if not safe_outbound(garment_url):
        raise HTTPException(422, "Invalid product image link")
    try:
        # Person photo: cleaned in memory and sent to our own ML service; the original is never stored.
        person, _ = clean_image(await read_capped(photo, s.max_image_bytes), max_side=1536)
        if garment_url.startswith(f"{s.public_api_url}/v1/media/"):
            raw = store().get(garment_url.rsplit("/", 1)[-1]) or b""
            ctype = "image/jpeg"
        else:
            raw, ctype, _ = await safe_get(garment_url, s.max_image_bytes, "image/*")
        if not ctype.startswith("image/"):
            raise MediaError("Product link is not an image")
        garment, _ = clean_image(raw, max_side=1536)
    except (MediaError, UnsafeURL) as e:
        raise HTTPException(422, str(e))
    t = TryOn(user_id=user.id, category=category, status="running")
    db.add(t)
    await db.commit()
    jobs.spawn(_run(t.id, person, garment, category))
    return {"id": t.id, "status": t.status}


@router.get("/{tryon_id}")
async def get_tryon(tryon_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    t = await db.get(TryOn, tryon_id)
    if not t or t.user_id != user.id:
        raise HTTPException(404, "Not found")
    return {"id": t.id, "status": t.status, "error": t.error,
            "output_url": f"/api/v1/media/{t.output_key}" if t.output_key else None}
