"use client";

// Linked tabular view of whatever is on the graph canvas (Task 9).
//
// Brushing here drives the graph (and any other linked view) and vice-versa:
// clicking a row focuses that entity; the checkbox toggles it into the brushed
// set; rows highlight when their entity is active anywhere. This is the
// concrete graph ⇄ table linked-brushing pair, sharing the root SelectionStore.

import { useMemo } from "react";
import { useSelection } from "@/lib/selection";
import { ENTITY_LABELS, entityColor } from "@/lib/colors";
import type { Entity } from "@/lib/types";

export function EntityTable({
  entities,
  onClose,
}: {
  entities: Entity[];
  onClose: () => void;
}) {
  const { selected, brushed, select, toggleBrush, setHovered, clearBrush, isActive } =
    useSelection();

  const rows = useMemo(
    () => [...entities].sort((a, b) => b.confidence_score - a.confidence_score),
    [entities],
  );

  return (
    <aside className="absolute right-4 top-16 z-20 flex max-h-[70vh] w-[26rem] flex-col rounded-lg border border-slate-700 bg-panel/95 shadow-xl">
      <div className="flex items-center justify-between border-b border-slate-700 px-3 py-2">
        <span className="text-xs font-semibold text-slate-200">
          Table · {rows.length} on canvas
          {brushed.size > 0 && <span className="ml-2 text-sky-400">{brushed.size} brushed</span>}
        </span>
        <div className="flex items-center gap-2">
          {brushed.size > 0 && (
            <button onClick={clearBrush} className="text-[11px] text-slate-400 hover:text-slate-200">
              clear
            </button>
          )}
          <button onClick={onClose} className="text-slate-400 hover:text-slate-200" aria-label="Close table">
            ✕
          </button>
        </div>
      </div>

      <div className="overflow-auto">
        <table className="w-full text-left text-xs">
          <thead className="sticky top-0 bg-panel text-slate-400">
            <tr>
              <th className="w-6 px-2 py-1" />
              <th className="px-2 py-1">Name</th>
              <th className="px-2 py-1">Type</th>
              <th className="px-2 py-1 text-right">Conf.</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => (
              <tr
                key={e.id}
                onClick={() => select(e.id)}
                onMouseEnter={() => setHovered(e.id)}
                onMouseLeave={() => setHovered(null)}
                className={`cursor-pointer border-t border-slate-800 ${
                  e.id === selected
                    ? "bg-sky-900/40"
                    : isActive(e.id)
                      ? "bg-slate-700/40"
                      : "hover:bg-slate-800/50"
                }`}
              >
                <td className="px-2 py-1" onClick={(ev) => ev.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={brushed.has(e.id)}
                    onChange={() => toggleBrush(e.id)}
                    aria-label={`Brush ${e.name}`}
                  />
                </td>
                <td className="px-2 py-1">
                  <span className="truncate text-slate-100" title={e.name}>{e.name}</span>
                </td>
                <td className="px-2 py-1">
                  <span style={{ color: entityColor(e.type) }}>{ENTITY_LABELS[e.type]}</span>
                </td>
                <td className="px-2 py-1 text-right font-mono text-slate-300">
                  {(e.confidence_score * 100).toFixed(0)}%
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={4} className="px-3 py-6 text-center text-slate-500">
                  No entities on the canvas yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </aside>
  );
}
