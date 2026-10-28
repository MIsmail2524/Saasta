"""Operator CLI (runs on the server, never exposed over HTTP).

  python -m app.admin set-plan mystore.pk growth
  python -m app.admin verify mystore.pk
  python -m app.admin stats
  python -m app.admin add-sites app/crawl/seeds.txt   # one domain per line
  python -m app.admin crawl khaadi.com               # crawl + index one site now
  python -m app.admin index                          # embed everything not yet indexed
  python -m app.admin export-training out.jsonl      # opted-in products -> embedding fine-tune data
  python -m app.admin export-training-stores out.txt # opted-in store domains -> try-on dataset builder
"""
import asyncio
import json
import sys

from sqlalchemy import func, select

from app.crawl.crawler import crawl_site
from app.db import SessionLocal, init_db
from app.indexer import index_pending
from app.models import CatalogItem, Click, CrawlSite, Merchant, Search, User
from app.plans import PLANS


async def _merchant(db, domain: str) -> Merchant:
    m = (await db.execute(select(Merchant).where(Merchant.domain == domain.lower()))).scalar_one_or_none()
    if not m:
        sys.exit(f"no store with domain {domain}")
    return m


async def main(argv: list[str]) -> None:
    await init_db()
    async with SessionLocal() as db:
        match argv:
            case ["set-plan", domain, plan] if plan in PLANS:
                m = await _merchant(db, domain)
                m.plan = plan
                await db.commit()
                print(f"{m.domain}: plan={plan}")
            case ["verify", domain]:
                m = await _merchant(db, domain)
                m.domain_verified = True
                await db.commit()
                print(f"{m.domain}: verified")
            case ["add-sites", path]:
                added = 0
                for line in open(path, encoding="utf-8"):
                    d = line.split("#")[0].strip().lower().removeprefix("www.")
                    if d and not await db.get(CrawlSite, d):
                        db.add(CrawlSite(domain=d))
                        added += 1
                await db.commit()
                print(f"added {added} sites")
            case ["crawl", domain]:
                d = domain.lower().removeprefix("www.")
                if not await db.get(CrawlSite, d):
                    db.add(CrawlSite(domain=d))
                    await db.commit()
                print(await crawl_site(d))
                print(f"indexed {await index_pending(limit=10_000, domain=d)} items")
            case ["index"]:
                print(f"indexed {await index_pending(limit=100_000)} items")
            case ["export-training", path]:
                rows = (await db.execute(select(CatalogItem).where(CatalogItem.allow_training.is_(True)))).scalars()
                n = 0
                with open(path, "w", encoding="utf-8") as f:
                    for r in rows:
                        text = " ".join(x for x in [r.color, r.title, r.category] if x)
                        f.write(json.dumps({"image_url": r.image_url, "text": text[:200], "id": r.id}) + "\n")
                        n += 1
                print(f"exported {n} opted-in products")
            case ["export-training-stores", path]:
                stores = (await db.execute(select(Merchant.domain).where(
                    Merchant.allow_training.is_(True), Merchant.kind == "store",
                    Merchant.domain_verified.is_(True)))).scalars().all()
                with open(path, "w", encoding="utf-8") as f:
                    f.write("\n".join(stores) + "\n")
                print(f"exported {len(stores)} opted-in stores")
            case ["stats"]:
                for name, model in (("users", User), ("stores", Merchant), ("products", CatalogItem),
                                    ("sites", CrawlSite),
                                    ("searches", Search), ("clicks", Click)):
                    print(f"{name:10} {await db.scalar(select(func.count()).select_from(model))}")
            case _:
                sys.exit(__doc__)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
