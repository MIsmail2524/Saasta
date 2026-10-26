"""Operator CLI (runs on the server, never exposed over HTTP).

  python -m app.admin set-plan mystore.pk growth
  python -m app.admin verify mystore.pk
  python -m app.admin stats
"""
import asyncio
import sys

from sqlalchemy import func, select

from app.db import SessionLocal, init_db
from app.models import CatalogItem, Click, Merchant, Search, User
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
            case ["stats"]:
                for name, model in (("users", User), ("stores", Merchant), ("products", CatalogItem),
                                    ("searches", Search), ("clicks", Click)):
                    print(f"{name:10} {await db.scalar(select(func.count()).select_from(model))}")
            case _:
                sys.exit(__doc__)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
