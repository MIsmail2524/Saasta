"""SaastaBot: a polite crawler that builds Saasta's own product index.

- Public pages only. robots.txt is fetched and obeyed (including Crawl-delay), with a 1 req/s floor.
- Shopify stores: the public /products.json feed. Others: sitemaps -> product pages -> JSON-LD.
- We store facts (title, price, link) and an image *embedding*; product images are never re-hosted.
- Sites can opt out any time via robots.txt (User-agent: SaastaBot) or the form on /bot.
"""
import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from defusedxml import ElementTree
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.crawl.extract import extract_product
from app.db import SessionLocal
from app.models import CatalogItem, CrawlSite
from app.net.safe_fetch import UA, UnsafeURL, safe_get, safe_outbound
from app.search import understand
from app.search.providers.base import parse_price

log = logging.getLogger("saasta.crawler")
BOT = "SaastaBot"
PRODUCT_HINTS = ("/product", "/products/", "/p/", "/item", "-p-", "/shop/")


class Site:
    def __init__(self, domain: str):
        self.domain = domain
        self.base = f"https://{domain}"
        self.robots = RobotFileParser()
        self.delay = get_settings().crawl_min_delay_s
        self._last = 0.0

    async def load_robots(self) -> list[str]:
        try:
            body, _, _ = await safe_get(self.base + "/robots.txt", 500_000, "text/plain", timeout=10)
            lines = body.decode("utf-8", "ignore").splitlines()
        except UnsafeURL:
            lines = []
        self.robots.parse(lines)
        d = self.robots.crawl_delay(BOT) or self.robots.crawl_delay("*")
        if d:
            self.delay = max(self.delay, min(float(d), 30.0))
        return self.robots.site_maps() or []

    def allowed(self, url: str) -> bool:
        return self.robots.can_fetch(BOT, url) and self.robots.can_fetch(UA, url)

    async def get(self, url: str, max_bytes: int, accept: str) -> tuple[bytes, str, str] | None:
        if not self.allowed(url):
            return None
        wait = self._last + self.delay - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        self._last = time.monotonic()
        try:
            return await safe_get(url, max_bytes, accept, timeout=20)
        except UnsafeURL:
            return None


def _ext_id(url: str, sku: str | None) -> str:
    return sku or hashlib.sha1(url.encode(), usedforsecurity=False).hexdigest()


async def _upsert(domain: str, items: list[dict]) -> int:
    n = 0
    async with SessionLocal() as db:
        for it in items:
            url, img = safe_outbound(it["url"]), safe_outbound(it["image"])
            host = (urlsplit(url or "").hostname or "").removeprefix("www.")
            if not url or not img or not (host == domain or host.endswith("." + domain)):
                continue
            ext = _ext_id(url, it.get("sku"))
            row = (await db.execute(select(CatalogItem).where(
                CatalogItem.domain == domain, CatalogItem.external_id == ext))).scalar_one_or_none()
            if row is None:
                row = CatalogItem(source="crawl", domain=domain, external_id=ext)
                db.add(row)
            elif row.source == "partner":
                continue  # the store's own feed wins over our crawl
            if row.image_url != img:
                row.vec = row.phash = row.color_hist = None
            row.title, row.url, row.image_url = it["title"][:300], url, img
            row.price, row.currency = it.get("price"), (it.get("currency") or "PKR")[:3].upper()
            row.in_stock, row.brand = it.get("in_stock", True), it.get("brand")
            row.rating, row.reviews = it.get("rating"), it.get("reviews")
            row.category = understand.categorize([it["title"], it.get("type") or ""]) or row.category
            n += 1
        await db.commit()
    return n


async def _crawl_shopify(site: Site, cap: int) -> int | None:
    total, page = 0, 1
    while total < cap and page <= 40:
        res = await site.get(f"{site.base}/products.json?limit=250&page={page}", 10_000_000, "application/json")
        if not res:
            return None if page == 1 else total
        try:
            products = json.loads(res[0]).get("products")
        except ValueError:
            return None if page == 1 else total
        if products is None:
            return None
        if not products:
            break
        batch = []
        for p in products:
            imgs, variants = p.get("images") or [], p.get("variants") or [{}]
            if not imgs or not p.get("handle"):
                continue
            batch.append({"url": f"{site.base}/products/{p['handle']}", "image": imgs[0].get("src", ""),
                          "title": p.get("title") or "", "price": parse_price(variants[0].get("price"))[0],
                          "currency": None, "sku": f"shopify-{p.get('id')}", "brand": p.get("vendor"),
                          "type": p.get("product_type"),
                          "in_stock": any(v.get("available", True) for v in variants)})
        total += await _upsert(site.domain, batch)
        page += 1
    return total


async def _sitemap_urls(site: Site, roots: list[str], cap: int) -> list[str]:
    queue = roots or [site.base + "/sitemap.xml"]
    seen, products = set(), []
    while queue and len(products) < cap and len(seen) < 60:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        res = await site.get(sm, 20_000_000, "application/xml,text/xml")
        if not res:
            continue
        try:
            root = ElementTree.fromstring(res[0])
        except Exception as e:  # defusedxml raises on bombs/external entities
            log.debug("bad sitemap %s: %s", sm, type(e).__name__)
            continue
        locs = [el.text.strip() for el in root.iter() if el.tag.endswith("loc") and el.text]
        if root.tag.endswith("sitemapindex"):
            # product sitemaps first
            queue = sorted(locs, key=lambda u: 0 if "product" in u.lower() else 1) + queue
        else:
            products += [u for u in locs if any(h in u.lower() for h in PRODUCT_HINTS)]
    return list(dict.fromkeys(products))[:cap]


async def crawl_site(domain: str) -> dict:
    s = get_settings()
    site = Site(domain)
    sitemaps = await site.load_robots()
    if not site.allowed(site.base + "/"):
        await _forget(domain)  # opt-out honoured: drop everything we crawled from this site
        return await _finish(domain, None, 0, "blocked by robots.txt")
    count = await _crawl_shopify(site, s.crawl_max_pages_per_site)
    kind = "shopify"
    if count is None:
        kind, count = "sitemap", 0
        urls = await _sitemap_urls(site, sitemaps, s.crawl_max_pages_per_site)
        batch = []
        for url in urls:
            res = await site.get(url, 4_000_000, "text/html")
            if not res or "html" not in res[1]:
                continue
            prod = extract_product(res[0].decode("utf-8", "ignore"))
            if prod:
                prod["url"] = res[2]
                prod["image"] = urljoin(res[2], prod["image"])
                batch.append(prod)
            if len(batch) >= 50:
                count += await _upsert(domain, batch)
                batch = []
        count += await _upsert(domain, batch)
    return await _finish(domain, kind, count, None if count else "no products found")


async def _forget(domain: str) -> None:
    async with SessionLocal() as db:
        await db.execute(delete(CatalogItem).where(CatalogItem.domain == domain, CatalogItem.source == "crawl"))
        await db.commit()


async def _finish(domain: str, kind: str | None, count: int, error: str | None) -> dict:
    async with SessionLocal() as db:
        site = await db.get(CrawlSite, domain) or CrawlSite(domain=domain)
        site.kind, site.products, site.error = kind, count, error
        site.status = "ok" if count else "empty"
        site.last_crawled_at = datetime.now(timezone.utc)
        db.add(site)
        await db.commit()
    log.info("crawled %s kind=%s products=%d %s", domain, kind, count, error or "")
    return {"domain": domain, "kind": kind, "products": count, "error": error}
