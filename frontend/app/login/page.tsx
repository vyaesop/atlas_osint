"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("admin@atlas.example.com");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.login(email, password);
      router.replace("/explore");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex h-screen items-center justify-center">
      <form
        onSubmit={onSubmit}
        className="w-80 rounded-xl bg-panel p-6 shadow-2xl ring-1 ring-edge"
      >
        <h1 className="mb-1 text-xl font-semibold">Project Atlas</h1>
        <p className="mb-6 text-sm text-slate-400">Sign in to explore the graph.</p>

        <label htmlFor="email" className="mb-1 block text-xs text-slate-400">Email</label>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="username"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mb-4 w-full rounded-md bg-ink px-3 py-2 text-sm ring-1 ring-edge outline-none focus:ring-blue-500"
          required
        />

        <label htmlFor="password" className="mb-1 block text-xs text-slate-400">Password</label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mb-4 w-full rounded-md bg-ink px-3 py-2 text-sm ring-1 ring-edge outline-none focus:ring-blue-500"
          required
        />

        {error && <p className="mb-3 text-sm text-red-400">{error}</p>}

        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-md bg-blue-600 py-2 text-sm font-medium hover:bg-blue-500 disabled:opacity-50"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </main>
  );
}
