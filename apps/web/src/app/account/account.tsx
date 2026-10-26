"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, mediaUrl, money } from "@/lib/api";
import { refreshMe, useMe } from "@/lib/use-me";

type Hist = { id: string; image?: string; query?: string; category?: string; best_price?: number; created_at: string; status: string };
type W = { id: string; title: string; url: string; image_url?: string; last_price?: number; target_price?: number; currency: string; history: { price: number }[] };
type B = { id: string; title: string; public: boolean; count: number };

export function Account() {
  const router = useRouter();
  const { user, loading } = useMe();
  const [hist, setHist] = useState<Hist[]>([]);
  const [watches, setWatches] = useState<W[]>([]);
  const [boards, setBoards] = useState<B[]>([]);

  useEffect(() => {
    if (loading) return;
    if (!user) return router.replace("/login?next=/account");
    api<Hist[]>("/v1/me/history").then(setHist).catch(() => {});
    api<W[]>("/v1/me/watches").then(setWatches).catch(() => {});
    api<B[]>("/v1/me/boards").then(setBoards).catch(() => {});
  }, [user, loading, router]);

  async function logout(all = false) {
    await api(`/v1/auth/${all ? "logout-all" : "logout"}`, { method: "POST" }).catch(() => {});
    await refreshMe();
    // Full reload so every component drops the old session state.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.href = "/";
  }

  async function deleteAccount() {
    if (!confirm("Delete your account, watches and boards permanently? This cannot be undone.")) return;
    await api("/v1/auth/me", { method: "DELETE" });
    await refreshMe();
    // Full reload so every component drops the old session state.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.href = "/";
  }

  if (!user) return null;
  return (
    <div className="mx-auto max-w-5xl space-y-10 px-4 py-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-extrabold">Salaam, {user.name || user.email.split("@")[0]}</h1>
          <p className="text-muted">{user.email}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {user.role !== "shopper" && <Link className="btn-ghost" href="/merchant">Store dashboard</Link>}
          <button className="btn-ghost" onClick={() => logout()}>Log out</button>
          <button className="btn-ghost" onClick={() => logout(true)}>Log out everywhere</button>
        </div>
      </div>

      <section>
        <h2 className="text-xl font-bold">Price watches</h2>
        {watches.length === 0 ? (
          <p className="mt-2 text-sm text-muted">Tap “Watch” on any result to track its price.</p>
        ) : (
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {watches.map((w) => {
              const first = w.history[0]?.price;
              const change = first && w.last_price ? Math.round(((w.last_price - first) / first) * 100) : 0;
              return (
                <div key={w.id} className="card flex gap-3 p-3">
                  {w.image_url && (
                    /* eslint-disable-next-line @next/next/no-img-element */
                    <img src={w.image_url} alt="" referrerPolicy="no-referrer" className="h-20 w-20 rounded-lg object-cover" />
                  )}
                  <div className="min-w-0 flex-1">
                    <a href={w.url} target="_blank" rel="noopener noreferrer nofollow" className="line-clamp-2 text-sm font-medium hover:underline">{w.title}</a>
                    <p className="mt-1 font-bold">
                      {money(w.last_price, w.currency) ?? "Checking…"}{" "}
                      {change !== 0 && <span className={change < 0 ? "text-ok" : "text-danger"}>{change > 0 ? "+" : ""}{change}%</span>}
                    </p>
                    <button
                      className="text-xs text-muted underline"
                      onClick={async () => {
                        await api(`/v1/me/watches/${w.id}`, { method: "DELETE" });
                        setWatches((x) => x.filter((y) => y.id !== w.id));
                      }}
                    >
                      Stop watching
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <section>
        <h2 className="text-xl font-bold">Look boards</h2>
        {boards.length === 0 ? (
          <p className="mt-2 text-sm text-muted">Save results from a search to build a shareable board.</p>
        ) : (
          <div className="mt-3 flex flex-wrap gap-2">
            {boards.map((b) => (
              <Link key={b.id} href={`/b/${b.id}`} className="chip !py-2 !text-sm">{b.title} · {b.count}</Link>
            ))}
          </div>
        )}
      </section>

      <section>
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold">Recent searches</h2>
          {hist.length > 0 && (
            <button
              className="text-sm text-muted underline"
              onClick={async () => {
                await api("/v1/me/history", { method: "DELETE" });
                setHist([]);
              }}
            >
              Clear history
            </button>
          )}
        </div>
        <div className="mt-3 grid grid-cols-3 gap-3 sm:grid-cols-6">
          {hist.map((h) => (
            <Link key={h.id} href={`/s/${h.id}`} className="card overflow-hidden">
              {h.image ? (
                /* eslint-disable-next-line @next/next/no-img-element */
                <img src={mediaUrl(h.image)} alt="" className="aspect-square w-full object-cover" />
              ) : (
                <div className="flex aspect-square items-center justify-center p-2 text-center text-xs text-muted">{h.query || "Text search"}</div>
              )}
              <p className="truncate p-2 text-xs">{h.best_price ? `from ${money(h.best_price)}` : h.category || h.status}</p>
            </Link>
          ))}
        </div>
      </section>

      <section className="card border-danger/40 p-5">
        <h2 className="font-bold">Delete account</h2>
        <p className="mt-1 text-sm text-muted">Removes your account, watches, boards and try-ons. Your past searches are detached from you.</p>
        <button className="btn mt-3 bg-danger text-white" onClick={deleteAccount}>Delete my account</button>
      </section>
    </div>
  );
}
