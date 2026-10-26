"""Cheap, dependency-light visual similarity: perceptual hash + colour histogram.

Good enough to re-rank provider results and match partner catalogs at MVP scale.
`embed()` is the single seam to swap in a CLIP/SigLIP model later.
"""
import io

import imagehash
import numpy as np
from PIL import Image


def fingerprint(img: Image.Image) -> dict:
    img = img.convert("RGB")
    crop = _center(img)
    hsv = np.asarray(crop.convert("HSV").resize((64, 64)), dtype=np.float32)
    hist, _ = np.histogramdd(
        hsv.reshape(-1, 3), bins=(12, 4, 4), range=((0, 256), (0, 256), (0, 256))
    )
    hist = hist.flatten()
    hist /= hist.sum() or 1
    return {"phash": str(imagehash.phash(crop)), "hist": hist.astype(np.float32)}


def _center(img: Image.Image) -> Image.Image:
    # Product photos usually center the item; trimming borders cuts background noise.
    w, h = img.size
    return img.crop((int(w * 0.1), int(h * 0.1), int(w * 0.9), int(h * 0.9)))


def similarity(a: dict, b: dict) -> float:
    ph = 1 - (imagehash.hex_to_hash(a["phash"]) - imagehash.hex_to_hash(b["phash"])) / 64
    col = float(np.minimum(a["hist"], b["hist"]).sum())  # histogram intersection, 0..1
    return round(0.45 * ph + 0.55 * col, 4)


def fingerprint_bytes(data: bytes) -> dict | None:
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.draft("RGB", (256, 256))
            return fingerprint(im)
    except Exception:
        return None


def hist_to_bytes(h: np.ndarray) -> bytes:
    return h.astype(np.float32).tobytes()


def hist_from_bytes(b: bytes) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float32)


COLORS = {
    "black": (0, 0, 0), "white": (245, 245, 245), "grey": (128, 128, 128), "red": (200, 30, 40),
    "maroon": (110, 20, 30), "pink": (240, 150, 180), "orange": (240, 130, 30),
    "yellow": (240, 210, 50), "mustard": (200, 160, 40), "green": (40, 140, 60),
    "olive": (110, 110, 40), "teal": (0, 128, 128), "blue": (40, 80, 200), "navy": (20, 30, 80),
    "purple": (110, 50, 150), "beige": (220, 200, 165), "brown": (120, 75, 40), "gold": (212, 175, 55),
    "silver": (192, 192, 192),
}


def dominant_color(img: Image.Image) -> str:
    small = np.asarray(_center(img.convert("RGB")).resize((48, 48)), dtype=np.float32).reshape(-1, 3)
    # ignore near-white studio backgrounds
    mask = small.min(axis=1) < 235
    px = small[mask] if mask.sum() > 50 else small
    mean = px.mean(axis=0)
    return min(COLORS, key=lambda c: float(np.sum((np.array(COLORS[c]) - mean) ** 2)))
