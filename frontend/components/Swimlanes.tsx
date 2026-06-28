"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import { api } from "@/lib/api";
import type { TimelineItem, TimelineResponse } from "@/lib/types";
import { SearchBar } from "./SearchBar";

const KIND_COLOR: Record<TimelineItem["kind"], string> = {
  attribute: "#a8a29e",
  relationship: "#4f8cff",
  event: "#f59e0b",
};

const LANE_PALETTE = ["#0f172a", "#111827"];

function toTime(date: string): number {
  return new Date(date).getTime();
}

/** N-entity swimlane timelines (#11): each entity is a horizontal lane plotted
 *  against a shared time axis, so activity can be compared across actors. */
export function Swimlanes({ onLogout }: { onLogout?: () => void }) {
  const [lanes, setLanes] = useState<TimelineResponse[]>([]);
  const [busy, setBusy] = useState(false);

  async function add(id: string) {
    if (lanes.some((l) => l.entity_id === id)) return;
    setBusy(true);
    try {
      const t = await api.timeline(id);
      setLanes((prev) => [...prev, t]);
    } catch {
      /* ignore */
    } finally {
      setBusy(false);
    }
  }

  function remove(id: string) {
    setLanes((prev) => prev.filter((l) => l.entity_id !== id));
  }

  const { min, span, ticks } = useMemo(() => {
    const times = lanes
      .flatMap((l) => l.items.map((i) => toTime(i.date)))
      .filter((n) => !Number.isNaN(n));
    if (times.length === 0) return { min: 0, span: 1, ticks: [] as { label: string; pct: number }[] };
    const lo = Math.min(...times);
    const hi = Math.max(...times);
    const s = hi - lo || 1;
    // Year ticks across the span (cap at ~8 labels).
    const y0 = new Date(lo).getUTCFullYear();
    const y1 = new Date(hi).getUTCFullYear();
    const step = Math.max(1, Math.ceil((y1 - y0 + 1) / 8));
    const tk: { label: string; pct: number }[] = [];
    for (let y = y0; y <= y1; y += step) {
      const t = Date.UTC(y, 0, 1);
      tk.push({ label: String(y), pct: ((t - lo) / s) * 100 });
    }
    return { min: lo, span: s, ticks: tk };
  }, [lanes]);

  function pct(date: string): number {
    return ((toTime(date) - min) / span) * 100;
  }

  return (
    <main className="flex h-screen flex-col bg-slate-900 text-slate-100">
      <header className="flex items-center justify-between border-b border-slate-800 px-4 py-2">
        <div className="flex items-center gap-4">
          <h1 className="text-sm font-semibold">Atlas · Activity Timelines</h1>
          <Link href="/explore" className="text-xs text-sky-400 hover:underline">
            ← Graph explorer
          </Link>
        </div>
        <div className="flex items-center gap-3">
          <SearchBar onSelect={(id) => void add(id)} />
          {onLogout && (
            <button onClick={onLogout} className="text-xs text-slate-400 hover:text-slate-200">
              Log out
            </button>
          )}
        </div>
      </header>

      <div className="flex-1 overflow-auto p-4">
        {lanes.length === 0 ? (
          <p className="text-sm text-slate-500">
            Search above to add entities. Each becomes a lane on a shared time axis
            {busy ? " · loading…" : ""}.
          </p>
        ) : (
          <div className="min-w-[640px]">
            {/* Axis */}
            <div className="relative mb-2 ml-44 h-5 border-b border-slate-700">
              {ticks.map((t, i) => (
                <span
                  key={i}
                  className="absolute -translate-x-1/2 text-[10px] font-mono text-slate-500"
                  style={{ left: `${t.pct}%` }}
                >
                  {t.label}
                </span>
              ))}
            </div>

            {/* Lanes */}
            {lanes.map((lane, li) => (
              <div key={lane.entity_id} className="mb-1 flex items-stretch">
                <div className="flex w-44 shrink-0 items-center justify-between pr-2">
                  <span className="truncate text-xs text-slate-200" title={lane.entity_name}>
                    {lane.entity_name}
                  </span>
                  <button
                    onClick={() => remove(lane.entity_id)}
                    className="text-slate-500 hover:text-slate-300"
                    title="Remove lane"
                  >
                    ✕
                  </button>
                </div>
                <div
                  className="relative h-9 flex-1 rounded"
                  style={{ background: LANE_PALETTE[li % LANE_PALETTE.length] }}
                >
                  {lane.items.length === 0 && (
                    <span className="absolute left-2 top-1/2 -translate-y-1/2 text-[10px] text-slate-600">
                      no dated activity
                    </span>
                  )}
                  {lane.items.map((item, i) => (
                    <span
                      key={i}
                      className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border border-slate-900"
                      style={{ left: `${pct(item.date)}%`, background: KIND_COLOR[item.kind] }}
                      title={`${item.date}${item.end_date ? ` → ${item.end_date}` : ""}: ${item.label}`}
                    />
                  ))}
                </div>
              </div>
            ))}

            {/* Legend */}
            <div className="ml-44 mt-3 flex gap-4 text-[10px] text-slate-400">
              {(["attribute", "relationship", "event"] as TimelineItem["kind"][]).map((k) => (
                <span key={k} className="flex items-center gap-1">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: KIND_COLOR[k] }} />
                  {k}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
