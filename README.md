# Saasta · سستا

**Dekho. Dhoondo. Saasta lo.** (See it. Find it. Get it for less.)

Saasta is visual shopping search for South Asia and beyond. Upload a photo, screenshot, product link or a
whole reel of any clothes, shoes, bag or jewellery. Saasta finds where it is sold across stores and social
sellers, compares prices and reviews, flags risky sellers, shows cheaper lookalikes, and lets you try it on.

Search, understanding and try-on all run on Saasta's own crawler, index and self-hosted models.

For stores, Saasta is a demand channel: get matched when shoppers search with photos, add search-by-photo to
your own site with one script tag, and see what customers want that nobody stocks.

## Features

Everything runs on Saasta's own infrastructure: our crawler, our product index, our models.
No third-party search, scraping or AI APIs.

**Shoppers**
- Search by **photo, screenshot (paste), product link, or video**. Videos are split into distinct
  keyframes, so one reel returns every look in it, with timestamps. **Crop** to a single item.
- **Our own fashion model** reads the photo: category (kurta, khussa, jhumka, lehenga…), colour and
  attributes (embroidered, mirror work, printed…), then searches our vector index.
- **Exact matches vs similar**, merged and de-duplicated across stores.
- **Price ladder** (min / usual / max) and **best trusted deal**.
- **Fake-seller radar**: explainable trust score per seller.
- **Dupe finder**: visually close items at 40%+ below the usual price.
- **Plain-language refinement**: "same but black under 5k" shifts the search vector and filters.
- **Social sellers**: Instagram/TikTok/WhatsApp shops list their products with us (opt-in, verified).
- **Try-on on our own models**: garments (tops, bottoms, full suits) with a self-hosted diffusion model;
  necklaces, earrings, glasses, watches, bags and shoes with our pose-based placement engine.
- Price-drop watches, shareable look boards, account deletion.

**Stores**
- Domain verification (DNS TXT or file), Shopify import, CSV/Merchant feed, or photo upload for social sellers.
- Search-by-photo widget (one script tag, domain-locked key), signed click analytics, Demand radar.
- Optional **training opt-in**: stores can license their product photos to improve our models.

## Architecture

```
            ┌──────────── Caddy (HTTPS, HSTS) ────────────┐
 browser ──▶│  /             → web (Next.js 16, CSP nonces)│
            │  /api/*, /w/*  → api (FastAPI)               │
            └──────────────────────────┬──────────────────┘
   api ──▶ ml (internal only, token)   │  Postgres · Redis
   │        ├─ fashion embeddings (SigLIP, fashion-tuned)
   │        ├─ garment try-on (self-hosted diffusion weights)
   │        └─ pose (DWPose ONNX) + our cut-out/placement engine
   └─ worker: SaastaBot crawler → indexer → vector index · price watches · retention
```

**How search works** (`apps/api/app/search/pipeline.py`)
1. Clean the upload (magic-byte sniff, pixel cap, re-encode, metadata stripped).
2. Embed it with our fashion model. Zero-shot against label prompts gives category, colour, attributes.
3. Cosine search over our vector index (crawled stores + partner feeds + social sellers).
4. Exact match = embedding cosine ≥ 0.93 or perceptual-hash near-duplicate.
5. Merge, convert currency, apply refinements, trust-score sellers, compute price ladder, best deal, dupes.
6. If the ML service is down, search degrades to perceptual-hash + colour matching instead of failing.

**How the index is built** (`apps/api/app/crawl/`)
SaastaBot reads public product data only (Shopify `products.json`, sitemaps → schema.org JSON-LD),
obeys robots.txt and Crawl-delay, never re-hosts images, and deletes a site's items if it opts out.
Partner feeds always override crawled data for the same store.

**Models** (`apps/ml`, see [apps/ml/LICENSES.md](apps/ml/LICENSES.md) and [docs/MODELS.md](docs/MODELS.md))
Open-weight foundations with commercial licenses, self-hosted, fine-tuned on our own licensed data.

## Run locally

```bash
# API
cd apps/api
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
.venv/bin/uvicorn app.main:app --reload --port 8000

# ML service (needs ~3 GB of model downloads the first time)
cd apps/ml
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/download_weights.py --dir ./weights/tryon
SAASTA_ML_DEV=1 .venv/bin/uvicorn app.main:app --port 8100

# Build the index
cd apps/api
.venv/bin/python -m app.admin add-sites app/crawl/seeds.txt
.venv/bin/python -m app.admin crawl sapphireonline.pk

# Web
cd apps/web && npm install && npm run dev   # http://localhost:3000
```

Tests: `pytest` in `apps/api` and `apps/ml`; `npm run lint` in `apps/web`.

## Deploy

```bash
cp .env.example .env   # set SITE_DOMAIN, POSTGRES_PASSWORD, SAASTA_SECRET_KEY, SAASTA_IP_HASH_SALT, SAASTA_ML_TOKEN
docker compose run --rm ml python scripts/download_weights.py --dir /models/tryon
docker compose up -d --build
docker compose exec api python -m app.admin add-sites app/crawl/seeds.txt
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
- [docs/MODELS.md](docs/MODELS.md): our models, licenses, and how we train our own
- [docs/ROADMAP.md](docs/ROADMAP.md): what's next
