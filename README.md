# Saasta · سستا

**Dekho. Dhoondo. Saasta lo.** (See it. Find it. Get it for less.)

Saasta is visual shopping search for South Asia and beyond. Upload a photo, screenshot, product link or a
whole reel of any clothes, shoes, bag or jewellery. Saasta finds where it is sold across the web, Instagram and
TikTok, compares prices and reviews, flags risky sellers, shows cheaper lookalikes, and lets you try it on.

For stores, Saasta is a demand channel: get matched when shoppers search with photos, add search-by-photo to
your own site with one script tag, and see what customers want that nobody stocks.

## Features

**Shoppers**
- Search by **photo, screenshot (paste), product/Instagram/TikTok link, or video**. Videos are split into
  distinct keyframes, so a single reel returns every look in it, with timestamps.
- **Exact matches vs similar** results, merged and de-duplicated across sources (tracking params stripped).
- **Price ladder**: min, usual (median) and max for the same item, normalised to your currency.
- **Best trusted deal**: the cheapest offer from a high-trust seller, not just the cheapest.
- **Fake-seller radar**: explainable trust score per seller (domain age via RDAP, HTTPS, known store,
  reviews and rating, social-only seller, price far below the market for the same item).
- **Dupe finder**: visually close items at 40% or more below the usual price, excluding low-trust sellers.
- **Plain-language refinement**: "same but black under 5k" sets the colour and price cap.
- **Instagram and TikTok seller discovery**: finds sellers who post prices in captions, with COD safety tips.
- **Price-drop watches** (reads JSON-LD / meta prices on product pages), **shareable look boards** with a total.
- **Virtual try-on** for apparel, eastern wear, shoes, bags, jewellery, watches and eyewear.

**Stores**
- Onboarding with **domain verification** (DNS TXT or `.well-known` file).
- Catalog sync from **Shopify** (public `products.json`), **CSV / Google Merchant feed**, or JSON API.
  Products must live on the verified domain.
- Partner products are **visually indexed** and ranked first-party in shopper results.
- **Search-by-photo widget**: one `<script>` tag. Keys are publishable but locked to the store's domain.
- **Signed click-out analytics** and a **Demand radar**: top categories, price bands, trending colours and
  unmet demand, all aggregated with k-anonymity (k ≥ 3).

## Architecture

```
            ┌──────────── Caddy (HTTPS, HSTS) ────────────┐
 browser ──▶│  /           → web  (Next.js 16, CSP nonces)│
            │  /api/*, /w/* → api (FastAPI)               │
            └──────────────────────────┬──────────────────┘
                                       │
   api ── Postgres (users, stores, catalog, searches, clicks, watches)
    │  └─ Redis (rate limits)
    ├─ worker: price watches + data retention
    └─ providers: SerpApi (Google Lens + Shopping) · Apify (Instagram, TikTok) · FASHN (try-on) · RDAP
```

Search pipeline (`apps/api/app/search/pipeline.py`):
1. Clean the upload (magic-byte sniff, decode with pixel cap, re-encode to JPEG, metadata stripped).
2. Google Lens exact + visual matches → infer product query and category from recurring title words.
3. In parallel: Google Shopping (all sellers and prices), Instagram, TikTok, partner catalog.
4. Merge and de-duplicate, convert currency, apply refinement filters.
5. Re-rank by visual similarity (perceptual hash + colour histogram) using SSRF-safe thumbnail fetches.
6. Trust-score sellers, compute the price ladder, best trusted deal and dupes.

Every provider is optional and isolated: if one fails or is not configured, the search still completes.

## Run locally

```bash
# API
cd apps/api
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env   # add SERPAPI / APIFY / FASHN keys to enable live sources
.venv/bin/uvicorn app.main:app --reload --port 8000

# Web (new terminal)
cd apps/web
npm install
npm run dev            # http://localhost:3000
```

Tests: `cd apps/api && .venv/bin/pytest`. Lint: `ruff check app tests` and `npm run lint`.

## Deploy

```bash
cp .env.example .env   # set SITE_DOMAIN, POSTGRES_PASSWORD, SAASTA_SECRET_KEY, SAASTA_IP_HASH_SALT, provider keys
docker compose up -d --build
```

Operator commands (inside the api container):

```bash
docker compose exec api python -m app.admin set-plan mystore.pk growth
docker compose exec api python -m app.admin stats
```

The API refuses to start in production with default secrets, SQLite, wildcard CORS or without Redis.

## Security

See [SECURITY.md](SECURITY.md) for the full list of controls and how to report a vulnerability.

## Docs

- [docs/PITCH.md](docs/PITCH.md): store pitch, pricing, outreach scripts and objection handling
- [docs/RESEARCH.md](docs/RESEARCH.md): market and competitor research, and what makes Saasta different
- [docs/ROADMAP.md](docs/ROADMAP.md): what's next
