"use client";
import { useRef, useState } from "react";

export type Box = { x: number; y: number; w: number; h: number }; // fractions of the image, 0..1

/** Drag on the image to select the one item you want (e.g. just the bag in an outfit photo). */
export function Cropper({ src, box, onChange }: { src: string; box: Box | null; onChange: (b: Box | null) => void }) {
  const wrap = useRef<HTMLDivElement>(null);
  const [start, setStart] = useState<{ x: number; y: number } | null>(null);

  const point = (e: React.PointerEvent) => {
    const r = wrap.current!.getBoundingClientRect();
    return {
      x: Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)),
      y: Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)),
    };
  };

  return (
    <div className="flex flex-col items-center gap-1" onClick={(e) => e.stopPropagation()}>
      <div
        ref={wrap}
        className="relative cursor-crosshair touch-none select-none overflow-hidden rounded-lg"
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture(e.pointerId);
          const p = point(e);
          setStart(p);
          onChange({ x: p.x, y: p.y, w: 0, h: 0 });
        }}
        onPointerMove={(e) => {
          if (!start) return;
          const p = point(e);
          onChange({ x: Math.min(start.x, p.x), y: Math.min(start.y, p.y), w: Math.abs(p.x - start.x), h: Math.abs(p.y - start.y) });
        }}
        onPointerUp={() => {
          setStart(null);
          if (box && (box.w < 0.05 || box.h < 0.05)) onChange(null);
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={src} alt="Your upload" draggable={false} className="max-h-64 rounded-lg object-contain" />
        {box && box.w > 0 && (
          <div
            className="pointer-events-none absolute rounded-md border-2 border-accent shadow-[0_0_0_9999px_rgba(0,0,0,.45)]"
            style={{ left: `${box.x * 100}%`, top: `${box.y * 100}%`, width: `${box.w * 100}%`, height: `${box.h * 100}%` }}
          />
        )}
      </div>
      <p className="text-xs text-muted">{box ? "Searching only the selected area" : "Tip: drag a box around one item to search just that"}</p>
    </div>
  );
}

export async function cropFile(file: File, box: Box): Promise<File> {
  const bmp = await createImageBitmap(file);
  const sx = Math.round(box.x * bmp.width);
  const sy = Math.round(box.y * bmp.height);
  const sw = Math.max(64, Math.round(box.w * bmp.width));
  const sh = Math.max(64, Math.round(box.h * bmp.height));
  const canvas = document.createElement("canvas");
  canvas.width = sw;
  canvas.height = sh;
  canvas.getContext("2d")!.drawImage(bmp, sx, sy, sw, sh, 0, 0, sw, sh);
  const blob = await new Promise<Blob>((res, rej) => canvas.toBlob((b) => (b ? res(b) : rej(new Error("crop failed"))), "image/jpeg", 0.92));
  return new File([blob], "crop.jpg", { type: "image/jpeg" });
}
