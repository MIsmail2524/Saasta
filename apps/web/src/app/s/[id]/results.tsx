"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { OfferCard } from "@/components/offer-card";
import { SearchBox } from "@/components/search-box";
import { api, mediaUrl, money, outUrl, type Offer, type SearchDoc, type SearchResult } from "@/lib/api";

const TABS = [
  ["exact", "Exact matches"],
  ["similar", "Similar"],
  ["dupes", "Cheaper dupes"],
  ["social", "Social sellers"],
] as const;

export function Results({ id }: { id: string }) {
  const [doc, setDoc] = useState<SearchDoc | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [look, setLook] = useState(0);

  useEffect(() => {
    let stop = false;
    let delay = 800;
    async function poll() {
      try {
        const d = await api<SearchDoc>(`/v1/searches/${encodeURIComponent(id)}`);
        if (stop) return;
        setDoc(d);
        if (d.status === "queued" || d.status === "running") {
          delay = Math.min(delay * 1.3, 3000);
          setTimeout(poll, delay);
        }
      } catch (e) {
        if (!stop) setErr((e as Error).message);
      }
    }
    poll();
    return () => {
      stop = true;
    };
  }, [id]);

  if (err) return <Shell><p className="text-danger">{err}</p></Shell>;
  if (!doc || doc.status === "queued" || doc.status === "running") return <Loading image={doc?.image} />;
  if (doc.status === "failed")
    return (
      <Shell>
        <div className="card p-6">
          <p className="text-lg font-bold">We couldn&apos;t finish that search</p>
          <p className="mt-1 text-muted">{doc.error}</p>
        </div>
        <div className="mt-6"><SearchBox compact /></div>
      </Shell>
    );

  const r = doc.result!;
  if (r.kind === "video" && "looks" in r) {
    const current = r.looks[look];
    return (
      <Shell>
        <h1 className="text-2xl font-extrabold">Shop this video</h1>
        <p className="text-muted">We found {r.looks.length} looks. Pick one.</p>
        <div className="mt-4 flex gap-3 overflow-x-auto pb-2">
          {r.looks.map((l, i) => (
            <button
              key={l.image + i}
              onClick={() => setLook(i)}
              className={`card shrink-0 overflow-hidden ${i === look ? "ring-2 ring-brand" : ""}`}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={mediaUrl(l.image)} alt={`Look at ${l.t}s`} className="h-28 w-20 object-cover" />
              <span className="block py-1 text-xs font-semibold">{l.t}s</span>
            </button>
          ))}
        </div>
        <ResultView r={current} image={current.image} searchId={id} />
      </Shell>
    );
  }
  return (
    <Shell>
      <ResultView r={r as SearchResult} image={doc.image} searchId={id} />
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return <div className="mx-auto max-w-6xl px-4 py-8">{children}</div>;
}

function Loading({ image }: { image?: string | null }) {
  const steps = ["Reading your photo", "Matching against thousands of stores", "Checking social sellers", "Comparing prices and seller trust"];
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI((x) => Math.min(x + 1, steps.length - 1)), 2500);
    return () => clearInterval(t);
  }, [steps.length]);
  return (
    <Shell>
      <div className="card mx-auto flex max-w-lg flex-col items-center gap-4 p-8 text-center">
        {image && (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img src={mediaUrl(image)} alt="" className="h-40 rounded-xl object-contain" />
        )}
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-line">
          <div className="h-full animate-pulse rounded-full bg-brand" style={{ width: `${(i + 1) * 25}%`, transition: "width .8s" }} />
        </div>
        <p className="font-semibold">{steps[i]}…</p>
        <p className="text-sm text-muted">Usually takes 10 to 20 seconds.</p>
      </div>
    </Shell>
  );
}

function PriceLadder({ r }: { r: SearchResult }) {
  if (!r.price) return null;
  const { min, median, max } = r.price;
  const pos = (v: number) => (max === min ? 50 : ((v - min) / (max - min)) * 100);
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between text-sm">
        <p className="font-semibold">Price range ({r.price.count} sellers, {r.price.basis} matches)</p>
      </div>
      <div className="relative mt-6 h-2 rounded-full bg-gradient-to-r from-brand via-accent to-danger">
        <span className="absolute -top-6 -translate-x-1/2 text-xs font-bold" style={{ left: `${pos(median)}%` }}>
          usual {money(median, r.currency)}
        </span>
        <span className="absolute top-1/2 h-4 w-1 -translate-y-1/2 rounded bg-ink" style={{ left: `${pos(median)}%` }} />
      </div>
      <div className="mt-2 flex justify-between text-sm">
        <span className="font-bold text-brand">{money(min, r.currency)}</span>
        <span className="text-muted">{money(max, r.currency)}</span>
      </div>
    </div>
  );
}

function ResultView({ r, image, searchId }: { r: SearchResult; image?: string | null; searchId: string }) {
  const first = useMemo(() => TABS.find(([k]) => (r[k] as Offer[]).length > 0)?.[0] ?? "exact", [r]);
  const [tab, setTab] = useState<(typeof TABS)[number][0]>(first);
  const [saved, setSaved] = useState<Offer[]>([]);
  const [boardMsg, setBoardMsg] = useState<string | null>(null);
  const list = r[tab] as Offer[];
  const u = r.understanding;

  async function saveBoard() {
    try {
      const b = await api<{ id: string }>("/v1/me/boards", {
        method: "POST",
        body: JSON.stringify({ title: u.query?.slice(0, 120) || "My look", public: true, items: saved }),
      });
      setBoardMsg(`/b/${b.id}`);
    } catch {
      setBoardMsg("login");
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
      <aside className="space-y-4">
        {image && (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img src={mediaUrl(image)} alt="Your search" className="card w-full object-contain p-2" />
        )}
        <div className="card space-y-2 p-4 text-sm">
          <p className="font-semibold">We think this is</p>
          <p className="text-lg font-bold">{u.query || "Unknown item"}</p>
          <div className="flex flex-wrap gap-1.5">
            {u.category && <span className="chip">{u.category}</span>}
            {u.color && <span className="chip">{u.color}</span>}
            {u.attributes?.map((a) => <span key={a} className="chip">{a}</span>)}
            {u.max_price && <span className="chip">under {money(u.max_price, r.currency)}</span>}
          </div>
        </div>
        <PriceLadder r={r} />
        {r.best_deal && (
          <a
            href={outUrl(r.best_deal.out)}
            target="_blank"
            rel="noopener noreferrer nofollow"
            className="card block border-brand bg-brand-soft p-4"
          >
            <p className="text-xs font-bold uppercase tracking-wide text-brand">Best trusted deal</p>
            <p className="mt-1 text-2xl font-extrabold">{money(r.best_deal.price_local, r.currency)}</p>
            <p className="text-sm text-muted">at {r.best_deal.seller || r.best_deal.domain} →</p>
          </a>
        )}
        <div className="card p-4 text-xs text-muted">
          Searched Saasta&apos;s index of {r.sources.indexed.toLocaleString()} products from stores and sellers
          {r.sources.engine === "fingerprint" && <> (quick match mode)</>}.
          <br />
          Prices converted to {r.currency} are approximate.
        </div>
        <SearchBox compact />
      </aside>

      <section>
        <div className="flex flex-wrap gap-2">
          {TABS.map(([k, label]) => (
            <button
              key={k}
              onClick={() => setTab(k)}
              className={`chip !px-4 !py-2 !text-sm ${tab === k ? "!border-brand bg-brand text-brand-ink" : ""}`}
            >
              {label} <span className="opacity-70">{(r[k] as Offer[]).length}</span>
            </button>
          ))}
        </div>
        {tab === "social" && list.length > 0 && (
          <p className="mt-3 rounded-lg bg-accent-soft px-3 py-2 text-sm">
            Buying from a social seller? Ask for cash on delivery or a video call first, and never send advance payment to
            unknown accounts.
          </p>
        )}
        {list.length === 0 ? (
          <div className="card mt-4 p-8 text-center text-muted">
            {r.sources.indexed === 0 ? (
              <>Our product index is still being built on this server. Check back soon.</>
            ) : (
              <>Nothing here yet. Try another tab, or refine with words like &quot;same but black&quot;.</>
            )}
          </div>
        ) : (
          <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
            {list.map((o) => (
              <OfferCard
                key={o.url}
                o={o}
                currency={r.currency}
                tryOnCategory={u.tryon_category || (u.category && ["shoes", "bags", "jewellery", "watches", "eyewear"].includes(u.category) ? u.category : null)}
                onSave={(x) => setSaved((s) => (s.some((y) => y.url === x.url) ? s : [...s, x]))}
              />
            ))}
          </div>
        )}
        {saved.length > 0 && (
          <div className="card sticky bottom-4 mt-6 flex flex-wrap items-center justify-between gap-3 p-4 shadow-lg">
            <p className="text-sm">
              <b>{saved.length}</b> saved. Total{" "}
              <b>{money(saved.reduce((a, o) => a + (o.price_local ?? 0), 0), r.currency)}</b>
            </p>
            {boardMsg && boardMsg !== "login" ? (
              <Link className="btn-primary" href={boardMsg}>Open shareable board</Link>
            ) : boardMsg === "login" ? (
              <Link className="btn-ghost" href={`/login?next=/s/${searchId}`}>Log in to save your board</Link>
            ) : (
              <button className="btn-primary" onClick={saveBoard}>Create shareable board</button>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
