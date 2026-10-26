import Link from "next/link";

export const metadata = {
  title: "Saasta for stores",
  description: "Get found by shoppers searching with photos and reels. Add search-by-photo to your store in one line.",
};

const PAINS = [
  ["Your products are invisible to photo shoppers", "Shoppers screenshot a reel and ask “where is this from?”. If Google Lens doesn't index you, you lose that sale to a reseller."],
  ["Visitors leave when search fails", "Text search can't find “that green kurta with mirror work”. Shoppers bounce instead of describing it."],
  ["You guess what to stock", "You don't see what people wanted and couldn't find, or what price they expected."],
];

const OFFER = [
  {
    t: "Get found",
    d: "Sync your catalog in minutes (Shopify, CSV or Google Merchant feed). When someone searches with a photo that matches your product, you show up as a verified partner with a trust badge.",
    k: "Free listing",
  },
  {
    t: "Search by photo on your site",
    d: "Paste one script tag. Shoppers upload a screenshot on your store and see your closest matching products. Works on Shopify, WooCommerce and custom sites.",
    k: "One-line widget",
  },
  {
    t: "Demand radar",
    d: "Weekly insights: top searched categories in your country, trending colours, price bands shoppers pay, and searches no one could fulfil. Stock what's already wanted.",
    k: "Unmet demand",
  },
  {
    t: "Click analytics",
    d: "See which products shoppers clicked through to and when. Every click is tracked with a signed link, so no bot inflation from fake redirects.",
    k: "Real traffic",
  },
];

const PLANS = [
  { n: "Starter", p: "Free", f: ["Up to 300 products listed", "Verified partner badge", "Basic click analytics"] },
  { n: "Growth", p: "Rs 4,999/mo", f: ["Up to 10,000 products", "Search-by-photo widget (5k searches/mo)", "Demand radar insights", "Priority placement in matches"], hot: true },
  { n: "Brand", p: "Custom", f: ["Unlimited products & widget searches", "API access", "Try-on on your product pages", "Dedicated onboarding"] },
];

export default function Stores() {
  return (
    <>
      <section className="mx-auto max-w-5xl px-4 pb-12 pt-16 text-center">
        <p className="chip mx-auto mb-4">Saasta for stores</p>
        <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl">
          Shoppers search with photos now. <span className="text-brand">Be the store they find.</span>
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-lg text-muted">
          Saasta turns reels, screenshots and street photos into buyers for your products, and tells you what they want next.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link href="/signup?next=/merchant" className="btn-primary px-6 py-3">List my store free</Link>
          <a href="#widget" className="btn-ghost px-6 py-3">See the widget</a>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-10">
        <div className="grid gap-4 sm:grid-cols-3">
          {PAINS.map(([t, d]) => (
            <div key={t} className="card p-5">
              <p className="font-bold">{t}</p>
              <p className="mt-2 text-sm text-muted">{d}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-10">
        <h2 className="text-3xl font-extrabold">What you get</h2>
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {OFFER.map((o) => (
            <div key={o.t} className="card p-6">
              <span className="chip border-accent/40 bg-accent-soft">{o.k}</span>
              <p className="mt-3 text-xl font-bold">{o.t}</p>
              <p className="mt-2 text-sm text-muted">{o.d}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="widget" className="mx-auto max-w-6xl px-4 py-10">
        <div className="card grid gap-6 p-6 md:grid-cols-2">
          <div>
            <h2 className="text-2xl font-extrabold">Install in 60 seconds</h2>
            <ol className="mt-4 list-decimal space-y-2 pl-5 text-sm text-muted">
              <li>Create a store account and verify your domain.</li>
              <li>Import products from Shopify or upload a CSV feed.</li>
              <li>Create a widget key and paste this before <code>&lt;/body&gt;</code>.</li>
            </ol>
            <p className="mt-4 text-sm text-muted">
              Keys only work on your verified domain, so copying your snippet to another site does nothing.
            </p>
          </div>
          <pre className="overflow-x-auto rounded-xl bg-ink p-4 text-xs text-bg">
{`<script src="https://saasta.pk/widget.js"
  data-key="sk_saasta_••••••"
  data-color="#0e5c46"
  data-label="Search by photo"
  async></script>`}
          </pre>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-10">
        <h2 className="text-3xl font-extrabold">Simple pricing</h2>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {PLANS.map((p) => (
            <div key={p.n} className={`card p-6 ${p.hot ? "border-brand ring-2 ring-brand" : ""}`}>
              <p className="font-semibold text-muted">{p.n}</p>
              <p className="mt-1 text-3xl font-extrabold">{p.p}</p>
              <ul className="mt-4 space-y-2 text-sm">
                {p.f.map((f) => <li key={f}>✓ {f}</li>)}
              </ul>
            </div>
          ))}
        </div>
        <p className="mt-4 text-sm text-muted">Founding-partner offer: first 50 stores get Growth free for 3 months.</p>
      </section>
    </>
  );
}
