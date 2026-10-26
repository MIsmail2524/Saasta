"""Untrusted media handling.

Images are sniffed by magic bytes, decoded by Pillow with a pixel cap, and re-encoded
to clean JPEG (drops EXIF/GPS, ICC tricks, polyglot payloads). Nothing the user sent
is ever stored or served as-is.
"""
import io

from PIL import Image, ImageOps

from app.core.config import get_settings

IMAGE_MAGIC = {
    b"\xff\xd8\xff": "jpeg",
    b"\x89PNG\r\n\x1a\n": "png",
    b"RIFF": "webp",  # confirmed below
    b"GIF87a": "gif",
    b"GIF89a": "gif",
}
VIDEO_BRANDS = {b"isom", b"iso2", b"mp41", b"mp42", b"avc1", b"qt  ", b"M4V ", b"dash", b"MSNV"}


class MediaError(ValueError):
    pass


def sniff(data: bytes) -> str | None:
    head = data[:16]
    for magic, kind in IMAGE_MAGIC.items():
        if head.startswith(magic):
            if kind == "webp" and data[8:12] != b"WEBP":
                return None
            return kind
    if data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in (b"heic", b"heix", b"mif1", b"avif"):
            return None  # not supported without extra codecs
        if brand in VIDEO_BRANDS or brand.startswith(b"3g"):
            return "mp4"
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "webm"
    return None


def clean_image(data: bytes, max_side: int = 1600) -> tuple[bytes, Image.Image]:
    s = get_settings()
    if len(data) > s.max_image_bytes:
        raise MediaError("Image too large")
    kind = sniff(data)
    if kind not in {"jpeg", "png", "webp", "gif"}:
        raise MediaError("Unsupported image type (use JPG, PNG or WEBP)")
    Image.MAX_IMAGE_PIXELS = s.max_image_pixels
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()
        img = Image.open(io.BytesIO(data))
        if img.width * img.height > s.max_image_pixels:
            raise MediaError("Image dimensions too large")
        img.seek(0)
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
    except MediaError:
        raise
    except Exception as e:  # decompression bombs, truncated files, etc.
        raise MediaError("Could not read image") from e
    if img.width < 64 or img.height < 64:
        raise MediaError("Image too small, try a clearer photo")
    img.thumbnail((max_side, max_side))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=88, optimize=True)  # no exif kwarg -> metadata dropped
    return out.getvalue(), img
