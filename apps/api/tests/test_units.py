import io

import pytest
from PIL import Image

from app.media.validate import MediaError, clean_image, sniff
from app.net.safe_fetch import UnsafeURL, check_url_shape, resolve_public, safe_outbound
from app.search import understand
from app.search.pipeline import canonical, dedupe
from app.search.providers.base import parse_price
from app.search.types import Offer
from app.worker import extract_price
from tests.conftest import jpeg


def test_sniff_rejects_disguised_files():
    assert sniff(jpeg()) == "jpeg"
    assert sniff(b"<svg xmlns='http://www.w3.org/2000/svg'></svg>") is None
    assert sniff(b"<?php echo 1; ?>" + b"\x00" * 20) is None


def test_clean_image_strips_exif_and_reencodes():
    out, _ = clean_image(jpeg(exif=True))
    assert b"SecretCam" not in out
    assert Image.open(io.BytesIO(out)).getexif().get(0x010F) is None


def test_clean_image_rejects_garbage_and_tiny():
    with pytest.raises(MediaError):
        clean_image(b"\xff\xd8\xff" + b"not really a jpeg" * 10)
    with pytest.raises(MediaError):
        clean_image(jpeg(size=(10, 10)))


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "gopher://x", "http://localhost/", "http://foo.internal/",
    "http://user:pw@example.com/", "http://example.com:6379/",
])
def test_url_shape_blocks(url):
    with pytest.raises(UnsafeURL):
        check_url_shape(url)


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.5", "169.254.169.254", "192.168.1.1", "::1",
                                "::ffff:127.0.0.1", "0.0.0.0", "100.64.0.1"])
async def test_private_ips_blocked(ip):
    with pytest.raises(UnsafeURL):
        await resolve_public(ip, 80)


def test_safe_outbound():
    assert safe_outbound("javascript:alert(1)") is None
    assert safe_outbound("data:text/html,hi") is None
    assert safe_outbound("https://daraz.pk/p/1") == "https://daraz.pk/p/1"


@pytest.mark.parametrize("raw,val,cur", [
    ("Rs 4,999", 4999.0, "PKR"), ("$12.50", 12.5, "USD"), ("€1.299,00", 1299.0, "EUR"),
    ({"value": "2500", "currency": "PKR"}, 2500.0, "PKR"), ("PKR 12,500.00", 12500.0, "PKR"),
])
def test_parse_price(raw, val, cur):
    assert parse_price(raw) == (val, cur)


def test_understanding():
    titles = ["Nike Air Force 1 '07 White Sneakers | Daraz.pk", "Nike Air Force 1 07 - Men's Shoes",
              "Buy Nike Air Force 1 White online"]
    assert understand.categorize(titles) == "shoes"
    q = understand.best_query(titles)
    assert "Nike" in q and "Air" in q and "Force" in q
    r = understand.parse_refinement("same but black under 5k")
    assert r["color"] == "black" and r["max_price"] == 5000


def test_dedupe_merges_tracking_variants():
    a = Offer(title="A", url="https://www.shop.pk/p/1?utm_source=x", source="google_lens", match="exact")
    b = Offer(title="A", url="https://shop.pk/p/1/", source="google_shopping", price=100.0)
    c = Offer(title="bad", url="javascript:alert(1)", source="google_lens")
    out = dedupe([a, b, c])
    assert len(out) == 1 and out[0].match == "exact" and out[0].price == 100.0
    assert canonical(a.url) == canonical(b.url)


def test_extract_price_jsonld():
    page = '<script type="application/ld+json">{"@type":"Product","offers":{"price":"3450"}}</script>'
    assert extract_price(page) == 3450.0
