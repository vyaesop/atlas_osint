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
      <Link
        href="/map"
        className="fixed bottom-4 right-4 z-[1000] rounded-full bg-teal-600 px-4 py-2 text-xs font-semibold text-white shadow-lg hover:bg-teal-500"
      >
        🗺 Map view
      </Link>
      <GraphExplorer onLogout={logout} />
    </>
  );
}
