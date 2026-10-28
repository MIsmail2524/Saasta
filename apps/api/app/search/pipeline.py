"""Search over Saasta's own index: image/video/url/text -> ranked sellers, prices, dupes, trust.

Everything runs on our own infrastructure: the fashion embedding model in apps/ml, the vector index
built by our crawler and partner feeds, and fingerprint matching as a fallback when ML is down.
"""
import io
import logging
import statistics
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import imagehash
import numpy as np
from PIL import Image
from sqlalchemy import select

from app import ml_client
from app.core.config import get_settings
from app.db import SessionLocal
from app.models import CatalogItem
from app.net.safe_fetch import safe_outbound
from app.search import index, labels, money, trust, understand, visual
from app.search.providers import catalog
from app.search.types import Offer, Query

log = logging.getLogger("saasta.search")
TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid",
            "srsltid", "igshid", "ref", "spm", "variant"}
EXACT_COS = 0.93       # embedding cosine above which two product photos are the same item
EXACT_PHASH = 10       # or near-identical pixels (resized/recompressed copies)
SIMILAR_COS = 0.55     # below this, results are noise


def canonical(url: str) -> str:
    p = urlsplit(url)
    q = [(k, v) for k, v in parse_qsl(p.query) if k.lower() not in TRACKING]
    host = (p.hostname or "").lower().removeprefix("www.")
    return urlunsplit(("https", host, p.path.rstrip("/"), urlencode(q), ""))


def dedupe(offers: list[Offer]) -> list[Offer]:
    seen: dict[str, Offer] = {}
    for o in offers:
        if not (u := safe_outbound(o.url)):
            continue
        o.url = u
        key = canonical(u)
        prev = seen.get(key)
        if prev is None:
            seen[key] = o
            continue
        prev.match = "exact" if "exact" in (prev.match, o.match) else prev.match
        prev.partner = prev.partner or o.partner
        prev.similarity = max(prev.similarity or 0, o.similarity or 0)
        for f in ("price", "currency", "rating", "reviews", "image", "seller", "in_stock"):
            if getattr(prev, f) is None and getattr(o, f) is not None:
                setattr(prev, f, getattr(o, f))
    return list(seen.values())


def _rank_key(o: Offer):
    return (
        0 if o.match == "exact" else 1,
        -round(o.similarity or 0, 2),
        0 if o.partner else 1,
        -(o.trust.get("score", 50)),
        o.price_local if o.price_local is not None else 1e12,
    )


def _offer(row: CatalogItem, sim: float, fp: dict | None) -> Offer:
    match = "exact" if sim >= EXACT_COS else "similar"
    if fp and row.phash:
        if imagehash.hex_to_hash(fp["phash"]) - imagehash.hex_to_hash(row.phash) <= EXACT_PHASH:
            match = "exact"
    return Offer(
        title=row.title, url=row.url, source=row.source if row.source != "partner" else "partner",
        image=row.image_url, price=row.price, currency=row.currency, rating=row.rating, reviews=row.reviews,
        seller=row.brand or row.domain, in_stock=row.in_stock, match=match, partner=row.source == "partner",
        merchant_id=row.merchant_id, similarity=round(sim, 4), extra={"color": row.color},
    )


async def _vector_search(vec: np.ndarray, fp: dict | None, category: str | None,
                         merchant_id: str | None) -> list[Offer]:
    hits = await index.search(vec, k=150, category=category, merchant_id=merchant_id)
    hits = [(i, s) for i, s in hits if s >= SIMILAR_COS]
    if not hits:
        return []
    async with SessionLocal() as db:
        rows = {r.id: r for r in (await db.execute(
            select(CatalogItem).where(CatalogItem.id.in_([i for i, _ in hits])))).scalars()}
    return [_offer(rows[i], s, fp) for i, s in hits if i in rows]


async def search_one(q: Query, img: Image.Image | None, merchant_id: str | None = None) -> dict:
    s = get_settings()
    fp = visual.fingerprint(img) if img else None
    refine = understand.parse_refinement(q.text)
    q.max_price, q.color = refine.get("max_price"), refine.get("color")
    rest = (refine.get("rest") or "").strip()

    vec: np.ndarray | None = None
    u: dict = {}
    engine = "fingerprint"
    try:
        if img is not None:
            buf = io.BytesIO()
            img.convert("RGB").save(buf, "JPEG", quality=90)
            vec = (await ml_client.embed_images([buf.getvalue()]))[0]
            u = await labels.understand(vec)
            if rest and rest.lower() not in ("same", "same but", "like this", "cheaper", "cheaper dupe"):
                # "same but with sleeves": nudge the image vector toward the text, stay anchored to the photo
                t = (await ml_client.embed_texts([rest]))[0]
                vec = vec + 0.35 * t
                vec /= np.linalg.norm(vec)
        elif q.text:
            text = " ".join(x for x in [q.color, rest or q.text] if x)
            vec = (await ml_client.embed_texts([f"a product photo of {text}"]))[0]
            u = {"query": text, "category": understand.categorize([text])}
        engine = "model"
    except ml_client.MLUnavailable:
        log.warning("ML unavailable, falling back to fingerprint search")

    category = u.get("category")
    if vec is not None:
        offers = await _vector_search(vec, fp, None, merchant_id)
    else:
        offers = await catalog.match(fp, q.text, None, limit=60, merchant_id=merchant_id)

    color = q.color or u.get("color") or (visual.dominant_color(img) if img else None)
    offers = dedupe(offers)
    for o in offers:
        o.price_local = money.convert(o.price, o.currency or q.currency, q.currency)
        if q.color and o.extra.get("color") and o.extra["color"] != q.color:
            o.similarity = (o.similarity or 0) - 0.08  # asked for another colour: demote, don't hide
            if o.match == "exact":
                o.match = "similar"
    if q.max_price:
        offers = [o for o in offers if o.price_local is None or o.price_local <= q.max_price]

    await trust.score(offers, check_age=s.env != "test")
    offers.sort(key=_rank_key)

    priced_exact = [o.price_local for o in offers if o.match == "exact" and o.price_local]
    priced = priced_exact or [o.price_local for o in offers[:20] if o.price_local]
    stats = None
    if priced:
        stats = {"min": min(priced), "median": statistics.median(priced), "max": max(priced),
                 "count": len(priced), "basis": "exact" if priced_exact else "similar"}

    dupes = []
    if stats:
        dupes = [o for o in offers if o.match == "similar" and o.price_local
                 and o.price_local <= 0.6 * stats["median"] and (o.similarity or 0) >= 0.7
                 and o.trust.get("level") != "low"][:8]

    social = [o for o in offers if o.source == "social"]
    web = [o for o in offers if o.source != "social"]
    exact = [o for o in web if o.match == "exact"]
    similar = [o for o in web if o.match != "exact"]
    best = min((o for o in exact or web[:10] if o.price_local and o.trust.get("level") == "high"),
               key=lambda o: o.price_local, default=None)

    return {
        "understanding": {
            "query": u.get("query") or rest or q.text, "category": category, "color": color,
            "attributes": u.get("attributes", []),
            "tryon_category": understand.TRYON_CATEGORY.get(category or ""),
            "max_price": q.max_price,
        },
        "price": stats,
        "best_deal": best.to_dict() if best else None,
        "exact": [o.to_dict() for o in exact[:30]],
        "similar": [o.to_dict() for o in similar[:48]],
        "dupes": [o.to_dict() for o in dupes],
        "social": [o.to_dict() for o in social[:24]],
        "sources": {"engine": engine, "indexed": index.size()},
        "currency": q.currency,
    }
