"""Embeddable 'Find it in this store' widget + server-to-server visual search API for partner stores."""
from io import BytesIO
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratelimit import client_ip, enforce
from app.core.security import hash_ip
from app.db import get_db
from app.deps import merchant_from_key
from app.media.storage import store
from app.media.validate import MediaError, clean_image
from app.models import Merchant, Search
from app.routes.search import read_capped
from app.search import visual
from app.search.providers import catalog

router = APIRouter(prefix="/v1/widget", tags=["widget"])


@router.post("/search")
async def widget_search(request: Request, file: UploadFile = File(...),
                        m: Merchant = Depends(merchant_from_key), db: AsyncSession = Depends(get_db)):
    """Shopper uploads a photo on the store's site; we return that store's closest products.

    The widget key is publishable, so browser calls must come from the store's own domain.
    """
    origin = request.headers.get("origin")
    if origin:
        host = (urlsplit(origin).hostname or "").removeprefix("www.")
        if not (host == m.domain or host.endswith("." + m.domain)):
            raise HTTPException(403, "Widget not allowed on this site")
    await enforce(request, "widget-ip", 20, 60)
    await enforce(request, "widget-merchant", 5000, 86400, subject=m.id)
    try:
        jpeg, img = clean_image(await read_capped(file, 10 * 1024 * 1024), max_side=800)
    except MediaError as e:
        raise HTTPException(422, str(e))
    fp = visual.fingerprint(img)
    offers = await catalog.match(fp, None, None, limit=12, merchant_id=m.id, min_sim=0.5)
    db.add(Search(kind="image", merchant_id=m.id, status="done", media_key=store().put_jpeg(jpeg),
                  ip_hash=hash_ip(client_ip(request)), country=m.country,
                  result={"count": len(offers)}))
    await db.commit()
    return {"results": [o.to_dict() for o in offers], "color": visual.dominant_color(Image.open(BytesIO(jpeg)))}
