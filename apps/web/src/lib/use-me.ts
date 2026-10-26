"use client";
import { useEffect, useState } from "react";
import { api, type User } from "./api";

// Tiny shared store so the header, pages and forms all see the same session.
let cache: Promise<User | null> | null = null;
const listeners = new Set<(u: User | null) => void>();

export function refreshMe() {
  cache = api<User>("/v1/auth/me").catch(() => null);
  cache.then((u) => listeners.forEach((l) => l(u)));
  return cache;
}

export function useMe() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const onChange = (u: User | null) => {
      setUser(u);
      setLoading(false);
    };
    listeners.add(onChange);
    (cache ?? refreshMe()).then(onChange);
    return () => {
      listeners.delete(onChange);
    };
  }, []);
  return { user, loading };
}
