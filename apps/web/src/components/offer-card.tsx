"use client";
import Link from "next/link";
import { useState } from "react";
import { api, money, outUrl, type Offer } from "@/lib/api";

const SOURCE: Record<string, string> = {
  google_lens: "Web",
  google_shopping: "Shopping",
  instagram: "Instagram",
  tiktok: "TikTok",
  partner: "Partner",
};

export function TrustBadge({ trust }: { trust: Offer["trust"] }) {
  const [open, setOpen] = useState(false);
  if (!trust?.level) return null;
  const tone =
    trust.level === "high"
      ? "bg-brand-soft text-brand"
      : trust.level === "medium"
        ? "bg-accent-soft text-ink"
        : "bg-danger-soft text-danger";
  return (
    <span className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${tone}`}
        aria-expanded={open}
      >
        Trust {trust.score}
      </button>
      {open && trust.reasons.length > 0 && (
        <span className="absolute left-0 top-7 z-20 w-64 rounded-xl border border-line bg-surface p-3 text-xs shadow-lg">
          {trust.reasons.map((r) => (
            <span key={r} className={`block py-0.5 ${r.startsWith("-") ? "text-danger" : "text-ok"}`}>
              {r}
            </span>
          ))}
        </span>
      )}
    </span>
  );
}

export function OfferCard({
  o,
  currency,
  tryOnCategory,
  onSave,
}: {
  o: Offer;
  currency: string;
  tryOnCategory?: string | null;
  onSave?: (o: Offer) => void;
}) {
  const [watched, setWatched] = useState<"idle" | "ok" | "login">("idle");
  const price = money(o.price_local ?? o.price, o.price_local != null ? currency : (o.currency ?? currency));

  async function watch() {
    try {
      await api("/v1/me/watches", {
        method: "POST",
        body: JSON.stringify({
          title: o.title.slice(0, 300),
          url: o.url,
          image_url: o.image ?? null,
          price: o.price_local ?? null,
          currency,
        }),
      });
      setWatched("ok");
    } catch {
      setWatched("login");
    }
  }

  return (
    <article className="card flex flex-col overflow-hidden">
      <a href={outUrl(o.out)} target="_blank" rel="noopener noreferrer nofollow" className="relative block aspect-square bg-bg">
        {o.image ? (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img src={o.image} alt="" loading="lazy" referrerPolicy="no-referrer" className="h-full w-full object-contain" />
        ) : (
          <div className="flex h-full items-center justify-center text-muted">No image</div>
        )}
        <span className="absolute left-2 top-2 flex gap-1">
          {o.partner && <span className="rounded-full bg-brand px-2 py-0.5 text-[11px] font-bold text-brand-ink">Partner</span>}
          {o.match === "exact" && <span className="rounded-full bg-ink px-2 py-0.5 text-[11px] font-bold text-bg">Exact match</span>}
        </span>
      </a>
      <div className="flex flex-1 flex-col gap-2 p-3">
        <div className="flex items-center justify-between gap-2 text-xs text-muted">
          <span className="truncate">{o.seller || o.domain}</span>
          <span className="shrink-0">{SOURCE[o.source] ?? o.source}</span>
        </div>
        <p className="line-clamp-2 text-sm font-medium">{o.title}</p>
        <div className="mt-auto flex items-end justify-between gap-2">
          <div>
            <p className="text-lg font-extrabold">{price ?? <span className="text-sm font-medium text-muted">Price on site</span>}</p>
            {o.rating != null && (
              <p className="text-xs text-muted">
                ★ {o.rating} {o.reviews ? `(${o.reviews.toLocaleString()})` : ""}
              </p>
            )}
          </div>
          <TrustBadge trust={o.trust} />
        </div>
        <div className="flex gap-1.5 pt-1">
          <a href={outUrl(o.out)} target="_blank" rel="noopener noreferrer nofollow" className="btn-primary flex-1 !px-2 !py-2 text-xs">
            Visit store
          </a>
          <button type="button" onClick={watch} className="btn-ghost !px-2 !py-2 text-xs" title="Track price">
            {watched === "ok" ? "Watching ✓" : "Watch"}
          </button>
          {onSave && (
            <button type="button" onClick={() => onSave(o)} className="btn-ghost !px-2 !py-2 text-xs" title="Save to board">
              Save
            </button>
          )}
        </div>
        {tryOnCategory && o.image && (
          <Link
            href={`/try-on?g=${encodeURIComponent(o.image)}&c=${tryOnCategory}`}
            className="text-center text-xs font-semibold text-brand hover:underline"
          >
            Try it on →
          </Link>
        )}
        {watched === "login" && (
          <p className="text-xs text-danger">
            <Link href="/login" className="underline">Log in</Link> to track prices.
          </p>
        )}
      </div>
    </article>
  );
}
