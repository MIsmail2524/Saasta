import Link from "next/link";
import { SearchBox } from "@/components/search-box";

const FEATURES = [
  {
    t: "Every seller, one search",
    d: "Google Lens, Google Shopping, brand stores, marketplaces, plus Instagram and TikTok sellers that Google never shows.",
  },
  {
    t: "Shop the whole reel",
    d: "Upload a video and Saasta pulls out each outfit, bag and pair of shoes, with the moment it appears.",
  },
  {
    t: "Fake-seller radar",
    d: "Each seller gets a trust score: domain age, HTTPS, reviews, and prices that are too good to be true.",
  },
  {
    t: "Dupe finder",
    d: "Same look for less. We rank close lookalikes from trusted sellers at 40% or more below the usual price.",
  },
  {
    t: "Talk to your search",
    d: "\"Same but black, under 5k.\" Refine in plain words, Roman Urdu friendly.",
  },
  {
    t: "Price-drop alerts",
    d: "Watch any product and we'll track its price for you. Buy when it hits your number.",
  },
];

const STEPS = [
  ["Dekho", "See something you love: a reel, a street photo, a screenshot."],
  ["Dhoondo", "Upload it. We find the exact item and its lookalikes everywhere."],
  ["Saasta lo", "Compare prices, reviews and seller trust, then buy at the best deal."],
];

export default function Home() {
  return (
    <>
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-x-0 -top-40 h-96 bg-[radial-gradient(ellipse_at_center,var(--brand-soft),transparent_65%)]" />
        <div className="relative mx-auto max-w-4xl px-4 pb-10 pt-14 text-center sm:pt-20">
          <p className="chip mx-auto mb-5 border-accent/40 bg-accent-soft">
            <span className="font-urdu text-base" lang="ur">دیکھو۔ ڈھونڈو۔ سستا لو</span>
          </p>
          <h1 className="text-4xl font-extrabold tracking-tight sm:text-6xl">
            Saw it somewhere? <span className="text-brand">Find it cheaper.</span>
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-muted">
            Upload a photo or video of any clothes, shoes, bag or jewellery. Saasta finds where it&apos;s sold across the
            internet, compares prices and reviews, and warns you about risky sellers.
          </p>
          <div className="mt-8 text-left">
            <SearchBox />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-12">
        <div className="grid gap-4 sm:grid-cols-3">
          {STEPS.map(([t, d], i) => (
            <div key={t} className="card p-5">
              <p className="text-sm font-semibold text-accent">Step {i + 1}</p>
              <p className="mt-1 text-2xl font-extrabold">{t}</p>
              <p className="mt-2 text-sm text-muted">{d}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-12">
        <h2 className="text-3xl font-extrabold tracking-tight">More than a reverse image search</h2>
        <p className="mt-2 max-w-2xl text-muted">Built for how people really shop: from reels, DMs and screenshots.</p>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.t} className="card p-5">
              <p className="font-bold">{f.t}</p>
              <p className="mt-2 text-sm text-muted">{f.d}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-12">
        <div className="card flex flex-col items-start justify-between gap-6 bg-brand p-8 text-brand-ink sm:flex-row sm:items-center">
          <div>
            <p className="text-2xl font-extrabold">Run an online store?</p>
            <p className="mt-1 max-w-xl opacity-90">
              Get found when shoppers search with a photo, add &quot;search by photo&quot; to your own site in one line, and
              see what customers want that nobody stocks.
            </p>
          </div>
          <Link href="/stores" className="btn bg-accent text-ink hover:brightness-105">
            Saasta for stores →
          </Link>
        </div>
      </section>
    </>
  );
}
