"""Search orchestration: image/video/url/text -> ranked sellers, prices, dupes, trust."""
import asyncio
import logging
import statistics
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from PIL import Image

from app.core.config import get_settings
from app.net.safe_fetch import safe_get, safe_outbound
from app.search import money, trust, understand, visual
from app.search.providers import catalog
from app.search.providers.serpapi import GoogleLens, GoogleShopping
from app.search.providers.social import Instagram, TikTok
from app.search.types import Offer, Query

log = logging.getLogger("saasta.search")
TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid",
            "srsltid", "igshid", "ref", "spm"}


async def _safe(name: str, coro, timeout: float):
    try:
        return await asyncio.wait_for(coro, timeout)
    except Exception as e:  # one provider failing must never fail the whole search
        log.warning("provider %s failed: %s", name, type(e).__name__)
        return [], {"error": name}


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
        # merge: keep richer data, exact beats similar, partner beats all
        prev.match = "exact" if "exact" in (prev.match, o.match) else prev.match
        prev.partner = prev.partner or o.partner
        for f in ("price", "currency", "rating", "reviews", "image", "seller", "in_stock"):
            if getattr(prev, f) is None and getattr(o, f) is not None:
                setattr(prev, f, getattr(o, f))
    return list(seen.values())


async def _rerank(fp: dict | None, offers: list[Offer], n: int = 24) -> None:
    if not fp:
        return
    targets = [o for o in offers if o.image and o.similarity is None][:n]

    async def one(o: Offer):
        try:
            data, ctype, _ = await safe_get(o.image, max_bytes=1_500_000, accept="image/*", timeout=4)
            if ctype.startswith("image/") and (other := visual.fingerprint_bytes(data)):
                o.similarity = visual.similarity(fp, other)
        except Exception:
            pass

    await asyncio.gather(*(one(o) for o in targets))


def _rank_key(o: Offer):
    return (
        0 if o.match == "exact" else 1,
        -(o.similarity or 0),
        -(o.trust.get("score", 50)),
        o.price_local if o.price_local is not None else 1e12,
    )


async def search_one(q: Query, img: Image.Image | None, merchant_id: str | None = None) -> dict:
    s = get_settings()
    fp = visual.fingerprint(img) if img else None
    color = visual.dominant_color(img) if img else None
    refine = understand.parse_refinement(q.text)
    q.max_price = refine.get("max_price")
    q.color = refine.get("color")

    lens, shop, ig, tt = GoogleLens(), GoogleShopping(), Instagram(), TikTok()
    sources_used, failed = [], []

    offers: list[Offer] = []
    hints: dict = {}
    if img is not None and lens.enabled():
        o, hints = await _safe(lens.name, lens.search(q), 40)
        offers += o
        sources_used.append(lens.name)
        if hints.get("error"):
            failed.append(lens.name)

    titles = hints.get("titles") or ([] if img is not None else [refine.get("rest") or q.text or ""])
    query = understand.best_query(titles, fallback=refine.get("rest") or q.text)
    if refine.get("rest") and img is not None and refine["rest"].lower() not in ("same", "same but"):
        query = f"{query} {refine['rest']}" if query else refine["rest"]
    category = understand.categorize(titles + ([query] if query else []))
    text_q = Query(text=query, country=q.country, currency=q.currency, color=q.color)

    tasks = {"partner": _safe("partner", _partner(fp, query, category, merchant_id), 10)}
    if not merchant_id:  # widget searches stay inside the merchant's own catalog
        for p in (shop, ig, tt):
            if p.enabled() and query:
                tasks[p.name] = _safe(p.name, p.search(text_q), 60 if p.name != shop.name else 25)
                sources_used.append(p.name)
    results = await asyncio.gather(*tasks.values())
    for name, (o, meta) in zip(tasks.keys(), results):
        offers += o
        if meta.get("error"):
            failed.append(name)

    offers = dedupe(offers)
    for o in offers:
        o.price_local = money.convert(o.price, o.currency or q.currency, q.currency)
    if q.max_price:
        offers = [o for o in offers if o.price_local is None or o.price_local <= q.max_price]

    await _rerank(fp, offers)
    await trust.score(offers, check_age=s.env != "test")
    offers.sort(key=_rank_key)

    priced_exact = [o.price_local for o in offers if o.match == "exact" and o.price_local]
    priced = priced_exact or [o.price_local for o in offers if o.price_local]
    stats = None
    if priced:
        stats = {"min": min(priced), "median": statistics.median(priced), "max": max(priced),
                 "count": len(priced), "basis": "exact" if priced_exact else "similar"}

    # Dupes: visually close, much cheaper, not flagged as risky.
    dupes = []
    if stats:
        dupes = [o for o in offers if o.match == "similar" and o.price_local
                 and o.price_local <= 0.6 * stats["median"] and (o.similarity or 0) >= 0.6
                 and o.trust.get("level") != "low"][:8]

    social = [o for o in offers if o.source in ("instagram", "tiktok")]
    web = [o for o in offers if o.source not in ("instagram", "tiktok")]
    exact = [o for o in web if o.match == "exact"]
    similar = [o for o in web if o.match != "exact"]
    cheapest_trusted = min(
        (o for o in exact or web if o.price_local and o.trust.get("level") == "high"),
        key=lambda o: o.price_local, default=None,
    )

    return {
        "understanding": {
            "query": query, "category": category, "color": color or q.color,
            "tryon_category": understand.TRYON_CATEGORY.get(category or ""),
            "max_price": q.max_price,
        },
        "price": stats,
        "best_deal": cheapest_trusted.to_dict() if cheapest_trusted else None,
        "exact": [o.to_dict() for o in exact[:30]],
        "similar": [o.to_dict() for o in similar[:40]],
        "dupes": [o.to_dict() for o in dupes],
        "social": [o.to_dict() for o in social[:20]],
        "sources": {"used": sorted(set(sources_used + ["partner"])), "failed": sorted(set(failed))},
        "currency": q.currency,
    }


async def _partner(fp, text, category, merchant_id):
    return await catalog.match(fp, text, category, merchant_id=merchant_id), {}
