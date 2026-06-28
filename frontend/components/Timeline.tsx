"use client";

import type { TimelineItem } from "@/lib/types";

const KIND_COLOR: Record<TimelineItem["kind"], string> = {
  attribute: "#a8a29e",
  relationship: "#4f8cff",
  event: "#f59e0b",
};

export function Timeline({ items }: { items: TimelineItem[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-slate-500">No dated events recorded.</p>;
  }
  return (
    <ol className="relative ml-2 border-l border-edge">
      {items.map((item, i) => (
        <li key={i} className="mb-4 ml-4">
          <span
            className="absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full"
            style={{ background: KIND_COLOR[item.kind] }}
          />
          <time className="text-xs font-mono text-slate-400">
            {item.date}
            {item.end_date ? ` → ${item.end_date}` : ""}
          </time>
          <p className="text-sm text-slate-200">{item.label}</p>
          {item.confidence > 0 && (
            <span className="text-[10px] text-slate-500">
              confidence {(item.confidence * 100).toFixed(0)}%
            </span>
          )}
        </li>
      ))}
    </ol>
  );
}
