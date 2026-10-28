"""Accessory try-on: cut the product out of its studio photo and place it on the person by body pose.

Covers what garment try-on models can't: jewellery, earrings, glasses, watches, bags and shoes.
Pure geometry + our own cut-out; deterministic and fast on CPU.
"""
import io

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from app import pose

NOSE, L_EYE, R_EYE, L_EAR, R_EAR, L_SH, R_SH, L_EL, R_EL, L_WR, R_WR, L_HIP, R_HIP, L_KN, R_KN, L_AN, R_AN = range(17)


class PlacementError(ValueError):
    pass


def cutout(img: Image.Image) -> Image.Image:
    """Remove a plain studio background. Returns RGBA cropped to the product."""
    rgb = np.asarray(img.convert("RGB"), dtype=np.float32)
    h, w = rgb.shape[:2]
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    bg = np.median(border, axis=0)
    spread = np.linalg.norm(border - bg, axis=1)
    if np.percentile(spread, 80) > 40:
        raise PlacementError("Use a product photo on a plain background for accessory try-on")
    thr = max(18.0, float(np.percentile(spread, 95)) * 1.5)
    dist = np.linalg.norm(rgb - bg, axis=2)
    near_bg = Image.fromarray(((dist <= thr) * 255).astype(np.uint8))
    # flood-fill background from the border so holes inside the product (e.g. a white stone) survive
    filled = near_bg.copy()
    for seed in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0), (w // 2, h - 1), (0, h // 2), (w - 1, h // 2)]:
        if filled.getpixel(seed) == 255:
            ImageDraw.floodfill(filled, seed, 128)
    alpha = np.where(np.asarray(filled) == 128, 0, 255).astype(np.uint8)
    mask = Image.fromarray(alpha).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    bbox = mask.getbbox()
    if not bbox or (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) < 0.01 * w * h:
        raise PlacementError("Couldn't find the product in that photo")
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out.crop(bbox)


def _paste(base: Image.Image, item: Image.Image, center: tuple[float, float], width: float,
           angle: float = 0.0, anchor: str = "center") -> None:
    width = max(8, int(width))
    height = max(8, int(item.height * width / item.width))
    it = item.resize((width, height), Image.LANCZOS)
    if abs(angle) > 1:
        it = it.rotate(-angle, resample=Image.BICUBIC, expand=True)
    x = center[0] - it.width / 2
    y = center[1] - (it.height / 2 if anchor == "center" else 0)
    shadow = Image.new("RGBA", it.size, (0, 0, 0, 0))
    shadow.putalpha(it.getchannel("A").point(lambda a: int(a * 0.35)).filter(ImageFilter.GaussianBlur(4)))
    base.alpha_composite(shadow, (int(x + 3), int(y + 4)))
    base.alpha_composite(it, (int(x), int(y)))


def _pt(kp, i, min_conf=0.3):
    return (float(kp[i, 0]), float(kp[i, 1])) if kp[i, 2] >= min_conf else None


def _angle(a, b) -> float:
    return float(np.degrees(np.arctan2(b[1] - a[1], b[0] - a[0])))


def place(person_jpeg: bytes, product_jpeg: bytes, kind: str) -> bytes:
    person = Image.open(io.BytesIO(person_jpeg)).convert("RGB")
    item = cutout(Image.open(io.BytesIO(product_jpeg)))
    kp = pose.keypoints(person)
    if kp is None:
        raise PlacementError("We couldn't see a person clearly. Try a front-facing photo in good light")
    ls, rs = _pt(kp, L_SH), _pt(kp, R_SH)
    if not (ls and rs):
        raise PlacementError("Make sure both shoulders are visible in your photo")
    sw = float(np.hypot(ls[0] - rs[0], ls[1] - rs[1]))
    base = person.convert("RGBA")

    if kind in ("jewellery", "necklace"):
        mid = ((ls[0] + rs[0]) / 2, (ls[1] + rs[1]) / 2)
        nose = _pt(kp, NOSE) or (mid[0], mid[1] - sw * 0.6)
        neck = (mid[0], mid[1] - (mid[1] - nose[1]) * 0.25)
        _paste(base, item, neck, sw * 0.55, _angle(rs, ls) if ls[0] > rs[0] else _angle(ls, rs), anchor="top")
    elif kind == "earrings":
        for ear in (L_EAR, R_EAR):
            p = _pt(kp, ear, 0.2)
            if p:
                _paste(base, item, (p[0], p[1] + sw * 0.03), sw * 0.13, anchor="top")
    elif kind == "eyewear":
        le, re_ = _pt(kp, L_EYE), _pt(kp, R_EYE)
        if not (le and re_):
            raise PlacementError("We need to see both eyes for glasses")
        d = float(np.hypot(le[0] - re_[0], le[1] - re_[1]))
        a, b = (re_, le) if re_[0] < le[0] else (le, re_)
        _paste(base, item, ((le[0] + re_[0]) / 2, (le[1] + re_[1]) / 2), d * 2.3, _angle(a, b))
    elif kind == "watches":
        wr, el = _pt(kp, L_WR), _pt(kp, L_EL)
        if not wr:
            wr, el = _pt(kp, R_WR), _pt(kp, R_EL)
        if not wr:
            raise PlacementError("Show your wrist in the photo to try a watch")
        ang = _angle(el, wr) - 90 if el else 0
        p = (wr[0] + (el[0] - wr[0]) * 0.12, wr[1] + (el[1] - wr[1]) * 0.12) if el else wr
        _paste(base, item, p, sw * 0.2, ang)
    elif kind == "bags":
        hand = _pt(kp, R_WR) or _pt(kp, L_WR)
        hip = _pt(kp, R_HIP) or _pt(kp, L_HIP)
        anchor_pt = hand or hip
        if not anchor_pt:
            raise PlacementError("Show your arm or hip to try a bag")
        _paste(base, item, anchor_pt, sw * 0.65, anchor="top")
    elif kind == "shoes":
        la, ra = _pt(kp, L_AN), _pt(kp, R_AN)
        if not (la or ra):
            raise PlacementError("Use a full-length photo with your feet visible to try shoes")
        for p in (la, ra):
            if p:
                _paste(base, item, (p[0], p[1] + sw * 0.06), sw * 0.38)
    else:
        raise PlacementError(f"Unsupported accessory: {kind}")

    out = io.BytesIO()
    base.convert("RGB").save(out, "JPEG", quality=92)
    return out.getvalue()
