"""Extract product facts from public pages: schema.org JSON-LD first, OpenGraph as fallback."""
import html
import json
import re

from app.search.providers.base import parse_price

_LD = re.compile(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", re.S | re.I)
_META = re.compile(r"<meta\s+[^>]*>", re.I)
_ATTR = re.compile(r'(property|name|itemprop|content)\s*=\s*(["\'])(.*?)\2', re.I | re.S)


def _nodes(data):
    if isinstance(data, list):
        for d in data:
            yield from _nodes(d)
    elif isinstance(data, dict):
        yield data
        for d in data.get("@graph") or []:
            yield from _nodes(d)


def _is_product(node: dict) -> bool:
    t = node.get("@type")
    return t == "Product" or (isinstance(t, list) and "Product" in t) or t == "ProductGroup"


def _first(v):
    return v[0] if isinstance(v, list) and v else v


def metas(page: str) -> dict:
    out = {}
    for tag in _META.findall(page[:500_000]):
        attrs = {m.group(1).lower(): html.unescape(m.group(3)) for m in _ATTR.finditer(tag)}
        key = attrs.get("property") or attrs.get("name") or attrs.get("itemprop")
        if key and "content" in attrs:
            out.setdefault(key.lower(), attrs["content"])
    return out


def extract_product(page: str) -> dict | None:
    for block in _LD.findall(page[:3_000_000]):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        for node in _nodes(data):
            if not _is_product(node):
                continue
            offers = node.get("offers") or (node.get("hasVariant") or [{}])[0].get("offers") or {}
            offer = _first(offers) if not isinstance(offers, dict) else offers
            offer = offer or {}
            price, cur = parse_price(str(offer.get("price") or offer.get("lowPrice") or "")) if offer else (None, None)
            image = _first(node.get("image"))
            if isinstance(image, dict):
                image = image.get("url")
            rating = node.get("aggregateRating") or {}
            brand = node.get("brand")
            if isinstance(brand, dict):
                brand = brand.get("name")
            avail = str(offer.get("availability", "")).lower()
            if not node.get("name") or not image:
                continue
            return {
                "title": str(node["name"])[:300], "image": str(image), "price": price,
                "currency": (offer.get("priceCurrency") or cur or None),
                "in_stock": "outofstock" not in avail and "soldout" not in avail,
                "brand": str(brand)[:120] if brand else None, "sku": str(node.get("sku") or "")[:160] or None,
                "rating": _num(rating.get("ratingValue")), "reviews": _int(rating.get("reviewCount") or rating.get("ratingCount")),
            }
    m = metas(page)
    if m.get("og:type", "").startswith("product") and m.get("og:image") and m.get("og:title"):
        price, cur = parse_price(m.get("product:price:amount") or m.get("og:price:amount"))
        return {"title": m["og:title"][:300], "image": m["og:image"], "price": price,
                "currency": m.get("product:price:currency") or m.get("og:price:currency") or cur,
                "in_stock": "out" not in m.get("product:availability", ""), "brand": m.get("product:brand"),
                "sku": None, "rating": None, "reviews": None}
    return None


def _num(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _int(v):
    try:
        return int(float(v)) if v is not None else None
    except (TypeError, ValueError):
        return None
