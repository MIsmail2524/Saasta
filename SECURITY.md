# Security

## Reporting

Email security@saasta.pk with details and steps to reproduce. Please don't open public issues for
vulnerabilities. We aim to reply within 72 hours.

## Controls in place

**Uploads and media**
- File type decided by magic bytes, never by extension or `Content-Type`. SVG, HTML, HEIC and unknown types rejected.
- Images decoded with a pixel cap (decompression-bomb safe), then re-encoded to JPEG. EXIF/GPS and any appended
  payloads are dropped. Originals are never stored or served.
- Videos: size and duration caps, ffmpeg run without a shell, with timeouts, audio/subtitle/data streams disabled.
- Stored files are content-addressed (`sha256.jpg`) and looked up with a strict regex, so there is no path traversal.
- Try-on selfies are processed in memory and never written to disk.

**Outbound requests (SSRF)**
- Only http/https on ports 80/443, no credentials in URLs, no `localhost`/`.internal`/`.local`.
- Every hostname is resolved and every address must be globally routable (blocks RFC1918, loopback, link-local
  incl. cloud metadata `169.254.169.254`, CGNAT, IPv4-mapped IPv6).
- The connection is pinned to the checked IP with TLS verified via SNI, which defeats DNS rebinding.
- Redirects are followed manually and re-validated (max 3). Response size is capped while streaming.

**Auth and sessions**
- Argon2id password hashing with transparent rehash. Constant-cost login for unknown emails (no user enumeration by timing).
- Password policy: length, a common-password list, repetition check.
- Account lockout after 8 failures plus per-IP and per-account rate limits.
- JWT in an `HttpOnly`, `SameSite=Lax`, `Secure` (prod) cookie, with issuer/audience checks and a token version
  for "log out everywhere" and revocation on password change.
- Cookie-authenticated state changes require a same-site `Origin` (CSRF defence in depth).
- Store API keys: 256-bit random, shown once, stored as HMAC-SHA256, revocable, max 5 active.
  Widget keys only work from the store's verified domain.

**Web**
- Per-request nonce CSP with `strict-dynamic`, `frame-ancestors 'none'`, `object-src 'none'`, HSTS preload,
  `nosniff`, a strict referrer policy, COOP and Permissions-Policy.
- The widget renders inside a closed Shadow DOM using `textContent` only, and only http(s) links.
- All outbound result links go through HMAC-signed `/out` redirects (no open redirect). `rel="noopener noreferrer nofollow"`.
- `?next=` redirects after login only accept same-site relative paths.

**API**
- Strict Pydantic schemas (`extra="forbid"`), length limits on every field, a request body cap.
- Validation errors never echo submitted values. Unhandled errors return a generic message plus a request id.
- OpenAPI docs disabled in production. The API refuses to boot with insecure production config.
- Rate limits on search, auth, try-on, verification, Shopify import and the widget (Redis-backed in prod).

**Privacy**
- IPs stored only as salted HMACs. Anonymous upload images are removed after 72h. Aggregates are kept for insights.
- Store insights use k-anonymity (k ≥ 3), and stores never see individual searches.
- Users can clear their history and delete their account (cascading delete).

**Supply chain and CI**
- Pinned dependencies, Dependabot, `pip-audit`, `npm audit`, CodeQL (security-extended), gitleaks secret scanning.
- Containers run as non-root with `no-new-privileges`, dropped capabilities, and a read-only web filesystem.
