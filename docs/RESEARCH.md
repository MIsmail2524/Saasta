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

## Unit economics (rough, check current provider pricing)

- SerpApi: roughly 1 to 2.5 US cents per call depending on plan. A full image search uses about 3 calls
  (Lens exact, Lens products, Shopping).
- Apify social scraping: paid per run. Enable it only for logged-in users or cache it per query.
- Try-on (FASHN): about 7 to 8 US cents per generation. Rate-limited per user per day, and a natural premium feature.
- Revenue: store subscriptions (Growth tier), CPC for partner clicks, affiliate commissions where networks
  exist (Daraz affiliate, Amazon Associates), and an optional shopper Pro tier (more try-ons and alerts).

## Risks and mitigations

- **Provider dependency (Google results via SerpApi):** partner catalog and our own visual index grow over time.
  The pipeline is provider-agnostic.
- **Scraping ToS for social platforms:** only public posts via a compliant vendor, link back to the original
  post, no content re-hosting. Easy to switch off per source.
- **Try-on misuse:** login required, consent checkbox, conservative moderation, selfies never stored.
