"""Google Lens + Google Shopping via SerpApi (licensed SERP access, no scraping on our side)."""
import httpx

from app.core.config import get_settings
from app.search.providers.base import parse_price
from app.search.types import Offer, Query

SERPAPI = "https://serpapi.com/search.json"


async def _call(params: dict, timeout: float = 25) -> dict:
    s = get_settings()
    params = {**params, "api_key": s.serpapi_key, "no_cache": "false"}
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as c:
        r = await c.get(SERPAPI, params=params)
        r.raise_for_status()
        return r.json()


def _offer_from(item: dict, source: str, match: str) -> Offer | None:
    url = item.get("link") or item.get("product_link")
    title = item.get("title")
    if not url or not title:
        return None
    price, cur = parse_price(item.get("price") or item.get("extracted_price"))
    if item.get("extracted_price") is not None:
        price = float(item["extracted_price"])
        cur = cur or parse_price(item.get("price"))[1]
    return Offer(
        title=title[:300], url=url, source=source, match=match,
        image=item.get("thumbnail") or item.get("image"),
        price=price, currency=cur, price_text=item.get("price") if isinstance(item.get("price"), str) else None,
        rating=_f(item.get("rating")), reviews=_i(item.get("reviews")),
        seller=item.get("source") or item.get("seller"),
        in_stock=item.get("in_stock"),
    )


def _f(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _i(v):
    try:
        return int(str(v).replace(",", "")) if v is not None else None
    except ValueError:
        return None


class GoogleLens:
    name = "google_lens"

    def enabled(self) -> bool:
        return bool(get_settings().serpapi_key)

    async def search(self, q: Query):
        if not q.image_url:
            return [], {}
        offers: list[Offer] = []
        hints: dict = {}
        exact = await _call({"engine": "google_lens", "url": q.image_url, "type": "exact_matches",
                             "country": q.country})
        for it in exact.get("exact_matches", [])[:20]:
            if o := _offer_from(it, self.name, "exact"):
                offers.append(o)
        prods = await _call({"engine": "google_lens", "url": q.image_url, "type": "products",
                             "country": q.country, **({"q": q.text} if q.text else {})})
        for it in (prods.get("visual_matches") or [])[:40]:
            if o := _offer_from(it, self.name, "similar"):
                offers.append(o)
        titles = [o.title for o in offers[:8]]
        if titles:
            hints["titles"] = titles
        for rs in prods.get("related_content", [])[:1]:
            if rs.get("query"):
                hints["query"] = rs["query"]
        return offers, hints


class GoogleShopping:
    """Text leg: once we know what the product is, find every seller + price + reviews."""

    name = "google_shopping"

    def enabled(self) -> bool:
        return bool(get_settings().serpapi_key)

    async def search(self, q: Query):
        if not q.text:
            return [], {}
        text = f"{q.text} {q.color}" if q.color and q.color not in q.text.lower() else q.text
        data = await _call({"engine": "google_shopping", "q": text[:200], "gl": q.country, "hl": "en",
                            "num": 40})
        offers = []
        for it in (data.get("shopping_results") or [])[:40]:
            if o := _offer_from(it, self.name, "similar"):
                offers.append(o)
        return offers, {}
