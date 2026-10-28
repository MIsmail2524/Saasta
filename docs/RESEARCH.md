# Market and competitor research

## What already exists

| Product | Who it serves | What it does well | Gap Saasta fills |
|---|---|---|---|
| Google Lens / Circle to Search | Shoppers | Huge index, exact matches, Shopping prices | No seller trust signals, no dupes, weak on IG/TikTok-only sellers, no video, no local-first ranking |
| Pinterest Lens | Shoppers | Style inspiration, similar looks | Weak on where-to-buy and price comparison |
| Amazon Lens (was StyleSnap) | Amazon shoppers | Buy-now inside Amazon | Only Amazon inventory |
| Daraz / marketplace image search | Marketplace shoppers | One-tap purchase | Only that marketplace's catalog |
| Consumer apps (StyleFinder, Shnap, Shop By Image, etc.) | Shoppers | Photo-to-shop for fashion | Mostly Western retailers, no social sellers, no trust layer |
| Syte, Lykdat, ViSenze (B2B) | Large retailers | Visual search inside one store's site | Enterprise pricing and sales cycles, no cross-store demand data |
| FASHN, Kolors and other try-on APIs | Developers / brands | Garment try-on | Not a shopping product on their own |

## What makes Saasta different

1. **Reel to cart.** Video input with keyframe extraction: one reel returns every look in it.
2. **Social commerce aware.** In Pakistan and South Asia a big share of fashion is sold through Instagram and TikTok
   DMs. Saasta surfaces those sellers next to web stores, with COD safety guidance.
3. **Trust as a first-class signal.** Explainable seller scores (domain age, reviews, HTTPS, below-market pricing
   on the same item) attack the main fear of online shoppers here: getting scammed.
4. **Best *trusted* deal, not just the cheapest.**
5. **Dupe finder.** Cheaper lookalikes for when the original is out of budget, the core "saasta" promise.
6. **Plain-language refinement** ("same but black under 5k").
7. **Both sides of the market.** Shoppers bring demand. Stores pay for being found, the widget, and the
   **Demand radar** (unmet demand plus price bands), which no single-store B2B tool can offer because it needs
   cross-store search data.
8. **Local first.** PKR by default, local brands recognised as trusted, eastern wear categories (kurta, khussa,
   lawn, lehenga, jhumka…) understood natively.

## Unit economics (self-hosted)

Saasta runs on its own crawler, index and models, so there is no per-search fee to anyone.
- **Search:** one image embedding (~40 ms on a CPU core, ~3 ms on a GPU) plus an in-memory vector lookup.
  A single 8-core CPU box serves roughly 50 to 100 searches per second. Cost per search is a tiny fraction of a cent.
- **Crawling:** about 1 request per second per site, weekly refresh. 500 stores × 2,000 products is ~1M pages a
  week on one small worker.
- **Garment try-on:** a diffusion model; about 5 to 10 s per image on one modern GPU. A rented 24 GB GPU
  (roughly $0.3 to $0.8/hour) does 400+ try-ons per hour, so well under a cent each at good utilisation.
  CPU-only works for testing but takes minutes per image.
- **Accessory try-on:** pose + placement, about 1 s on CPU.
- **Revenue:** store subscriptions (Growth tier), CPC for partner clicks, affiliate commissions where networks
  exist, and an optional shopper Pro tier (more try-ons and alerts).

## Risks and mitigations

- **Index coverage vs. Google:** we cover the stores Pakistani shoppers actually buy from (seed list plus
  partner and social onboarding), not the whole web. Coverage grows every time a store joins or gets crawled.
- **Crawling ethics and law:** public product facts only, robots.txt obeyed, opt-out honoured by deleting data,
  no images re-hosted, every result links to the source. Social platforms are **not** scraped: sellers there
  list themselves.
- **Model licenses:** only Apache/MIT weights (see apps/ml/LICENSES.md). Popular non-commercial models
  (CatVTON, IDM-VTON, OOTDiffusion) are excluded.
- **Try-on misuse:** login required, consent checkbox, per-user rate limits, selfies never stored or used for training.
