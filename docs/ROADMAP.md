# Roadmap

**Next**
- First fine-tune of `saasta-siglip` on opted-in catalogs; publish recall@5 before and after.
- Grow the opted-in try-on dataset to 20k pairs, then fine-tune garment try-on for eastern wear.
- Garment detection to auto-crop multiple items per photo (shirt + bag + shoes) before matching.
- Move the vector index to pgvector / HNSW past ~2M products.
- Price-alert delivery over email and WhatsApp.
- Urdu UI and Roman-Urdu query understanding.
- Browser extension and mobile share-sheet: "Find on Saasta" from any app.

**Later**
- Affiliate link integration for marketplace clicks.
- Try-on embedded on partner product pages.
- Seller reputation from verified purchases (shopper-reported scams feed back into the trust score).
- Size and fit hints from brand size charts.
- Alembic migrations and a Redis job queue for horizontal scaling.
