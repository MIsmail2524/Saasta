"use client";
import Link from "next/link";
import { useMe } from "@/lib/use-me";

export function AccountLink() {
  const { user, loading } = useMe();
  if (loading) return <span className="w-20" />;
  if (!user)
    return (
      <Link href="/login" className="btn-primary !py-2">
        Log in
      </Link>
    );
  return (
    <>
      {user.role !== "shopper" && (
        <Link href="/merchant" className="hidden rounded-lg px-3 py-2 font-medium hover:bg-brand-soft sm:block">
          Store dashboard
        </Link>
      )}
      <Link href="/account" className="btn-ghost max-w-36 !py-2">
        <span className="truncate">{user.name || user.email.split("@")[0]}</span>
      </Link>
    </>
  );
}
