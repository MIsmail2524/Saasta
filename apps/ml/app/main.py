"""Saasta ML service: our own fashion embeddings and try-on. Internal network only, token protected."""
import asyncio
import base64
import binascii
import hmac
import logging
from contextlib import asynccontextmanager

import torch
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app import embed, garment, place, pose
from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("saasta.ml")
MAX_IMAGE_B64 = 14_000_000  # ~10 MB decoded
_tryon_slots = asyncio.Semaphore(1)


@asynccontextmanager
async def lifespan(_: FastAPI):
    s = settings()
    if s.token == "dev-ml-token" and not s.dev:  # noqa: S105
        raise RuntimeError("Set SAASTA_ML_TOKEN (or SAASTA_ML_DEV=1 for local development)")
    if s.threads:
        torch.set_num_threads(s.threads)
    await run_in_threadpool(embed.texts, ["warm up"])  # load the embedding model at boot
    log.info("embedding model ready")
    yield


app = FastAPI(title="Saasta ML", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


def auth(authorization: str = Header(default="")):
    expected = f"Bearer {settings().token}"
    if not hmac.compare_digest(authorization.encode(), expected.encode()):
        raise HTTPException(401, "unauthorized")


def _decode(b64: str) -> bytes:
    if len(b64) > MAX_IMAGE_B64:
        raise HTTPException(413, "image too large")
    try:
        return base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(422, "invalid image encoding")


class ImagesIn(BaseModel):
    images: list[str] = Field(min_length=1, max_length=32)


class TextsIn(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=128)


class TryOnIn(BaseModel):
    person: str
    garment: str
    category: str = Field(pattern=r"^(tops|bottoms|one-pieces)$")


class PlaceIn(BaseModel):
    person: str
    product: str
    kind: str = Field(pattern=r"^(jewellery|necklace|earrings|eyewear|watches|bags|shoes)$")


@app.get("/health")
async def health():
    return {"ok": True, "embed_loaded": embed.loaded(), "tryon_weights": garment.available(),
            "pose_weights": pose.available(), "device": "cuda" if torch.cuda.is_available() else "cpu"}


@app.post("/v1/embed/images", dependencies=[Depends(auth)])
async def embed_images(body: ImagesIn):
    imgs = [_decode(b) for b in body.images]
    try:
        vecs = await run_in_threadpool(embed.images, imgs)
    except OSError:
        raise HTTPException(422, "unreadable image")
    return {"vectors": vecs.round(6).tolist(), "dim": int(vecs.shape[1])}


@app.post("/v1/embed/texts", dependencies=[Depends(auth)])
async def embed_texts(body: TextsIn):
    vecs = await run_in_threadpool(embed.texts, [t[:300] for t in body.texts])
    return {"vectors": vecs.round(6).tolist(), "dim": int(vecs.shape[1])}


@app.post("/v1/tryon", dependencies=[Depends(auth)])
async def tryon(body: TryOnIn):
    if not garment.available():
        raise HTTPException(503, "try-on weights not installed")
    async with _tryon_slots:
        out = await run_in_threadpool(garment.generate, _decode(body.person), _decode(body.garment), body.category)
    return {"image": base64.b64encode(out).decode()}


@app.post("/v1/place", dependencies=[Depends(auth)])
async def place_accessory(body: PlaceIn):
    if not pose.available():
        raise HTTPException(503, "pose weights not installed")
    try:
        out = await run_in_threadpool(place.place, _decode(body.person), _decode(body.product), body.kind)
    except place.PlacementError as e:
        raise HTTPException(422, str(e))
    return {"image": base64.b64encode(out).decode()}
