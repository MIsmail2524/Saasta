"use client";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError, money } from "@/lib/api";
import { refreshMe, useMe } from "@/lib/use-me";

type M = { id: string; name: string; domain: string; domain_verified: boolean; verify_url: string; verify_token: string; currency: string; plan: string; limits: { products: number; widget: boolean; insights: boolean }; kind: "store" | "social"; allow_training: boolean };
type Key = { id: string; prefix: string; label: string; revoked: boolean; last_used_at?: string };
type Cat = { total: number; indexed: number; items: { id: string; title: string; image_url: string; price?: number; currency: string; category?: string; indexed: boolean; url: string }[] };
type An = { clicks: number; widget_searches: number; by_day: [string, number][]; top_products: { url: string; clicks: number }[] };
type In = {
  total_searches: number;
  top_categories: { category: string; searches: number; price_band?: { p25: number; median: number; p75: number } | null }[];
  unmet_demand: { category: string; query: string; searches: number }[];
  trending_colors: { category: string; color: string; searches: number }[];
};

export function Dashboard() {
  const router = useRouter();
  const { user, loading } = useMe();
  const [m, setM] = useState<M | null | undefined>(undefined);
  const [msg, setMsg] = useState<{ ok: boolean; t: string } | null>(null);

  const load = useCallback(
    () =>
      api<M>("/v1/merchant")
        .then(setM)
        .catch((e) => {
          if (e instanceof ApiError && e.status === 404) setM(null);
        }),
    [],
  );

  useEffect(() => {
    if (loading) return;
    if (!user) return router.replace("/login?next=/merchant");
    api<M>("/v1/merchant")
      .then(setM)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) setM(null);
      });
  }, [user, loading, router]);

  const run = async (fn: () => Promise<unknown>, ok: string) => {
    setMsg(null);
    try {
      await fn();
      setMsg({ ok: true, t: ok });
      await load();
    } catch (e) {
      setMsg({ ok: false, t: (e as Error).message });
    }
  };

  if (m === undefined) return <div className="mx-auto max-w-5xl px-4 py-10 text-muted">Loading…</div>;

  return (
    <div className="mx-auto max-w-5xl space-y-8 px-4 py-10">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-3xl font-extrabold">{m ? m.name : "Register your store"}</h1>
        {m && <span className="chip uppercase">{m.plan} plan · up to {m.limits.products.toLocaleString()} products</span>}
      </div>
      {msg && <p role="status" className={`rounded-lg px-3 py-2 text-sm ${msg.ok ? "bg-brand-soft text-brand" : "bg-danger-soft text-danger"}`}>{msg.t}</p>}
      {m === null ? (
        <Register onDone={async () => { await refreshMe(); await load(); }} />
      ) : (
        <>
          {!m.domain_verified && m.kind === "social" && (
            <section className="card space-y-2 border-accent p-5">
              <h2 className="text-lg font-bold">1. We&apos;re verifying @{m.domain.split("/")[1]}</h2>
              <p className="text-sm text-muted">Our team will DM your account a code within a day to confirm it&apos;s you. Then you can add products.</p>
            </section>
          )}
          {!m.domain_verified && m.kind === "store" && (
            <section className="card space-y-3 border-accent p-5">
              <h2 className="text-lg font-bold">1. Verify you own {m.domain}</h2>
              <p className="text-sm text-muted">Pick one. Option A works on Shopify and any hosted store.</p>
              <p className="text-sm font-semibold">A. Add a DNS TXT record on {m.domain}</p>
              <pre className="overflow-x-auto rounded-lg bg-ink p-3 text-sm text-bg">saasta-verify={m.verify_token}</pre>
              <p className="text-sm font-semibold">
                B. Or upload a file to <code className="rounded bg-bg px-1">{m.verify_url}</code> containing
              </p>
              <pre className="overflow-x-auto rounded-lg bg-ink p-3 text-sm text-bg">{m.verify_token}</pre>
              <button className="btn-primary" onClick={() => run(() => api("/v1/merchant/verify", { method: "POST" }), "Domain verified!")}>
                Check now
              </button>
            </section>
          )}
          <Catalog m={m} run={run} />
          <Keys m={m} />
          <Analytics />
          {m.limits.insights ? <Insights /> : <Upsell />}
        </>
      )}
    </div>
  );
}

function Register({ onDone }: { onDone: () => void }) {
  const [err, setErr] = useState<string | null>(null);
  const [kind, setKind] = useState<"store" | "social">("store");
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      await api("/v1/merchant", {
        method: "POST",
        body: JSON.stringify({
          name: f.get("name"),
          kind,
          domain: f.get("domain"),
          platform: f.get("platform") ?? "instagram",
          currency: f.get("currency"),
          allow_training: f.get("allow_training") === "on",
        }),
      });
      onDone();
    } catch (e) {
      setErr((e as Error).message);
    }
  }
  return (
    <form onSubmit={submit} className="card max-w-md space-y-3 p-5">
      <div className="grid grid-cols-2 gap-2">
        {(["store", "social"] as const).map((k) => (
          <button key={k} type="button" onClick={() => setKind(k)} className={`chip justify-center !py-2 !text-sm ${kind === k ? "!border-brand bg-brand text-brand-ink" : ""}`}>
            {k === "store" ? "I have a website" : "I sell on Instagram / TikTok"}
          </button>
        ))}
      </div>
      <input name="name" className="input" placeholder="Store / brand name" required minLength={2} maxLength={120} />
      {kind === "store" ? (
        <input name="domain" className="input" placeholder="Domain, e.g. mystore.pk" required maxLength={253} />
      ) : (
        <div className="grid grid-cols-[auto_1fr] gap-2">
          <select name="platform" className="input" defaultValue="instagram">
            <option value="instagram">Instagram</option>
            <option value="tiktok">TikTok</option>
          </select>
          <input name="domain" className="input" placeholder="@yourhandle" required maxLength={60} />
        </div>
      )}
      <select name="currency" className="input" defaultValue="PKR">
        {["PKR", "INR", "AED", "SAR", "GBP", "USD", "EUR"].map((c) => <option key={c}>{c}</option>)}
      </select>
      <label className="flex items-start gap-2 text-sm text-muted">
        <input type="checkbox" name="allow_training" className="mt-1" />
        <span>Let Saasta use my product photos to improve its try-on and search models (optional, you can change this later).</span>
      </label>
      {err && <p className="text-sm text-danger">{err}</p>}
      <button className="btn-primary w-full">Create</button>
    </form>
  );
}

function PhotoUpload({ run }: { run: (fn: () => Promise<unknown>, ok: string) => Promise<void> }) {
  return (
    <form
      className="grid gap-2 rounded-xl border border-line p-3 sm:grid-cols-[1fr_1fr_120px_auto]"
      onSubmit={(e) => {
        e.preventDefault();
        const form = e.currentTarget;
        const fd = new FormData(form);
        run(async () => {
          await api("/v1/merchant/catalog/photo", { method: "POST", body: fd });
          form.reset();
        }, "Product added. It becomes searchable in a minute.");
      }}
    >
      <input name="photo" type="file" accept="image/jpeg,image/png,image/webp" required className="input" />
      <input name="title" className="input" placeholder="Title, e.g. Red chiffon suit" required minLength={2} maxLength={300} />
      <input name="price" type="number" min={0} className="input" placeholder="Price" />
      <input name="link" type="url" className="input sm:col-span-3" placeholder="Link to your post or WhatsApp (https://wa.me/…)" required maxLength={2048} />
      <button className="btn-primary">Add product</button>
    </form>
  );
}

function Catalog({ m, run }: { m: M; run: (fn: () => Promise<unknown>, ok: string) => Promise<void> }) {
  const [cat, setCat] = useState<Cat | null>(null);
  const refresh = useCallback(() => api<Cat>("/v1/merchant/catalog").then(setCat).catch(() => {}), []);
  useEffect(() => {
    refresh();
  }, [refresh]);
  const disabled = !m.domain_verified;
  return (
    <section className="card space-y-4 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-bold">Products</h2>
        {cat && <p className="text-sm text-muted">{cat.total} listed · {cat.indexed} visually indexed</p>}
      </div>
      {m.kind === "store" && (
      <div className="flex flex-wrap gap-2">
        <button
          className="btn-primary"
          disabled={disabled}
          onClick={() => run(async () => { await api("/v1/merchant/catalog/shopify", { method: "POST", body: JSON.stringify({ max_products: 2000 }) }); await refresh(); }, "Shopify products imported. Visual indexing runs in the background.")}
        >
          Import from Shopify
        </button>
        <label className={`btn-ghost cursor-pointer ${disabled ? "pointer-events-none opacity-50" : ""}`}>
          Upload CSV feed
          <input
            type="file"
            accept=".csv,.tsv,text/csv,text/tab-separated-values"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (!f) return;
              const fd = new FormData();
              fd.append("file", f);
              run(async () => { await api("/v1/merchant/catalog/csv", { method: "POST", body: fd }); await refresh(); }, "Feed uploaded.");
            }}
          />
        </label>
        <button className="btn-ghost" onClick={() => refresh()}>Refresh</button>
      </div>
      )}
      <p className="text-xs text-muted">
        {m.kind === "social"
          ? "Add each product with a photo and a link to your Instagram/TikTok post or WhatsApp chat."
          : `CSV columns: id, title, link, image_link, price, availability, product_type (Merchant Center format). Product links must be on ${m.domain}.`}
      </p>
      {m.kind === "social" && m.domain_verified && <PhotoUpload run={run} />}
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
        {cat?.items.map((i) => (
          <a key={i.id} href={i.url} target="_blank" rel="noopener noreferrer" className="rounded-xl border border-line p-1 text-xs">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={i.image_url} alt="" referrerPolicy="no-referrer" className="aspect-square w-full rounded-lg object-cover" />
            <p className="truncate pt-1">{i.title}</p>
            <p className="text-muted">{money(i.price, i.currency)} {i.indexed ? "✓" : "…"}</p>
          </a>
        ))}
      </div>
    </section>
  );
}

function Keys({ m }: { m: M }) {
  const [keys, setKeys] = useState<Key[]>([]);
  const [fresh, setFresh] = useState<string | null>(null);
  const load = useCallback(() => api<Key[]>("/v1/merchant/keys").then(setKeys).catch(() => {}), []);
  useEffect(() => {
    load();
  }, [load]);
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  return (
    <section className="card space-y-4 p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold">Search-by-photo widget</h2>
        <button
          className="btn-primary"
          onClick={async () => {
            const k = await api<{ key: string }>("/v1/merchant/keys", { method: "POST", body: JSON.stringify({ label: "website" }) });
            setFresh(k.key);
            load();
          }}
        >
          New key
        </button>
      </div>
      {!m.limits.widget && (
        <p className="rounded-xl bg-accent-soft p-3 text-sm">
          The widget is part of the Growth plan. Keys you create now will start working as soon as you upgrade.
        </p>
      )}
      {fresh && (
        <div className="space-y-2 rounded-xl bg-accent-soft p-3 text-sm">
          <p className="font-semibold">Copy this snippet now. The key won&apos;t be shown again.</p>
          <pre className="overflow-x-auto rounded-lg bg-ink p-3 text-xs text-bg">{`<script src="${origin}/widget.js" data-key="${fresh}" async></script>`}</pre>
          <p className="text-xs text-muted">Works only on {m.domain} and its subdomains.</p>
        </div>
      )}
      <ul className="divide-y divide-line text-sm">
        {keys.map((k) => (
          <li key={k.id} className="flex items-center justify-between py-2">
            <span><code>{k.prefix}…</code> {k.label} {k.revoked && <span className="text-danger">(revoked)</span>}</span>
            {!k.revoked && (
              <button className="text-xs text-danger underline" onClick={async () => { await api(`/v1/merchant/keys/${k.id}`, { method: "DELETE" }); load(); }}>
                Revoke
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function Analytics() {
  const [a, setA] = useState<An | null>(null);
  useEffect(() => {
    api<An>("/v1/merchant/analytics").then(setA).catch(() => {});
  }, []);
  if (!a) return null;
  const peak = Math.max(1, ...a.by_day.map(([, n]) => n));
  return (
    <section className="card space-y-4 p-5">
      <h2 className="text-lg font-bold">Last 30 days</h2>
      <div className="grid grid-cols-2 gap-3">
        <Stat label="Clicks to your store" v={a.clicks} />
        <Stat label="Widget searches" v={a.widget_searches} />
      </div>
      {a.by_day.length > 0 && (
        <div className="flex h-24 items-end gap-1" aria-label="Clicks per day">
          {a.by_day.map(([d, n]) => (
            <div key={d} title={`${d}: ${n}`} className="flex-1 rounded-t bg-brand" style={{ height: `${(n / peak) * 100}%` }} />
          ))}
        </div>
      )}
    </section>
  );
}

function Insights() {
  const [i, setI] = useState<In | null>(null);
  useEffect(() => {
    api<In>("/v1/merchant/insights").then(setI).catch(() => {});
  }, []);
  if (!i) return null;
  return (
    <section className="card space-y-5 p-5">
      <div>
        <h2 className="text-lg font-bold">Demand radar</h2>
        <p className="text-sm text-muted">From {i.total_searches.toLocaleString()} anonymous searches in your country. Queries searched by fewer than 3 people are hidden.</p>
      </div>
      <div className="grid gap-5 md:grid-cols-3">
        <div>
          <p className="mb-2 text-sm font-semibold">Top categories</p>
          {i.top_categories.map((c) => (
            <p key={c.category} className="flex justify-between border-b border-line py-1 text-sm">
              <span>{c.category}</span>
              <span className="text-muted">{c.searches}{c.price_band ? ` · ~${money(c.price_band.median)}` : ""}</span>
            </p>
          ))}
        </div>
        <div>
          <p className="mb-2 text-sm font-semibold">Wanted but not found</p>
          {i.unmet_demand.length === 0 && <p className="text-sm text-muted">Not enough data yet.</p>}
          {i.unmet_demand.map((u) => (
            <p key={u.query} className="border-b border-line py-1 text-sm">{u.query} <span className="text-muted">· {u.searches}</span></p>
          ))}
        </div>
        <div>
          <p className="mb-2 text-sm font-semibold">Trending colours</p>
          {i.trending_colors.map((c) => (
            <p key={c.category + c.color} className="border-b border-line py-1 text-sm">{c.color} {c.category} <span className="text-muted">· {c.searches}</span></p>
          ))}
        </div>
      </div>
    </section>
  );
}

function Upsell() {
  return (
    <section className="card space-y-2 border-accent p-5">
      <h2 className="text-lg font-bold">Demand radar (Growth plan)</h2>
      <p className="text-sm text-muted">
        See what shoppers in your country searched for and couldn&apos;t find, the price band they expect per category,
        and which colours are trending. Founding partners get Growth free for 3 months. Contact us to switch.
      </p>
      <a className="btn-primary" href="mailto:stores@saasta.pk?subject=Growth%20plan">Upgrade to Growth</a>
    </section>
  );
}

function Stat({ label, v }: { label: string; v: number }) {
  return (
    <div className="rounded-xl bg-bg p-4">
      <p className="text-3xl font-extrabold">{v.toLocaleString()}</p>
      <p className="text-sm text-muted">{label}</p>
    </div>
  );
}
