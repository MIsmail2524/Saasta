"""Shopper features: history, price-drop watches, shareable look boards."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import current_user
from app.models import Board, Search, User, Watch
from app.net.safe_fetch import safe_outbound
from app.schemas import BoardIn, WatchIn

router = APIRouter(prefix="/v1/me", tags=["me"])


@router.get("/history")
async def history(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Search).where(Search.user_id == user.id)
                             .order_by(Search.created_at.desc()).limit(50))).scalars().all()
    return [{"id": s.id, "kind": s.kind, "status": s.status, "image": s.media_key, "category": s.category,
             "best_price": s.best_price, "query": ((s.result or {}).get("understanding") or {}).get("query"),
             "created_at": s.created_at} for s in rows]


@router.delete("/history", status_code=204)
async def clear_history(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Search).where(Search.user_id == user.id))).scalars().all()
    for s in rows:
        s.user_id = None  # detach; anonymous aggregate stats remain
    await db.commit()


@router.get("/watches")
async def list_watches(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Watch).where(Watch.user_id == user.id, Watch.active.is_(True))
                             .order_by(Watch.created_at.desc()))).scalars().all()
    return [{"id": w.id, "title": w.title, "url": w.url, "image_url": w.image_url, "last_price": w.last_price,
             "target_price": w.target_price, "currency": w.currency, "history": w.history or []} for w in rows]


@router.post("/watches", status_code=201)
async def add_watch(body: WatchIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    if not (url := safe_outbound(body.url)):
        raise HTTPException(422, "Invalid link")
    n = await db.scalar(select(func.count()).select_from(Watch).where(Watch.user_id == user.id, Watch.active.is_(True)))
    if n >= 50:
        raise HTTPException(400, "Watch limit reached (50)")
    w = Watch(user_id=user.id, title=body.title, url=url, image_url=safe_outbound(body.image_url),
              target_price=body.target_price, last_price=body.price, currency=body.currency,
              history=[{"price": body.price}] if body.price else [])
    db.add(w)
    await db.commit()
    return {"id": w.id}


@router.delete("/watches/{watch_id}", status_code=204)
async def remove_watch(watch_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    w = await db.get(Watch, watch_id)
    if not w or w.user_id != user.id:
        raise HTTPException(404, "Not found")
    w.active = False
    await db.commit()


def _clean_items(items: list[dict]) -> list[dict]:
    out = []
    for it in items:
        url = safe_outbound(str(it.get("url", "")))
        if not url:
            continue
        out.append({"title": str(it.get("title", ""))[:300], "url": url,
                    "image": safe_outbound(str(it.get("image") or "")),
                    "price": it.get("price_local") if isinstance(it.get("price_local"), (int, float)) else None,
                    "domain": str(it.get("domain", ""))[:253]})
    return out


@router.get("/boards")
async def list_boards(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Board).where(Board.user_id == user.id))).scalars().all()
    return [{"id": b.id, "title": b.title, "public": b.public, "count": len(b.items or [])} for b in rows]


@router.post("/boards", status_code=201)
async def create_board(body: BoardIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    b = Board(user_id=user.id, title=body.title, public=body.public, note=body.note, items=_clean_items(body.items))
    db.add(b)
    await db.commit()
    return {"id": b.id}


@router.put("/boards/{board_id}")
async def update_board(board_id: str, body: BoardIn, user: User = Depends(current_user),
                       db: AsyncSession = Depends(get_db)):
    b = await db.get(Board, board_id)
    if not b or b.user_id != user.id:
        raise HTTPException(404, "Not found")
    b.title, b.public, b.note, b.items = body.title, body.public, body.note, _clean_items(body.items)
    await db.commit()
    return {"id": b.id}


public = APIRouter(prefix="/v1/boards", tags=["boards"])


@public.get("/{board_id}")
async def view_board(board_id: str, db: AsyncSession = Depends(get_db)):
    b = await db.get(Board, board_id)
    if not b or not b.public:
        raise HTTPException(404, "Not found")
    total = sum(i["price"] for i in b.items if i.get("price"))
    return {"id": b.id, "title": b.title, "note": b.note, "items": b.items, "total": total}
