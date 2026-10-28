"""Turns catalog rows into searchable vectors: fetch image safely, fingerprint, embed, classify."""
import asyncio
import io
import logging

from PIL import Image
from sqlalchemy import or_, select

from app import ml_client
from app.db import SessionLocal
from app.media.validate import clean_image
from app.models import CatalogItem
from app.net.safe_fetch import safe_get
from app.search import labels, visual

log = logging.getLogger("saasta.indexer")
BATCH = 16


async def _download(row: CatalogItem, sem: asyncio.Semaphore) -> bytes | None:
    async with sem:
        try:
            data, ctype, _ = await safe_get(row.image_url, 6_000_000, "image/*", timeout=12)
            if not ctype.startswith("image/"):
                return None
            jpeg, _ = clean_image(data, max_side=512)
            return jpeg
        except Exception:  # one bad image must not stop the batch
            return None


async def index_pending(limit: int = 2000, merchant_id: str | None = None, domain: str | None = None) -> int:
    """Embed rows that have no vector yet. Returns how many were indexed."""
    done = 0
    sem = asyncio.Semaphore(8)
    async with SessionLocal() as db:
        stmt = select(CatalogItem).where(or_(CatalogItem.vec.is_(None), CatalogItem.phash.is_(None)))
        if merchant_id:
            stmt = stmt.where(CatalogItem.merchant_id == merchant_id)
        if domain:
            stmt = stmt.where(CatalogItem.domain == domain)
        rows = (await db.execute(stmt.limit(limit))).scalars().all()
        for i in range(0, len(rows), BATCH):
            chunk = rows[i:i + BATCH]
            images = await asyncio.gather(*(_download(r, sem) for r in chunk))
            ok = [(r, j) for r, j in zip(chunk, images, strict=True) if j]
            for r, j in ok:
                img = Image.open(io.BytesIO(j))
                fp = visual.fingerprint(img)
                r.phash, r.color_hist = fp["phash"], visual.hist_to_bytes(fp["hist"])
                r.color = visual.dominant_color(img)
            try:
                vecs = await ml_client.embed_images([j for _, j in ok]) if ok else []
                for (r, _), v in zip(ok, vecs, strict=True):
                    r.vec = ml_client.to_f16(v)
                    u = await labels.understand(v)
                    r.category = r.category or u["category"]
                    r.color = u["color"]
                    done += 1
            except ml_client.MLUnavailable:
                log.warning("ML service unavailable; stored fingerprints only")
            await db.commit()
    return done
