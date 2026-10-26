# Saasta web

Next.js app for shoppers (search, results, try-on, account) and stores (dashboard, widget).

```bash
npm install
SAASTA_API_INTERNAL_URL=http://localhost:8000 npm run dev
```

All API calls go through `/api/*`, which Next rewrites to the API server, so the session cookie stays first-party.
`public/widget.js` is the embeddable search-by-photo widget for partner stores.
