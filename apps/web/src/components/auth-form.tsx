"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { refreshMe } from "@/lib/use-me";

// Only allow same-site relative redirects after login (no open redirect via ?next=).
function safeNext(n: string | null) {
  return n && n.startsWith("/") && !n.startsWith("//") && !n.startsWith("/\\") ? n : "/";
}

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const params = useSearchParams();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const body: Record<string, string> = { email: String(f.get("email")), password: String(f.get("password")) };
    if (mode === "signup" && f.get("name")) body.name = String(f.get("name"));
    setBusy(true);
    setError(null);
    try {
      await api(`/v1/auth/${mode}`, { method: "POST", body: JSON.stringify(body) });
      await refreshMe();
      router.push(safeNext(params.get("next")));
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  const other = mode === "login" ? "signup" : "login";
  const next = params.get("next");
  return (
    <div className="mx-auto max-w-sm px-4 py-16">
      <h1 className="text-3xl font-extrabold">{mode === "login" ? "Welcome back" : "Create your account"}</h1>
      <p className="mt-1 text-muted">
        {mode === "login" ? "Log in to see your watches and boards." : "Track prices, save looks and try things on."}
      </p>
      <form onSubmit={submit} className="mt-6 space-y-3">
        {mode === "signup" && <input name="name" className="input" placeholder="Name (optional)" maxLength={120} autoComplete="name" />}
        <input name="email" type="email" required className="input" placeholder="Email" autoComplete="email" maxLength={320} />
        <input
          name="password"
          type="password"
          required
          minLength={mode === "signup" ? 10 : 1}
          maxLength={128}
          className="input"
          placeholder={mode === "signup" ? "Password (10+ characters)" : "Password"}
          autoComplete={mode === "signup" ? "new-password" : "current-password"}
        />
        {error && <p role="alert" className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
        <button className="btn-primary w-full" disabled={busy}>
          {busy ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}
        </button>
      </form>
      <p className="mt-4 text-sm text-muted">
        {mode === "login" ? "New to Saasta?" : "Already have an account?"}{" "}
        <Link className="font-semibold text-brand" href={`/${other}${next ? `?next=${encodeURIComponent(safeNext(next))}` : ""}`}>
          {mode === "login" ? "Create an account" : "Log in"}
        </Link>
      </p>
    </div>
  );
}
