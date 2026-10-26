"""SSRF-hardened HTTP fetch for user-supplied URLs.

- http/https only, default ports only
- every hostname resolved and every address checked against private/reserved ranges
- connection pinned to the checked IP (defeats DNS rebinding), TLS still verified via SNI
- redirects followed manually and re-validated, capped
- response size capped while streaming
"""
import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

MAX_REDIRECTS = 3
UA = "Mozilla/5.0 (compatible; SaastaBot/1.0; +https://saasta.pk/bot)"


class UnsafeURL(ValueError):
    pass


def _is_public(ip: str) -> bool:
    a = ipaddress.ip_address(ip)
    if isinstance(a, ipaddress.IPv6Address) and a.ipv4_mapped:
        a = a.ipv4_mapped
    return a.is_global and not (a.is_multicast or a.is_reserved or a.is_link_local)


def check_url_shape(url: str) -> tuple[str, str, int]:
    if len(url) > 2048:
        raise UnsafeURL("URL too long")
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https"):
        raise UnsafeURL("Only http(s) links are allowed")
    if parts.username or parts.password:
        raise UnsafeURL("Credentials in URL are not allowed")
    host = (parts.hostname or "").rstrip(".").lower()
    if not host or host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise UnsafeURL("Host not allowed")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    if port not in (80, 443):
        raise UnsafeURL("Port not allowed")
    return parts.scheme, host, port


async def resolve_public(host: str, port: int) -> str:
    try:
        ipaddress.ip_address(host)
        literal = True
    except ValueError:
        literal = False
    if literal:
        ips = [host]
    else:
        loop = asyncio.get_running_loop()
        try:
            infos = await asyncio.wait_for(
                loop.getaddrinfo(host, port, type=socket.SOCK_STREAM), timeout=5
            )
        except (socket.gaierror, asyncio.TimeoutError) as e:
            raise UnsafeURL("Could not resolve host") from e
        ips = list(dict.fromkeys(i[4][0] for i in infos))
    if not ips or not all(_is_public(ip) for ip in ips):
        raise UnsafeURL("Host resolves to a private address")
    return ips[0]


async def safe_get(url: str, max_bytes: int, accept: str = "*/*", timeout: float = 15.0) -> tuple[bytes, str, str]:
    """Returns (body, content_type, final_url)."""
    current = url
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False) as client:
        for _ in range(MAX_REDIRECTS + 1):
            scheme, host, port = check_url_shape(current)
            ip = await resolve_public(host, port)
            parts = urlsplit(current)
            ip_host = f"[{ip}]" if ":" in ip else ip
            pinned = urlunsplit((scheme, f"{ip_host}:{port}", parts.path or "/", parts.query, ""))
            req = client.build_request(
                "GET", pinned,
                headers={"Host": host, "User-Agent": UA, "Accept": accept},
                extensions={"sni_hostname": host} if scheme == "https" else {},
            )
            resp = await client.send(req, stream=True)
            try:
                if resp.status_code in (301, 302, 303, 307, 308):
                    loc = resp.headers.get("location")
                    if not loc:
                        raise UnsafeURL("Bad redirect")
                    current = urljoin(current, loc)
                    continue
                if resp.status_code >= 400:
                    raise UnsafeURL(f"Remote returned {resp.status_code}")
                declared = resp.headers.get("content-length")
                if declared and declared.isdigit() and int(declared) > max_bytes:
                    raise UnsafeURL("Remote file too large")
                buf = bytearray()
                async for chunk in resp.aiter_bytes():
                    buf.extend(chunk)
                    if len(buf) > max_bytes:
                        raise UnsafeURL("Remote file too large")
                return bytes(buf), resp.headers.get("content-type", ""), current
            finally:
                await resp.aclose()
    raise UnsafeURL("Too many redirects")


def safe_outbound(url: str | None) -> str | None:
    """Sanitize a link we will render/redirect to: http(s) only, no creds, no js:."""
    if not url or len(url) > 2048:
        return None
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username:
        return None
    return urlunsplit(parts)
