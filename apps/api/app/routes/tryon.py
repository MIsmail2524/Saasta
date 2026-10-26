from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.ratelimit import enforce
from app.db import get_db
from app.deps import current_user
from app.media.validate import MediaError, clean_image
from app.models import TryOn, User
from app.net.safe_fetch import UnsafeURL, safe_get, safe_outbound
from app.routes.search import read_capped
from app.tryon import fashn

router = APIRouter(prefix="/v1/tryon", tags=["tryon"])
ACCESSORY = {"shoes", "bags", "jewellery", "watches", "eyewear"}


@router.post("", status_code=202)
async def start_tryon(
    request: Request,
    photo: UploadFile = File(...),
    garment_url: str = Form(max_length=2048),
    category: str = Form(default="auto", pattern=r"^(auto|tops|bottoms|one-pieces|shoes|bags|jewellery|watches|eyewear)$"),
    consent: bool = Form(...),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    s = get_settings()
    if not s.fashn_api_key:
        raise HTTPException(503, "Try-on is not enabled yet")
    if not consent:
        raise HTTPException(422, "Please confirm this is your photo and you agree to processing")
    await enforce(request, "tryon", s.rl_tryon_per_day, 86400, subject=user.id)
    if not safe_outbound(garment_url):
        raise HTTPException(422, "Invalid product image link")
    try:
        # Person photo: cleaned in memory, sent to the provider, never written to our disk.
        person, _ = clean_image(await read_capped(photo, s.max_image_bytes), max_side=1536)
        g_raw, ctype, _ = await safe_get(garment_url, s.max_image_bytes, "image/*")
        if not ctype.startswith("image/"):
            raise MediaError("Product link is not an image")
        garment, _ = clean_image(g_raw, max_side=1536)
    except (MediaError, UnsafeURL) as e:
        raise HTTPException(422, str(e))
    try:
        job = await fashn.start(person, garment, category, accessory=category in ACCESSORY)
    except Exception:
        raise HTTPException(502, "Try-on service is busy, try again shortly")
    t = TryOn(user_id=user.id, category=category, provider_job=job, status="running")
    db.add(t)
    await db.commit()
    return {"id": t.id, "status": t.status}


@router.get("/{tryon_id}")
async def get_tryon(tryon_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    t = await db.get(TryOn, tryon_id)
    if not t or t.user_id != user.id:
        raise HTTPException(404, "Not found")
    if t.status == "running" and t.provider_job:
        try:
            t.status, t.output_url, t.error = await fashn.status(t.provider_job)
            await db.commit()
        except Exception:
            pass
    return {"id": t.id, "status": t.status, "output_url": safe_outbound(t.output_url), "error": t.error}
