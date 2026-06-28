"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { clearTokens, isAuthenticated } from "@/lib/auth";

// React Flow touches the DOM/window, so load the explorer client-side only.
const GraphExplorer = dynamic(
  () => import("@/components/GraphExplorer").then((m) => m.GraphExplorer),
  { ssr: false },
);

export default function ExplorePage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login");
    } else {
      setReady(true);
    }
  }, [router]);

  function logout() {
    clearTokens();
    router.replace("/login");
  }

  if (!ready) {
    return (
      <main className="flex h-screen items-center justify-center text-slate-400">
        Checking session…
      </main>
    );
  }

  return (
    <>
      <div className="fixed bottom-4 right-4 z-[1000] flex gap-2">
        <Link
          href="/investigate"
          className="rounded-full bg-emerald-700 px-4 py-2 text-xs font-semibold text-white shadow-lg hover:bg-emerald-600"
        >
          🧭 Investigate
        </Link>
        <Link
          href="/insights"
          className="rounded-full bg-rose-700 px-4 py-2 text-xs font-semibold text-white shadow-lg hover:bg-rose-600"
        >
          📊 Insights
        </Link>
        <Link
          href="/timeline"
          className="rounded-full bg-sky-700 px-4 py-2 text-xs font-semibold text-white shadow-lg hover:bg-sky-600"
        >
          ⏱ Timelines
        </Link>
        <Link
          href="/map"
          className="rounded-full bg-teal-600 px-4 py-2 text-xs font-semibold text-white shadow-lg hover:bg-teal-500"
        >
          🗺 Map view
        </Link>
      </div>
      <GraphExplorer onLogout={logout} />
    </>
  );
}
