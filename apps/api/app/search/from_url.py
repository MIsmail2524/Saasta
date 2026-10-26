"""Pasted links: a direct image, or a product/Instagram/TikTok page we read og:image from."""
import html
import re

from app.net.safe_fetch import UnsafeURL, safe_get

_META = re.compile(r"<meta\s+[^>]*>", re.I)
_ATTR = re.compile(r'(property|name|content)\s*=\s*"([^"]*)"|(property|name|content)\s*=\s*\'([^\']*)\'', re.I)


def _metas(page: str) -> dict:
    out = {}
    for tag in _META.findall(page[:400_000]):
        attrs = {}
        for m in _ATTR.finditer(tag):
            k = (m.group(1) or m.group(3)).lower()
            attrs[k] = html.unescape(m.group(2) if m.group(2) is not None else m.group(4))
        key = attrs.get("property") or attrs.get("name")
        if key and "content" in attrs:
            out.setdefault(key.lower(), attrs["content"])
    return out


async def resolve(url: str, max_image_bytes: int) -> tuple[bytes | None, str | None]:
    """Returns (image_bytes, title_hint)."""
    body, ctype, final = await safe_get(url, max_bytes=max(max_image_bytes, 3_000_000), accept="text/html,image/*")
    if ctype.startswith("image/"):
        return body, None
    if "html" not in ctype:
        raise UnsafeURL("Link is not an image or web page")
    meta = _metas(body.decode("utf-8", errors="ignore"))
    title = meta.get("og:title") or meta.get("twitter:title")
    img = meta.get("og:image") or meta.get("og:image:secure_url") or meta.get("twitter:image")
    if not img:
        return None, title
    from urllib.parse import urljoin

    data, ictype, _ = await safe_get(urljoin(final, img), max_bytes=max_image_bytes, accept="image/*")
    if not ictype.startswith("image/"):
        return None, title
    return data, (title[:200] if title else None)
