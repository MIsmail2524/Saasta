import Link from "next/link";
import { AccountLink } from "./account-link";

export function Logo({ small = false }: { small?: boolean }) {
  return (
    <Link href="/" className="flex items-center gap-2" aria-label="Saasta home">
      <svg viewBox="0 0 64 64" className={small ? "h-7 w-7" : "h-8 w-8"} aria-hidden>
        <rect width="64" height="64" rx="16" fill="var(--brand)" />
        <circle cx="28" cy="28" r="13" fill="none" stroke="var(--brand-ink)" strokeWidth="6" />
        <path d="M38 38l11 11" stroke="var(--accent)" strokeWidth="7" strokeLinecap="round" />
      </svg>
      <span className="text-xl font-extrabold tracking-tight">Saasta</span>
      <span className="font-urdu text-lg leading-none text-brand" lang="ur" dir="rtl">سستا</span>
    </Link>
  );
}

export function Header() {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-bg/85 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4">
        <Logo />
        <nav className="flex items-center gap-1 text-sm">
          <Link href="/stores" className="hidden rounded-lg px-3 py-2 font-medium hover:bg-brand-soft sm:block">
            For stores
          </Link>
          <Link href="/try-on" className="hidden rounded-lg px-3 py-2 font-medium hover:bg-brand-soft sm:block">
            Try on
          </Link>
          <AccountLink />
        </nav>
      </div>
    </header>
  );
}

export function Footer() {
  return (
    <footer className="mt-20 border-t border-line">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-10 text-sm sm:grid-cols-4">
        <div className="sm:col-span-2">
          <Logo small />
          <p className="mt-3 max-w-sm text-muted">
            Dekho. Dhoondo. Saasta lo. Find where anything you see is sold, at the best price, from sellers you can trust.
          </p>
        </div>
        <div className="space-y-2">
          <p className="font-semibold">Product</p>
          <Link className="block text-muted hover:text-ink" href="/">Search</Link>
          <Link className="block text-muted hover:text-ink" href="/try-on">Virtual try-on</Link>
          <Link className="block text-muted hover:text-ink" href="/account">My watches & boards</Link>
        </div>
        <div className="space-y-2">
          <p className="font-semibold">Company</p>
          <Link className="block text-muted hover:text-ink" href="/stores">Saasta for stores</Link>
          <Link className="block text-muted hover:text-ink" href="/privacy">Privacy</Link>
          <Link className="block text-muted hover:text-ink" href="/bot">SaastaBot</Link>
          <Link className="block text-muted hover:text-ink" href="/terms">Terms</Link>
        </div>
      </div>
      <p className="pb-8 text-center text-xs text-muted">© {new Date().getFullYear()} Saasta. Prices and availability come from third-party sellers and may change.</p>
    </footer>
  );
}
