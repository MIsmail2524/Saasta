import type { Metadata } from "next";
import { notFound } from "next/navigation";

const API = process.env.SAASTA_API_INTERNAL_URL ?? "http://localhost:8000";

type Board = { id: string; title: string; note?: string; total: number; items: { title: string; url: string; image?: string; price?: number; domain: string }[] };

async function load(id: string): Promise<Board | null> {
  if (!/^[a-f0-9]{32}$/.test(id)) return null;
  const r = await fetch(`${API}/v1/boards/${id}`, { cache: "no-store" });
  return r.ok ? r.json() : null;
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const b = await load((await params).id);
  return { title: b ? b.title : "Board" };
}

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const b = await load((await params).id);
  if (!b) notFound();
  const fmt = (v?: number) => (v == null ? "" : `Rs ${Math.round(v).toLocaleString("en-PK")}`);
  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <p className="text-sm font-semibold text-accent">Saasta look board</p>
      <h1 className="text-3xl font-extrabold">{b.title}</h1>
      {b.note && <p className="mt-2 text-muted">{b.note}</p>}
      <p className="mt-2 font-semibold">Total: {fmt(b.total)}</p>
      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {b.items.map((i) => (
          <a key={i.url} href={i.url} target="_blank" rel="noopener noreferrer nofollow" className="card overflow-hidden">
            {i.image && (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img src={i.image} alt="" referrerPolicy="no-referrer" className="aspect-square w-full object-contain" />
            )}
            <div className="p-3">
              <p className="line-clamp-2 text-sm">{i.title}</p>
              <p className="mt-1 text-xs text-muted">{i.domain}</p>
              <p className="font-bold">{fmt(i.price)}</p>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}
