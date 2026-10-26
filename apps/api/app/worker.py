"""Periodic jobs: price-watch refresh and data retention.

Run as a separate process:  python -m app.worker
"""
import asyncio
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update

from app.core.config import get_settings
from app.db import SessionLocal, init_db
from app.media.storage import store
from app.models import Search, Watch
from app.net.safe_fetch import safe_get
from app.search.providers.base import parse_price

log = logging.getLogger("saasta.worker")
_LD = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.S | re.I)
_META_PRICE = re.compile(
    r'<meta[^>]+(?:property|itemprop)=["\'](?:product:price:amount|og:price:amount|price)["\'][^>]+content=["\']([^"\']+)',
    re.I,
)


def extract_price(page: str) -> float | None:
    for block in _LD.findall(page[:2_000_000]):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        for node in data if isinstance(data, list) else [data, *(data.get("@graph") or [])]:
            if not isinstance(node, dict):
                continue
            offers = node.get("offers")
            for off in offers if isinstance(offers, list) else [offers]:
                if isinstance(off, dict):
                    p = off.get("price") or off.get("lowPrice")
                    if p is not None:
                        v, _ = parse_price(str(p))
                        if v:
                            return v
    if m := _META_PRICE.search(page):
        return parse_price(m.group(1))[0]
    return None


async def refresh_watches() -> int:
    alerts = 0
    async with SessionLocal() as db:
        watches = (await db.execute(select(Watch).where(Watch.active.is_(True)).limit(2000))).scalars().all()
        sem = asyncio.Semaphore(4)

        async def one(w: Watch):
            nonlocal alerts
            async with sem:
                try:
                    body, ctype, _ = await safe_get(w.url, 3_000_000, "text/html", timeout=15)
                except Exception:
                    return
                if "html" not in ctype or not (price := extract_price(body.decode("utf-8", "ignore"))):
                    return
                hist = list(w.history or [])
                hist.append({"price": price, "at": datetime.now(timezone.utc).isoformat()})
                w.history = hist[-60:]
                dropped = w.last_price and price < w.last_price
                hit_target = w.target_price and price <= w.target_price
                if dropped or hit_target:
                    alerts += 1
                    log.info("price alert watch=%s %s -> %s", w.id, w.last_price, price)
                    # Notification channel (email / WhatsApp / push) plugs in here.
                w.last_price = price

        await asyncio.gather(*(one(w) for w in watches))
        await db.commit()
    return alerts


async def retention() -> None:
    """Privacy by default: anonymous uploads are removed after the TTL."""
    s = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=s.search_ttl_hours)
    async with SessionLocal() as db:
        # Scrub identifying bits from anonymous searches; keep anonymous aggregates for insights.
        await db.execute(update(Search).where(
            Search.user_id.is_(None), Search.created_at < cutoff, Search.media_key.is_not(None)
        ).values(media_key=None, ip_hash=None, query_text=None))
        await db.execute(delete(Search).where(
            Search.user_id.is_(None), Search.created_at < datetime.now(timezone.utc) - timedelta(days=180)))
        await db.commit()
        keep = {k for (k,) in (await db.execute(select(Search.media_key))).all() if k}
    root = store().root
    for name in os.listdir(root):
        p = os.path.join(root, name)
        if name not in keep and os.path.getmtime(p) < cutoff.timestamp():
            os.remove(p)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    await init_db()
    while True:
        try:
            await retention()
            n = await refresh_watches()
            log.info("cycle done, %d alerts", n)
        except Exception:
            log.exception("worker cycle failed")
        await asyncio.sleep(6 * 3600)


if __name__ == "__main__":
    asyncio.run(main())
