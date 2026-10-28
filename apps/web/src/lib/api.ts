export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const field = Array.isArray(data?.errors) && data.errors[0];
    const msg = field
      ? `${field.field ? `${field.field}: ` : ""}${String(field.msg).replace(/^Value error, /, "")}`
      : typeof data?.detail === "string"
        ? data.detail
        : res.status === 429
          ? "Too many requests, please wait a moment."
          : "Something went wrong.";
    throw new ApiError(res.status, msg);
  }
  return data as T;
}

export async function api<T = unknown>(path: string, init: RequestInit = {}): Promise<T> {
  const isForm = init.body instanceof FormData;
  const res = await fetch(`/api${path}`, {
    ...init,
    credentials: "same-origin",
    headers: isForm ? init.headers : { "Content-Type": "application/json", ...(init.headers || {}) },
  });
  return handle<T>(res);
}

export const mediaUrl = (key?: string | null) => (key ? `/api/v1/media/${key}` : undefined);
export const outUrl = (out?: string) => (out ? `/api${out}` : undefined);

export function money(v?: number | null, cur = "PKR") {
  if (v == null) return null;
  try {
    return new Intl.NumberFormat("en-PK", { style: "currency", currency: cur, maximumFractionDigits: 0 }).format(v);
  } catch {
    return `${cur} ${Math.round(v).toLocaleString()}`;
  }
}

export type Trust = { score: number; level: "high" | "medium" | "low"; reasons: string[] };
export type Offer = {
  title: string;
  url: string;
  out?: string;
  source: string;
  domain: string;
  image?: string | null;
  price?: number | null;
  currency?: string | null;
  price_local?: number | null;
  rating?: number | null;
  reviews?: number | null;
  seller?: string | null;
  in_stock?: boolean | null;
  match: "exact" | "similar";
  partner: boolean;
  similarity?: number | null;
  trust: Trust;
};
export type SearchResult = {
  understanding: {
    query?: string;
    category?: string;
    color?: string;
    tryon_category?: string | null;
    attributes?: string[];
    max_price?: number | null;
  };
  price?: { min: number; median: number; max: number; count: number; basis: string } | null;
  best_deal?: Offer | null;
  exact: Offer[];
  similar: Offer[];
  dupes: Offer[];
  social: Offer[];
  sources: { engine: "model" | "fingerprint"; indexed: number };
  currency: string;
};
export type SearchDoc = {
  id: string;
  status: "queued" | "running" | "done" | "failed";
  error?: string | null;
  kind: string;
  image?: string | null;
  result?: (SearchResult & { kind: string; image?: string }) | { kind: "video"; looks: (SearchResult & { t: number; image: string })[] } | null;
};
export type User = { id: string; email: string; name?: string | null; role: string };
