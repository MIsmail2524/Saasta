"""Partner catalog matching: stores that onboard with Saasta are matched visually first-party."""
import numpy as np
from sqlalchemy import or_, select

from app.db import SessionLocal
from app.models import CatalogItem
from app.search.types import Offer
from app.search.visual import hist_from_bytes, similarity


async def match(fp: dict | None, text: str | None, category: str | None, limit: int = 12,
                merchant_id: str | None = None, min_sim: float = 0.55) -> list[Offer]:
    async with SessionLocal() as db:
        stmt = select(CatalogItem).where(CatalogItem.in_stock.is_(True))
        if merchant_id:
            stmt = stmt.where(CatalogItem.merchant_id == merchant_id)
        if category:
            stmt = stmt.where(or_(CatalogItem.category == category, CatalogItem.category.is_(None)))
        items = (await db.execute(stmt.limit(5000))).scalars().all()
    scored = []
    words = set((text or "").lower().split())
    for it in items:
        sim = 0.0
        if fp and it.phash and it.color_hist:
            sim = similarity(fp, {"phash": it.phash, "hist": hist_from_bytes(it.color_hist)})
        if words:
            overlap = len(words & set(it.title.lower().split())) / max(len(words), 1)
            sim = max(sim, 0.5 + 0.4 * overlap if overlap >= 0.5 else sim)
        if sim >= min_sim:
            scored.append((sim, it))
    scored.sort(key=lambda x: -x[0])
    return [
        Offer(title=it.title, url=it.url, source=it.source, image=it.image_url, price=it.price,
              currency=it.currency, seller=it.brand or it.domain, in_stock=it.in_stock, partner=it.source == "partner",
              merchant_id=it.merchant_id, similarity=round(float(np.clip(s, 0, 1)), 3),
              match="exact" if s > 0.86 else "similar")
        for s, it in scored[:limit]
    ]
