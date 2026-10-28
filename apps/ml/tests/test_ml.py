import base64
import io
import os

import numpy as np
import pytest

os.environ.setdefault("SAASTA_ML_DEV", "1")

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app import embed, place, pose  # noqa: E402


def _jpeg(img: Image.Image) -> bytes:
    b = io.BytesIO()
    img.convert("RGB").save(b, "JPEG", quality=95)
    return b.getvalue()


def product_shot() -> Image.Image:
    """A red pendant with a white stone in the middle, on a white studio background."""
    img = Image.new("RGB", (400, 400), (250, 250, 250))
    d = ImageDraw.Draw(img)
    d.ellipse((120, 120, 280, 280), fill=(190, 20, 30))
    d.ellipse((180, 180, 220, 220), fill=(250, 250, 250))
    return img


def test_cutout_keeps_inner_holes_and_drops_background():
    out = place.cutout(product_shot())
    a = np.asarray(out.getchannel("A"))
    assert out.size[0] < 200 and out.size[1] < 200  # cropped to the product
    h, w = a.shape
    assert a[h // 2, 5] > 200  # red ring is opaque
    assert a[h // 2, w // 2] > 200  # white stone inside stays (not connected to background)
    assert a[0, 0] < 30  # corner is transparent


def test_cutout_rejects_busy_backgrounds():
    noise = Image.fromarray(np.random.default_rng(1).integers(0, 255, (300, 300, 3), dtype=np.uint8))
    with pytest.raises(place.PlacementError):
        place.cutout(noise)


def _fake_kp(monkeypatch):
    kp = np.zeros((17, 3), dtype=np.float32)
    pts = {0: (200, 120), 1: (215, 110), 2: (185, 110), 3: (230, 120), 4: (170, 120),
           5: (260, 200), 6: (140, 200), 7: (280, 280), 8: (120, 280), 9: (290, 350), 10: (110, 350),
           11: (240, 360), 12: (160, 360), 15: (240, 560), 16: (160, 560)}
    for i, (x, y) in pts.items():
        kp[i] = (x, y, 0.9)
    monkeypatch.setattr(pose, "keypoints", lambda img: kp)


@pytest.mark.parametrize("kind,region", [
    ("necklace", (150, 150, 250, 260)), ("eyewear", (160, 90, 240, 130)), ("watches", (250, 300, 330, 380)),
    ("shoes", (110, 520, 290, 600)),
])
def test_place_draws_product_at_the_right_body_part(monkeypatch, kind, region):
    _fake_kp(monkeypatch)
    person = Image.new("RGB", (400, 600), (60, 90, 120))
    out = Image.open(io.BytesIO(place.place(_jpeg(person), _jpeg(product_shot()), kind))).convert("RGB")
    assert out.size == person.size
    crop = np.asarray(out.crop(region), dtype=np.float32)
    red = (crop[..., 0] > 140) & (crop[..., 1] < 80)
    assert red.mean() > 0.02, f"no product pixels near the {kind} anchor"


def test_place_needs_a_person(monkeypatch):
    monkeypatch.setattr(pose, "keypoints", lambda img: None)
    with pytest.raises(place.PlacementError):
        place.place(_jpeg(Image.new("RGB", (300, 300), "white")), _jpeg(product_shot()), "necklace")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(embed, "texts", lambda items: np.eye(len(items), 8, dtype=np.float32))
    monkeypatch.setattr(embed, "images", lambda imgs: np.eye(len(imgs), 8, dtype=np.float32))
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_service_requires_token(client):
    assert client.post("/v1/embed/texts", json={"texts": ["kurta"]}).status_code == 401
    r = client.post("/v1/embed/texts", json={"texts": ["kurta"]}, headers={"Authorization": "Bearer dev-ml-token"})
    assert r.status_code == 200 and r.json()["dim"] == 8


def test_service_rejects_bad_payloads(client):
    h = {"Authorization": "Bearer dev-ml-token"}
    assert client.post("/v1/embed/images", json={"images": ["%%%"]}, headers=h).status_code == 422
    assert client.post("/v1/embed/texts", json={"texts": []}, headers=h).status_code == 422
    big = base64.b64encode(b"x" * 11_000_000).decode()
    assert client.post("/v1/embed/images", json={"images": [big]}, headers=h).status_code == 413
