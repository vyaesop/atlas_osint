"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { clearTokens, isAuthenticated } from "@/lib/auth";

const InsightsDashboard = dynamic(
  () => import("@/components/InsightsDashboard").then((m) => m.InsightsDashboard),
  { ssr: false },
);

export default function InsightsPage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) router.replace("/login");
    else setReady(true);
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

  return <InsightsDashboard onLogout={logout} />;
}
