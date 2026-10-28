"""In-process vector index over Saasta's own catalog.

Brute-force cosine search over a float32 matrix: ~5 ms per query at 200k items on one CPU core.
Refreshed incrementally from the database. Swap for pgvector/FAISS HNSW past a few million items.
"""
import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
from sqlalchemy import select

from app.db import SessionLocal
from app.ml_client import from_f16
from app.models import CatalogItem

REFRESH_S = 60


@dataclass
class _State:
    ids: list[str] = field(default_factory=list)
    pos: dict[str, int] = field(default_factory=dict)
    mat: np.ndarray = field(default_factory=lambda: np.zeros((0, 0), dtype=np.float32))
    cat: list[str | None] = field(default_factory=list)
    merchant: list[str | None] = field(default_factory=list)
    alive: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=bool))
    since: datetime | None = None
    checked: float = 0.0


_s = _State()
_lock = asyncio.Lock()


async def refresh(force: bool = False) -> None:
    if not force and time.time() - _s.checked < REFRESH_S:
        return
    async with _lock:
        if not force and time.time() - _s.checked < REFRESH_S:
            return
        async with SessionLocal() as db:
            stmt = select(CatalogItem.id, CatalogItem.vec, CatalogItem.category, CatalogItem.merchant_id,
                          CatalogItem.in_stock, CatalogItem.updated_at).where(CatalogItem.vec.is_not(None))
            if _s.since:
                stmt = stmt.where(CatalogItem.updated_at >= _s.since)
            rows = (await db.execute(stmt)).all()
        new_vecs, newest = [], _s.since
        for id_, vec, cat, mid, stock, upd in rows:
            v = from_f16(vec)
            if _s.mat.size and v.shape[0] != _s.mat.shape[1]:
                continue  # model changed; reindex job will rewrite these
            if id_ in _s.pos:
                i = _s.pos[id_]
                _s.mat[i], _s.cat[i], _s.merchant[i], _s.alive[i] = v, cat, mid, bool(stock)
            else:
                _s.pos[id_] = len(_s.ids) + len(new_vecs)
                new_vecs.append((id_, v, cat, mid, bool(stock)))
            newest = upd if newest is None or upd > newest else newest
        if new_vecs:
            add = np.stack([v for _, v, *_ in new_vecs])
            _s.mat = add if not _s.mat.size else np.vstack([_s.mat, add])
            _s.ids += [i for i, *_ in new_vecs]
            _s.cat += [c for *_, c, _, _ in new_vecs]
            _s.merchant += [m for *_, m, _ in new_vecs]
            _s.alive = np.concatenate([_s.alive, np.array([a for *_, a in new_vecs], dtype=bool)])
        _s.since = newest
        _s.checked = time.time()


def size() -> int:
    return int(_s.alive.sum()) if _s.alive.size else 0


async def search(q: np.ndarray, k: int = 120, category: str | None = None,
                 merchant_id: str | None = None) -> list[tuple[str, float]]:
    await refresh()
    if not _s.mat.size:
        return []
    scores = _s.mat @ q.astype(np.float32)
    mask = _s.alive.copy()
    if merchant_id:
        mask &= np.array([m == merchant_id for m in _s.merchant])
    if category:
        # keep same-category items, plus uncategorised ones
        mask &= np.array([c in (category, None) for c in _s.cat])
    scores = np.where(mask, scores, -1.0)
    k = min(k, int(mask.sum()))
    if k <= 0:
        return []
    top = np.argpartition(-scores, k - 1)[:k]
    top = top[np.argsort(-scores[top])]
    return [(_s.ids[i], float(scores[i])) for i in top]


def reset() -> None:
    global _s
    _s = _State()
