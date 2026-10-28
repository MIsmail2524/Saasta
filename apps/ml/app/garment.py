"""Garment try-on (tops, bottoms, one-pieces) on self-hosted FASHN VTON v1.5 weights (Apache-2.0).

Runs inside our ML service: photos never leave our servers. GPU recommended (bf16 on Ampere+);
CPU works in float32 but takes minutes per image, so the API runs it as a background job.
"""
import io
import os
import threading

from PIL import Image

from app.config import settings

_lock = threading.Lock()   # one generation at a time per process keeps memory predictable
_pipe = None
CATEGORIES = {"tops", "bottoms", "one-pieces"}


def available() -> bool:
    return os.path.exists(os.path.join(settings().tryon_weights, "model.safetensors"))


def _load():
    global _pipe
    if _pipe is None:
        from fashn_vton import TryOnPipeline

        _pipe = TryOnPipeline(weights_dir=settings().tryon_weights)
    return _pipe


def generate(person_jpeg: bytes, garment_jpeg: bytes, category: str) -> bytes:
    if category not in CATEGORIES:
        raise ValueError(f"category must be one of {sorted(CATEGORIES)}")
    person = Image.open(io.BytesIO(person_jpeg)).convert("RGB")
    garment = Image.open(io.BytesIO(garment_jpeg)).convert("RGB")
    with _lock:
        pipe = _load()
        result = pipe(person_image=person, garment_image=garment, category=category)
    out = io.BytesIO()
    result.images[0].convert("RGB").save(out, "JPEG", quality=92)
    return out.getvalue()
