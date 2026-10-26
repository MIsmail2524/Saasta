"""Store side: onboarding, domain verification, catalog sync, API keys, analytics, demand insights."""
import asyncio
import csv
import io
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import jobs
from app.core.ratelimit import enforce
from app.core.security import new_api_key
from app.db import SessionLocal, get_db
from app.deps import current_user, merchant_owner
from app.models import ApiKey, CatalogItem, Click, Merchant, Search, User
from app.net.safe_fetch import UnsafeURL, safe_get, safe_outbound
from app.schemas import (
    ApiKeyIn,
    CatalogItemIn,
    CatalogUploadIn,
    MerchantIn,
    ShopifyImportIn,
)
from app.search import understand, visual
from app.search.providers.base import parse_price

router = APIRouter(prefix="/v1/merchant", tags=["merchant"])
VERIFY_PATH = "/.well-known/saasta-verify.txt"


def _owns(url: str, domain: str) -> bool:
    host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    return host == domain or host.endswith("." + domain)


def _public(m: Merchant) -> dict:
    return {"id": m.id, "name": m.name, "domain": m.domain, "domain_verified": m.domain_verified,
            "verify_url": f"https://{m.domain}{VERIFY_PATH}", "verify_token": m.verify_token,
            "country": m.country, "currency": m.currency, "plan": m.plan}


@router.post("", status_code=201)
async def register(body: MerchantIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    if (await db.execute(select(Merchant).where(Merchant.owner_id == user.id))).scalar_one_or_none():
        raise HTTPException(409, "You already registered a store")
    if (await db.execute(select(Merchant).where(Merchant.domain == body.domain))).scalar_one_or_none():
        raise HTTPException(409, "That domain is already registered")
    m = Merchant(owner_id=user.id, name=body.name, domain=body.domain, country=body.country,
                 currency=body.currency)
    user.role = "merchant" if user.role == "shopper" else user.role
    db.add(m)
    await db.commit()
    return _public(m)


@router.get("")
async def get_merchant(m: Merchant = Depends(merchant_owner)):
    return _public(m)


async def _dns_txt(domain: str) -> list[str]:
    # DNS-over-HTTPS keeps this dependency-free and avoids trusting the local resolver.
    async with httpx.AsyncClient(timeout=6, trust_env=False) as c:
        r = await c.get("https://cloudflare-dns.com/dns-query", params={"name": domain, "type": "TXT"},
                        headers={"accept": "application/dns-json"})
        r.raise_for_status()
        return [a.get("data", "").strip('"') for a in r.json().get("Answer", []) if a.get("type") == 16]


@router.post("/verify")
async def verify_domain(request: Request, m: Merchant = Depends(merchant_owner), db: AsyncSession = Depends(get_db)):
    """Prove control of the store, either way works:
    - DNS TXT record on the domain:  saasta-verify=<token>   (best for Shopify / hosted stores)
    - file at https://<domain>/.well-known/saasta-verify.txt containing <token>
    """
    await enforce(request, "verify", 10, 3600, subject=m.id)
    ok = False
    try:
        ok = f"saasta-verify={m.verify_token}" in await _dns_txt(m.domain)
    except httpx.HTTPError:
        pass
    if not ok:
        try:
            body, _, final = await safe_get(f"https://{m.domain}{VERIFY_PATH}", max_bytes=4096, accept="text/plain")
            ok = _owns(final, m.domain) and m.verify_token in body.decode(errors="ignore")
        except UnsafeURL:
            pass
    if not ok:
        raise HTTPException(400, "Verification not found yet. DNS changes can take a few minutes.")
    m.domain_verified = True
    await db.commit()
    return _public(m)


# ---------- API keys ----------

@router.post("/keys", status_code=201)
async def create_key(body: ApiKeyIn, m: Merchant = Depends(merchant_owner), db: AsyncSession = Depends(get_db)):
    active = await db.scalar(select(func.count()).select_from(ApiKey).where(
        ApiKey.merchant_id == m.id, ApiKey.revoked.is_(False)))
    if active >= 5:
        raise HTTPException(400, "Revoke an old key first (max 5 active)")
    raw, prefix, hashed = new_api_key()
    k = ApiKey(merchant_id=m.id, prefix=prefix, key_hash=hashed, label=body.label)
    db.add(k)
    await db.commit()
    return {"id": k.id, "key": raw, "prefix": prefix, "label": k.label,
            "note": "Copy this key now. It will not be shown again."}


@router.get("/keys")
async def list_keys(m: Merchant = Depends(merchant_owner), db: AsyncSession = Depends(get_db)):
    keys = (await db.execute(select(ApiKey).where(ApiKey.merchant_id == m.id))).scalars().all()
    return [{"id": k.id, "prefix": k.prefix, "label": k.label, "revoked": k.revoked,
             "last_used_at": k.last_used_at, "created_at": k.created_at} for k in keys]


@router.delete("/keys/{key_id}", status_code=204)
async def revoke_key(key_id: str, m: Merchant = Depends(merchant_owner), db: AsyncSession = Depends(get_db)):
    k = await db.get(ApiKey, key_id)
    if not k or k.merchant_id != m.id:
        raise HTTPException(404, "Not found")
    k.revoked = True
    await db.commit()


# ---------- Catalog ----------

def _require_verified(m: Merchant):
    if not m.domain_verified:
        raise HTTPException(403, "Verify your domain before syncing products")


async def _upsert(m: Merchant, items: list[CatalogItemIn]) -> dict:
    accepted, rejected = 0, []
    async with SessionLocal() as db:
        for it in items:
            url, img = safe_outbound(it.url), safe_outbound(it.image_url)
            if not url or not img or not _owns(url, m.domain):
                rejected.append({"id": it.external_id, "reason": "product url must be on your verified domain"})
                continue
            row = (await db.execute(select(CatalogItem).where(
                CatalogItem.merchant_id == m.id, CatalogItem.external_id == it.external_id))).scalar_one_or_none()
            if row is None:
                row = CatalogItem(merchant_id=m.id, external_id=it.external_id)
                db.add(row)
            changed_img = row.image_url != img
            row.title, row.url, row.image_url = it.title, url, img
            row.price, row.currency = it.price, it.currency or m.currency
            row.category = it.category or understand.categorize([it.title])
            row.in_stock = it.in_stock
            if changed_img:
                row.phash, row.embedding = None, None
            accepted += 1
        await db.commit()
    jobs.spawn(_fingerprint_pending(m.id))
    return {"accepted": accepted, "rejected": rejected[:50], "rejected_count": len(rejected)}


async def _fingerprint_pending(merchant_id: str) -> None:
    sem = asyncio.Semaphore(6)
    async with SessionLocal() as db:
        rows = (await db.execute(select(CatalogItem).where(
            CatalogItem.merchant_id == merchant_id, CatalogItem.phash.is_(None)).limit(5000))).scalars().all()

        async def one(row: CatalogItem):
            async with sem:
                try:
                    data, ctype, _ = await safe_get(row.image_url, 4_000_000, "image/*", timeout=10)
                    if ctype.startswith("image/") and (fp := visual.fingerprint_bytes(data)):
                        row.phash, row.embedding = fp["phash"], visual.hist_to_bytes(fp["hist"])
                except Exception:
                    pass

        await asyncio.gather(*(one(r) for r in rows))
        await db.commit()


@router.post("/catalog")
async def upload_json(body: CatalogUploadIn, m: Merchant = Depends(merchant_owner)):
    _require_verified(m)
    return await _upsert(m, body.items)


@router.post("/catalog/csv")
async def upload_csv(file: UploadFile = File(...), m: Merchant = Depends(merchant_owner)):
    """Google Merchant Center style feed: id,title,link,image_link,price,availability,product_type"""
    _require_verified(m)
    raw = await file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, "Feed too large (5 MB max, split it)")
    text = raw.decode("utf-8-sig", errors="replace")
    dialect = "excel-tab" if text.split("\n", 1)[0].count("\t") > 2 else "excel"
    items, errors = [], 0
    for row in csv.DictReader(io.StringIO(text), dialect=dialect):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        price, cur = parse_price(row.get("sale_price") or row.get("price"))
        try:
            items.append(CatalogItemIn(
                external_id=row.get("id", "")[:128], title=row.get("title", "")[:300],
                url=row.get("link", ""), image_url=row.get("image_link", ""), price=price, currency=cur,
                category=understand.categorize([row.get("product_type", ""), row.get("title", "")]),
                in_stock=row.get("availability", "in stock").lower() != "out of stock",
            ))
        except Exception:
            errors += 1
        if len(items) >= 10_000:
            break
    res = await _upsert(m, items)
    res["parse_errors"] = errors
    return res


@router.post("/catalog/shopify")
async def import_shopify(body: ShopifyImportIn, request: Request, m: Merchant = Depends(merchant_owner)):
    """Pull the public /products.json of a verified Shopify store. No app install needed."""
    _require_verified(m)
    await enforce(request, "shopify", 6, 3600, subject=m.id)
    items: list[CatalogItemIn] = []
    page = 1
    while len(items) < body.max_products and page <= 20:
        try:
            raw, _, _ = await safe_get(f"https://{m.domain}/products.json?limit=250&page={page}",
                                       max_bytes=8_000_000, accept="application/json")
            products = json.loads(raw).get("products", [])
        except (UnsafeURL, ValueError) as e:
            raise HTTPException(400, f"Could not read Shopify catalog: {e}")
        if not products:
            break
        for p in products:
            variants = p.get("variants") or [{}]
            imgs = p.get("images") or []
            if not imgs:
                continue
            price, _ = parse_price(variants[0].get("price"))
            items.append(CatalogItemIn(
                external_id=str(p.get("id"))[:128], title=(p.get("title") or "")[:300],
                url=f"https://{m.domain}/products/{p.get('handle')}", image_url=imgs[0].get("src", ""),
                price=price, currency=m.currency,
                category=understand.categorize([p.get("product_type") or "", p.get("title") or ""]),
                in_stock=any(v.get("available", True) for v in variants),
            ))
        page += 1
    return await _upsert(m, items[: body.max_products])


@router.get("/catalog")
async def list_catalog(offset: int = 0, m: Merchant = Depends(merchant_owner), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(CatalogItem).where(CatalogItem.merchant_id == m.id)
                             .order_by(CatalogItem.updated_at.desc()).offset(max(0, offset)).limit(50))).scalars().all()
    total = await db.scalar(select(func.count()).select_from(CatalogItem).where(CatalogItem.merchant_id == m.id))
    indexed = await db.scalar(select(func.count()).select_from(CatalogItem).where(
        CatalogItem.merchant_id == m.id, CatalogItem.phash.is_not(None)))
    return {"total": total, "indexed": indexed, "items": [
        {"id": r.id, "external_id": r.external_id, "title": r.title, "url": r.url, "image_url": r.image_url,
         "price": r.price, "currency": r.currency, "category": r.category, "in_stock": r.in_stock,
         "indexed": r.phash is not None} for r in rows]}


# ---------- Analytics & insights ----------

@router.get("/analytics")
async def analytics(days: int = 30, m: Merchant = Depends(merchant_owner), db: AsyncSession = Depends(get_db)):
    days = max(1, min(days, 90))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    clicks = (await db.execute(select(Click).where(
        Click.merchant_id == m.id, Click.created_at >= since))).scalars().all()
    widget_searches = await db.scalar(select(func.count()).select_from(Search).where(
        Search.merchant_id == m.id, Search.created_at >= since))
    by_day = Counter(c.created_at.date().isoformat() for c in clicks)
    top = Counter(c.url for c in clicks).most_common(10)
    return {"days": days, "clicks": len(clicks), "widget_searches": widget_searches,
            "by_day": sorted(by_day.items()), "top_products": [{"url": u, "clicks": n} for u, n in top]}


@router.get("/insights")
async def insights(days: int = 30, m: Merchant = Depends(merchant_owner), db: AsyncSession = Depends(get_db)):
    """Demand radar: what shoppers in your country look for, what they couldn't find, and at what price.

    Aggregated and anonymous: no shopper identity, images, or individual searches are exposed.
    """
    days = max(7, min(days, 90))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (await db.execute(select(Search.category, Search.best_price, Search.result).where(
        Search.country == m.country, Search.status == "done", Search.merchant_id.is_(None),
        Search.created_at >= since).limit(20_000))).all()
    cats: Counter = Counter()
    unmet: Counter = Counter()
    colors: Counter = Counter()
    prices: dict[str, list[float]] = {}
    for cat, best, result in rows:
        if not cat:
            continue
        cats[cat] += 1
        if best:
            prices.setdefault(cat, []).append(best)
        res = result or {}
        if res.get("kind") == "video" and res.get("looks"):
            res = res["looks"][0]
        u = res.get("understanding") or {}
        if u.get("color"):
            colors[(cat, u["color"])] += 1
        if not res.get("exact") and u.get("query"):
            unmet[(cat, u["query"].lower()[:60])] += 1

    def band(v: list[float]):
        v = sorted(v)
        return {"p25": v[len(v) // 4], "median": v[len(v) // 2], "p75": v[(3 * len(v)) // 4]} if len(v) >= 5 else None

    k_anon = 3  # never surface a query fewer than 3 people searched
    return {
        "window_days": days, "country": m.country, "total_searches": len(rows),
        "top_categories": [{"category": c, "searches": n, "price_band": band(prices.get(c, []))}
                           for c, n in cats.most_common(8)],
        "unmet_demand": [{"category": c, "query": q, "searches": n}
                         for (c, q), n in unmet.most_common(30) if n >= k_anon][:15],
        "trending_colors": [{"category": c, "color": col, "searches": n}
                            for (c, col), n in colors.most_common(12) if n >= k_anon],
    }
