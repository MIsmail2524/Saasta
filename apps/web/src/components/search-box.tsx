"use client";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { type Box, Cropper, cropFile } from "./cropper";

const MAX_IMAGE = 10 * 1024 * 1024;
const MAX_VIDEO = 60 * 1024 * 1024;
const EXAMPLES = ["same but in black", "under 5000", "khussa like this under 3k", "cheaper dupe"];

export function SearchBox({ compact = false }: { compact?: boolean }) {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [box, setBox] = useState<Box | null>(null);
  const [link, setLink] = useState("");
  const [text, setText] = useState("");
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pick = useCallback((f: File | null | undefined) => {
    setError(null);
    if (!f) return;
    const isVideo = f.type.startsWith("video/");
    if (!isVideo && !f.type.startsWith("image/")) return setError("Pick a photo or a short video.");
    if (f.size > (isVideo ? MAX_VIDEO : MAX_IMAGE))
      return setError(isVideo ? "Video must be under 60 MB." : "Photo must be under 10 MB.");
    setFile(f);
    setBox(null);
    setLink("");
  }, []);

  const preview = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview);
  }, [preview]);

  // Paste a screenshot straight from the clipboard.
  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const item = Array.from(e.clipboardData?.items ?? []).find((i) => i.type.startsWith("image/"));
      if (item) pick(item.getAsFile());
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [pick]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file && !link.trim() && !text.trim()) return setError("Add a photo, video, link or a few words.");
    setBusy(true);
    setError(null);
    const fd = new FormData();
    if (file) fd.append("file", box && !file.type.startsWith("video/") ? await cropFile(file, box) : file);
    else if (link.trim()) fd.append("url", link.trim());
    if (text.trim()) fd.append("text", text.trim());
    try {
      const r = await api<{ id: string }>("/v1/searches", { method: "POST", body: fd });
      router.push(`/s/${r.id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  const isVideo = file?.type.startsWith("video/");

  return (
    <form onSubmit={submit} className="card w-full p-3 shadow-[0_10px_40px_-20px_rgba(14,92,70,.35)] sm:p-4">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          pick(e.dataTransfer.files?.[0]);
        }}
        onClick={() => !file && input.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
        className={`relative flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed text-center transition ${
          compact ? "min-h-28 p-4" : "min-h-48 p-6"
        } ${drag ? "border-brand bg-brand-soft" : "border-line hover:border-brand/60"}`}
      >
        <input
          ref={input}
          type="file"
          accept="image/jpeg,image/png,image/webp,video/mp4,video/webm,video/quicktime"
          className="hidden"
          onChange={(e) => pick(e.target.files?.[0])}
        />
        {preview ? (
          <div className="flex flex-col items-center gap-4 sm:flex-row">
            {isVideo ? (
              <video src={preview} className="h-32 rounded-lg" muted autoPlay loop playsInline />
            ) : (
              <Cropper src={preview} box={box} onChange={setBox} />
            )}
            <div className="text-left text-sm">
              <p className="font-semibold">{isVideo ? "Video ready: we'll find every item in it" : "Photo ready"}</p>
              <div className="mt-1 flex gap-3">
                <button
                  type="button"
                  className="text-muted underline"
                  onClick={(e) => {
                    e.stopPropagation();
                    setFile(null);
                    setBox(null);
                  }}
                >
                  Remove
                </button>
                <button type="button" className="text-muted underline" onClick={(e) => { e.stopPropagation(); input.current?.click(); }}>
                  Change
                </button>
                {box && (
                  <button type="button" className="text-muted underline" onClick={(e) => { e.stopPropagation(); setBox(null); }}>
                    Clear selection
                  </button>
                )}
              </div>
            </div>
          </div>
        ) : (
          <>
            <svg viewBox="0 0 24 24" className="h-9 w-9 text-brand" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden>
              <path d="M4 7h3l2-3h6l2 3h3v12H4z" />
              <circle cx="12" cy="13" r="3.5" />
            </svg>
            <p className="font-semibold">Drop a photo or reel here, or tap to upload</p>
            <p className="text-xs text-muted">Clothes, shoes, bags, jewellery, watches. You can also paste a screenshot (Ctrl+V).</p>
          </>
        )}
      </div>

      <div className={`mt-3 grid gap-2 ${compact ? "" : "sm:grid-cols-[1fr_1fr_auto]"}`}>
        <input
          className="input"
          type="url"
          inputMode="url"
          placeholder="…or paste an Instagram / TikTok / product link"
          value={link}
          onChange={(e) => {
            setLink(e.target.value);
            if (e.target.value) setFile(null);
          }}
          maxLength={2048}
        />
        <input
          className="input"
          placeholder='Refine: "same but black under 5k"'
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={300}
        />
        <button className="btn-primary h-11 px-6" disabled={busy}>
          {busy ? "Searching…" : "Dhoondo"}
        </button>
      </div>
      {!compact && (
        <div className="mt-3 flex flex-wrap gap-2">
          {EXAMPLES.map((x) => (
            <button key={x} type="button" className="chip hover:border-brand" onClick={() => setText(x)}>
              {x}
            </button>
          ))}
        </div>
      )}
      {error && (
        <p role="alert" className="mt-3 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}
    </form>
  );
}
