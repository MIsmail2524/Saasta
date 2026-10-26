"""Seller trust signals. Not a verdict, a set of explainable reasons a shopper can act on."""
import asyncio
import statistics
import time
from datetime import datetime, timezone

import httpx

from app.search.types import Offer

TRUSTED = {
    "daraz.pk", "amazon.com", "amazon.ae", "amazon.in", "amazon.co.uk", "noon.com", "myntra.com",
    "ajio.com", "flipkart.com", "zalando.com", "asos.com", "farfetch.com", "nordstrom.com",
    "zara.com", "hm.com", "uniqlo.com", "nike.com", "adidas.com", "ebay.com", "etsy.com",
    "khaadi.com", "pk.khaadi.com", "gulahmedshop.com", "sapphireonline.pk", "junaidjamshed.com",
    "outfitters.com.pk", "breakout.com.pk", "limelight.pk", "alkaramstudio.com", "nishatlinen.com",
    "mariab.pk", "bonanzasatrangi.com", "stylo.pk", "bata.com.pk", "servis.pk", "ndure.com",
    "ethnic.com.pk", "jdot.com.pk", "beechtree.pk", "zellbury.com", "generation.com.pk",
    "sanaSafinaz.com".lower(), "agha-noor.com", "charcoal.com.pk", "diners.com.pk", "shein.com",
    "temu.com", "aliexpress.com", "walmart.com", "target.com",
}
SOCIAL = {"instagram", "tiktok"}

_age_cache: dict[str, tuple[float, float | None]] = {}
_lock = asyncio.Semaphore(6)


async def domain_age_days(domain: str) -> float | None:
    root = ".".join(domain.split(".")[-3:]) if domain.endswith((".com.pk", ".co.uk", ".com.au")) \
        else ".".join(domain.split(".")[-2:])
    hit = _age_cache.get(root)
    if hit and hit[0] > time.time():
        return hit[1]
    age = None
    try:
        async with _lock, httpx.AsyncClient(timeout=4, trust_env=False, follow_redirects=True) as c:
            r = await c.get(f"https://rdap.org/domain/{root}")
            if r.status_code == 200:
                for ev in r.json().get("events", []):
                    if ev.get("eventAction") == "registration":
                        reg = datetime.fromisoformat(ev["eventDate"].replace("Z", "+00:00"))
                        age = (datetime.now(timezone.utc) - reg).days
    except Exception:
        age = None
    _age_cache[root] = (time.time() + 86400, age)
    return age


def _base(domain: str) -> bool:
    return any(domain == t or domain.endswith("." + t) for t in TRUSTED)


async def score(offers: list[Offer], check_age: bool = True) -> None:
    exact_prices = [o.price_local for o in offers if o.match == "exact" and o.price_local]
    all_prices = [o.price_local for o in offers if o.price_local]
    ref = statistics.median(exact_prices or all_prices) if (exact_prices or all_prices) else None

    domains = {o.domain for o in offers if o.source not in SOCIAL and not _base(o.domain)}
    ages = {}
    if check_age and domains:
        res = await asyncio.gather(*(domain_age_days(d) for d in list(domains)[:15]))
        ages = dict(zip(list(domains)[:15], res))

    for o in offers:
        pts, why = 60, []
        if o.partner:
            pts += 20
            why.append("+ Verified Saasta partner store")
        if _base(o.domain):
            pts += 25
            why.append("+ Well-known store or marketplace")
        if o.url.startswith("https://"):
            pts += 3
        else:
            pts -= 15
            why.append("- Site does not use HTTPS")
        if o.reviews and o.reviews >= 20 and (o.rating or 0) >= 4:
            pts += 10
            why.append(f"+ {o.reviews} reviews, rated {o.rating}")
        elif o.rating is not None and o.rating < 3:
            pts -= 10
            why.append(f"- Low rating ({o.rating})")
        age = ages.get(o.domain)
        if age is not None:
            if age < 120:
                pts -= 25
                why.append(f"- Website is only {age} days old")
            elif age > 3 * 365:
                pts += 5
                why.append(f"+ Website active for {age // 365}+ years")
        if o.source in SOCIAL:
            pts -= 10
            why.append("- Social seller: ask for COD or a video call before paying")
        if ref and o.price_local and o.match == "exact" and o.price_local < 0.35 * ref:
            pts -= 30
            why.append("- Price is far below other sellers of the same item (possible fake)")
        o.trust = {"score": max(0, min(100, pts)), "reasons": why,
                   "level": "high" if pts >= 75 else "medium" if pts >= 50 else "low"}
