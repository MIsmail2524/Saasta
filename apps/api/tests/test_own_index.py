"""Own-index search path with a deterministic stand-in for the ML service."""
import asyncio

import numpy as np
import pytest
from sqlalchemy import update

from app import ml_client
from app.crawl.extract import extract_product
from app.db import SessionLocal
from app.models import CatalogItem, Merchant
from app.search import index, labels
from tests.conftest import jpeg, signup

DIM = 16


def _unit(seed: int) -> np.ndarray:
    v = np.random.default_rng(seed).normal(size=DIM).astype(np.float32)
    return v / np.linalg.norm(v)


@pytest.fixture
def fake_ml(monkeypatch):
    """Images embed by their mean colour; texts embed by hash. Enough to test ranking and plumbing."""
    import io

    from PIL import Image

    async def embed_images(jpegs):
        out = []
        for j in jpegs:
            r, g, b = np.asarray(Image.open(io.BytesIO(j)).convert("RGB")).reshape(-1, 3).mean(0) / 255
            v = np.zeros(DIM, dtype=np.float32)
            v[:3] = [r, g, b]
            v[3] = 0.2
            out.append(v / np.linalg.norm(v))
        return np.stack(out)

    async def embed_texts(texts):
        return np.stack([_unit(abs(hash(t)) % 10_000) for t in texts])

    monkeypatch.setattr(ml_client, "embed_images", embed_images)
    monkeypatch.setattr(ml_client, "embed_texts", embed_texts)
    labels._cache.clear()
    index.reset()
    yield
    labels._cache.clear()
    index.reset()


async def test_vector_search_ranks_closest_product_first(client, fake_ml):
    await signup(client, "vec@example.com")
    await client.post("/v1/merchant", json={"name": "Vec Shop", "domain": "vecshop.pk"})
    async with SessionLocal() as db:
        await db.execute(update(Merchant).where(Merchant.domain == "vecshop.pk").values(domain_verified=True))
        await db.commit()
    await client.post("/v1/merchant/catalog", json={"items": [
        {"external_id": "green", "title": "Green kurta", "url": "https://vecshop.pk/p/g",
         "image_url": "https://vecshop.pk/g.jpg", "price": 4000},
        {"external_id": "blue", "title": "Blue kurta", "url": "https://vecshop.pk/p/b",
         "image_url": "https://vecshop.pk/b.jpg", "price": 3000},
    ]})
    # index directly (no network in tests)
    green, blue = (await ml_client.embed_images([jpeg(color=(20, 160, 60)), jpeg(color=(30, 60, 200))]))
    async with SessionLocal() as db:
        await db.execute(update(CatalogItem).where(CatalogItem.external_id == "green")
                         .values(vec=ml_client.to_f16(green)))
        await db.execute(update(CatalogItem).where(CatalogItem.external_id == "blue")
                         .values(vec=ml_client.to_f16(blue)))
        await db.commit()
    await index.refresh(force=True)

    client.cookies.clear()
    sid = (await client.post("/v1/searches", files={"file": ("q.jpg", jpeg(color=(25, 150, 70)), "image/jpeg")})).json()["id"]
    for _ in range(50):
        res = (await client.get(f"/v1/searches/{sid}")).json()
        if res["status"] in ("done", "failed"):
            break
        await asyncio.sleep(0.1)
    assert res["status"] == "done", res
    r = res["result"]
    assert r["sources"]["engine"] == "model"
    top = (r["exact"] + r["similar"])[0]
    assert top["title"] == "Green kurta" and top["partner"] is True


def test_extract_product_jsonld_and_og():
    page = """<script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"Product",
      "name":"Mirror work kurta","image":["https://s.pk/a.jpg"],"brand":{"name":"S"},"sku":"K1",
      "offers":{"@type":"Offer","price":"5490","priceCurrency":"PKR","availability":"https://schema.org/InStock"},
      "aggregateRating":{"ratingValue":"4.6","reviewCount":"31"}}]}</script>"""
    p = extract_product(page)
    assert p["title"] == "Mirror work kurta" and p["price"] == 5490 and p["currency"] == "PKR"
    assert p["rating"] == 4.6 and p["reviews"] == 31 and p["in_stock"] and p["brand"] == "S"
    og = '<meta property="og:type" content="product"><meta property="og:title" content="Khussa">' \
         '<meta property="og:image" content="https://s.pk/k.jpg"><meta property="product:price:amount" content="2,999">'
    assert extract_product(og)["price"] == 2999


async def test_robots_txt_is_obeyed(monkeypatch):
    from app.crawl import crawler

    async def fake_get(url, max_bytes, accept="*/*", timeout=15.0):
        if url.endswith("/robots.txt"):
            return b"User-agent: SaastaBot\nDisallow: /\n", "text/plain", url
        raise AssertionError(f"crawler fetched {url} despite robots.txt")

    monkeypatch.setattr(crawler, "safe_get", fake_get)
    res = await crawler.crawl_site("blocked-shop.pk")
    assert res["error"] == "blocked by robots.txt" and res["products"] == 0
