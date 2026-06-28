"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { isAuthenticated } from "@/lib/auth";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    router.replace(isAuthenticated() ? "/explore" : "/login");
  }, [router]);
  return (
    <main className="flex h-screen items-center justify-center text-slate-400">
      Loading Atlas…
    </main>
  );
}
