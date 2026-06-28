"use client";

import type { LayoutKind } from "@/lib/layout";
import { ENTITY_COLORS, ENTITY_LABELS } from "@/lib/colors";
import type { EntityType } from "@/lib/types";

interface Props {
  layout: LayoutKind;
  onLayoutChange: (l: LayoutKind) => void;
  onReset: () => void;
  onLogout: () => void;
  analyticsOpen: boolean;
  onToggleAnalytics: () => void;
  ingestOpen: boolean;
  onToggleIngest: () => void;
}

const LAYOUTS: { kind: LayoutKind; label: string }[] = [
  { kind: "force", label: "Force" },
  { kind: "hierarchical", label: "Hierarchical" },
  { kind: "timeline", label: "Timeline" },
];

export function Toolbar({
  layout, onLayoutChange, onReset, onLogout, analyticsOpen, onToggleAnalytics,
  ingestOpen, onToggleIngest,
}: Props) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex overflow-hidden rounded-md ring-1 ring-edge">
        {LAYOUTS.map((l) => (
          <button
            key={l.kind}
            onClick={() => onLayoutChange(l.kind)}
            className={`px-3 py-2 text-xs font-medium ${
              layout === l.kind ? "bg-blue-600 text-white" : "bg-panel text-slate-300 hover:bg-ink"
            }`}
          >
            {l.label}
          </button>
        ))}
      </div>
      <button
        onClick={onToggleAnalytics}
        className={`rounded-md px-3 py-2 text-xs font-medium ring-1 ring-edge ${
          analyticsOpen ? "bg-blue-600 text-white" : "bg-panel text-slate-300 hover:bg-ink"
        }`}
      >
        Analyze
      </button>
      <button
        onClick={onToggleIngest}
        className={`rounded-md px-3 py-2 text-xs font-medium ring-1 ring-edge ${
          ingestOpen ? "bg-blue-600 text-white" : "bg-panel text-slate-300 hover:bg-ink"
        }`}
      >
        Ingest
      </button>
      <button
        onClick={onReset}
        className="rounded-md bg-panel px-3 py-2 text-xs text-slate-300 ring-1 ring-edge hover:bg-ink"
      >
        Clear
      </button>
      <button
        onClick={onLogout}
        className="rounded-md bg-panel px-3 py-2 text-xs text-slate-300 ring-1 ring-edge hover:bg-ink"
      >
        Sign out
      </button>
    </div>
  );
}

export function Legend() {
  return (
    <div className="rounded-lg bg-panel/90 p-3 text-xs ring-1 ring-edge backdrop-blur">
      <div className="mb-2 font-semibold text-slate-300">Entity types</div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1">
        {(Object.keys(ENTITY_COLORS) as EntityType[]).map((t) => (
          <div key={t} className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: ENTITY_COLORS[t] }} />
            <span className="text-slate-400">{ENTITY_LABELS[t]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
