"""Client for Saasta's own ML service (apps/ml). No third-party AI APIs are used anywhere."""
import base64
import logging

import httpx
import numpy as np

from app.core.config import get_settings

log = logging.getLogger("saasta.ml")


class MLUnavailable(RuntimeError):
    pass


def _headers() -> dict:
    return {"Authorization": f"Bearer {get_settings().ml_token}"}


async def _post(path: str, payload: dict, timeout: float | None = None) -> dict:
    s = get_settings()
    if not s.ml_url:
        raise MLUnavailable("ML service not configured")
    try:
        async with httpx.AsyncClient(timeout=timeout or s.ml_timeout_s, trust_env=False) as c:
            r = await c.post(f"{s.ml_url}{path}", json=payload, headers=_headers())
    except httpx.HTTPError as e:
        raise MLUnavailable(type(e).__name__) from e
    if r.status_code >= 500:
        raise MLUnavailable(f"ML {r.status_code}")
    if r.status_code >= 400:
        raise ValueError(r.json().get("detail", "ML request rejected"))
    return r.json()


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _vecs(rows: list[list[float]]) -> np.ndarray:
    return np.asarray(rows, dtype=np.float32)


async def embed_images(jpegs: list[bytes]) -> np.ndarray:
    """Unit-normalised fashion embeddings, shape (n, d)."""
    if not jpegs:
        return np.zeros((0, 0), dtype=np.float32)
    return _vecs((await _post("/v1/embed/images", {"images": [_b64(j) for j in jpegs]}, 60))["vectors"])


async def embed_texts(texts: list[str]) -> np.ndarray:
    return _vecs((await _post("/v1/embed/texts", {"texts": texts}))["vectors"])


async def tryon(person: bytes, garment: bytes, category: str) -> bytes:
    s = get_settings()
    d = await _post("/v1/tryon", {"person": _b64(person), "garment": _b64(garment), "category": category},
                    s.tryon_timeout_s)
    return base64.b64decode(d["image"])


async def place(person: bytes, product: bytes, kind: str) -> bytes:
    d = await _post("/v1/place", {"person": _b64(person), "product": _b64(product), "kind": kind}, 120)
    return base64.b64decode(d["image"])


async def health() -> dict | None:
    s = get_settings()
    if not s.ml_url:
        return None
    try:
        async with httpx.AsyncClient(timeout=3, trust_env=False) as c:
            r = await c.get(f"{s.ml_url}/health")
            return r.json() if r.status_code == 200 else None
    except httpx.HTTPError:
        return None


def to_f16(v: np.ndarray) -> bytes:
    return v.astype(np.float16).tobytes()


def from_f16(b: bytes) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float16).astype(np.float32)
