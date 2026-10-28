"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useMe } from "@/lib/use-me";

const CATS = [
  ["auto", "Auto-detect"],
  ["tops", "Top / shirt / kurta"],
  ["bottoms", "Trousers / skirt"],
  ["one-pieces", "Dress / full suit"],
  ["shoes", "Shoes"],
  ["bags", "Bag"],
  ["jewellery", "Necklace / set"],
  ["earrings", "Earrings / jhumkay"],
  ["watches", "Watch"],
  ["eyewear", "Glasses"],
];

export function TryOn() {
  const params = useSearchParams();
  const { user, loading } = useMe();
  const [garment, setGarment] = useState(params.get("g") ?? "");
  const [cat, setCat] = useState(CATS.some(([k]) => k === params.get("c")) ? params.get("c")! : "auto");
  const [photo, setPhoto] = useState<File | null>(null);
  const [consent, setConsent] = useState(false);
  const [job, setJob] = useState<{ id: string; status: string; output_url?: string; error?: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const preview = useMemo(() => (photo ? URL.createObjectURL(photo) : null), [photo]);
  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview);
  }, [preview]);

  useEffect(() => {
    if (!job || job.status !== "running") return;
    const t = setTimeout(async () => {
      try {
        setJob(await api(`/v1/tryon/${job.id}`));
      } catch (e) {
        setError((e as Error).message);
      }
    }, 2500);
    return () => clearTimeout(t);
  }, [job]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!photo) return setError("Add a full-body or half-body photo of yourself.");
    const fd = new FormData();
    fd.append("photo", photo);
    fd.append("garment_url", garment);
    fd.append("category", cat);
    fd.append("consent", String(consent));
    setBusy(true);
    setError(null);
    try {
      setJob(await api("/v1/tryon", { method: "POST", body: fd }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <h1 className="text-3xl font-extrabold">Try it on before you buy</h1>
      <p className="mt-1 max-w-2xl text-muted">
        See how a find looks on you: clothes, eastern suits, shoes, bags and jewellery. Runs on Saasta&apos;s own
        models. Your photo is used for this try-on only and never kept.
      </p>
      {!loading && !user ? (
        <div className="card mt-6 p-6">
          <p>Please <Link className="font-semibold text-brand underline" href="/login?next=/try-on">log in</Link> to use try-on.</p>
        </div>
      ) : (
        <div className="mt-6 grid gap-6 md:grid-cols-2">
          <form onSubmit={submit} className="card space-y-4 p-5">
            <label className="block text-sm font-semibold">
              Your photo
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                capture="user"
                className="input mt-1"
                onChange={(e) => setPhoto(e.target.files?.[0] ?? null)}
              />
            </label>
            {preview && (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img src={preview} alt="You" className="h-48 rounded-xl object-contain" />
            )}
            <label className="block text-sm font-semibold">
              Product image link
              <input className="input mt-1" type="url" required value={garment} onChange={(e) => setGarment(e.target.value)} maxLength={2048} placeholder="https://…" />
            </label>
            <label className="block text-sm font-semibold">
              What is it?
              <select className="input mt-1" value={cat} onChange={(e) => setCat(e.target.value)}>
                {CATS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              </select>
            </label>
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" className="mt-1" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
              <span>This is a photo of me (or I have permission), and I agree to Saasta processing it for this try-on.</span>
            </label>
            {error && <p role="alert" className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
            <button className="btn-primary w-full" disabled={busy || !consent || job?.status === "running"}>
              {busy || job?.status === "running" ? "Creating your look…" : "Try it on"}
            </button>
          </form>
          <div className="card flex min-h-80 items-center justify-center p-4">
            {job?.status === "done" && job.output_url ? (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img src={job.output_url} alt="Try-on result" className="max-h-[560px] rounded-xl object-contain" />
            ) : job?.status === "failed" ? (
              <p className="text-danger">{job.error}</p>
            ) : job ? (
              <p className="animate-pulse text-muted">Creating your look… this can take up to a minute</p>
            ) : garment ? (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img src={garment} alt="Product" referrerPolicy="no-referrer" className="max-h-96 object-contain" />
            ) : (
              <p className="text-muted">Your result will appear here.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
