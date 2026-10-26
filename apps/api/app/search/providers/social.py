"""Instagram & TikTok seller discovery via Apify actors.

Many South Asian brands sell mainly through IG/TikTok DMs, so these sources surface sellers
Google never indexes. We only read public posts and link back to the original post.
"""
import re

import httpx

from app.core.config import get_settings
from app.search.providers.base import parse_price
from app.search.types import Offer, Query

APIFY = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
PRICE_RE = re.compile(r"(?:rs\.?|pkr|₨|price[:\s]*)\s*([\d,]{3,9})", re.I)
SELL_WORDS = ("price", "rs", "pkr", "dm", "order", "whatsapp", "cod", "delivery", "available", "stock")


def _hashtags(text: str) -> list[str]:
    words = [w for w in re.findall(r"[a-zA-Z]{3,}", text.lower()) if w not in _STOP]
    tags = []
    if len(words) >= 2:
        tags.append("".join(words[:2]))
    tags += words[:2]
    return list(dict.fromkeys(tags))[:3]


_STOP = {"the", "and", "for", "with", "women", "men", "new", "buy", "online", "sale", "best"}


async def _actor(actor: str, payload: dict, timeout: float = 60) -> list[dict]:
    token = get_settings().apify_token
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as c:
        r = await c.post(APIFY.format(actor=actor), params={"token": token}, json=payload)
        r.raise_for_status()
        return r.json() if isinstance(r.json(), list) else []


def _seller_post(caption: str) -> bool:
    c = caption.lower()
    return sum(w in c for w in SELL_WORDS) >= 2


class Instagram:
    name = "instagram"

    def enabled(self) -> bool:
        return bool(get_settings().apify_token)

    async def search(self, q: Query):
        if not q.text:
            return [], {}
        items = await _actor("apify~instagram-hashtag-scraper",
                             {"hashtags": _hashtags(q.text), "resultsLimit": 30})
        offers = []
        for it in items:
            cap = it.get("caption") or ""
            if not _seller_post(cap) or not it.get("url"):
                continue
            m = PRICE_RE.search(cap)
            price = parse_price(m.group(1))[0] if m else None
            offers.append(Offer(
                title=(cap.split("\n")[0] or "Instagram post")[:140], url=it["url"], source=self.name,
                image=it.get("displayUrl"), price=price, currency="PKR" if price else None,
                seller="@" + (it.get("ownerUsername") or "seller"),
                extra={"likes": it.get("likesCount"), "comments": it.get("commentsCount")},
            ))
        return offers, {}


class TikTok:
    name = "tiktok"

    def enabled(self) -> bool:
        return bool(get_settings().apify_token)

    async def search(self, q: Query):
        if not q.text:
            return [], {}
        items = await _actor("clockworks~tiktok-scraper",
                             {"searchQueries": [q.text[:80]], "resultsPerPage": 20,
                              "shouldDownloadVideos": False, "shouldDownloadCovers": False})
        offers = []
        for it in items:
            cap = it.get("text") or ""
            url = it.get("webVideoUrl")
            if not url or not _seller_post(cap):
                continue
            m = PRICE_RE.search(cap)
            price = parse_price(m.group(1))[0] if m else None
            author = (it.get("authorMeta") or {}).get("name") or "seller"
            offers.append(Offer(
                title=cap[:140] or "TikTok video", url=url, source=self.name,
                image=(it.get("videoMeta") or {}).get("coverUrl"), price=price,
                currency="PKR" if price else None, seller="@" + author,
                extra={"plays": it.get("playCount"), "likes": it.get("diggCount")},
            ))
        return offers, {}
