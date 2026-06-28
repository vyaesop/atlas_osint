"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { entityColor, ENTITY_LABELS } from "@/lib/colors";
import type { ConfidenceSummary, Entity } from "@/lib/types";

interface Props {
  entityId: string;
  expanded: boolean;
  onExpand: () => void;
  onCollapse: () => void;
  onClose: () => void;
}

export function DetailPanel({ entityId, expanded, onExpand, onCollapse, onClose }: Props) {
  const [entity, setEntity] = useState<Entity | null>(null);
  const [confidence, setConfidence] = useState<ConfidenceSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<string | null>(null);
  const [summarizing, setSummarizing] = useState(false);

  async function summarize() {
    setSummarizing(true);
    try {
      const res = await api.summarizeEntity(entityId);
      setSummary(res.summary);
    } catch {
      setSummary("Failed to generate summary.");
    } finally {
      setSummarizing(false);
    }
  }

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([api.getEntity(entityId), api.entityConfidence(entityId)])
      .then(([e, c]) => {
        if (!active) return;
        setEntity(e);
        setConfidence(c);
      })
      .catch(() => active && setEntity(null))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [entityId]);

  if (loading) {
    return <Panel><p className="text-sm text-slate-400">Loading…</p></Panel>;
  }
  if (!entity) {
    return <Panel><p className="text-sm text-red-400">Entity not found.</p></Panel>;
  }

  const color = entityColor(entity.type);

  return (
    <Panel>
      <div className="mb-3 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-1.5">
            <span
              className="rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase"
              style={{ background: `${color}22`, color }}
            >
              {ENTITY_LABELS[entity.type]}
            </span>
            {entity.is_ai_generated && (
              <span
                className="rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-semibold text-amber-300"
                title="AI-extracted — pending verification"
              >
                AI · unverified
              </span>
            )}
          </div>
          <h2 className="mt-1 text-lg font-semibold">{entity.name}</h2>
        </div>
        <button onClick={onClose} className="text-slate-500 hover:text-slate-300">✕</button>
      </div>

      {entity.aliases.length > 0 && (
        <p className="mb-2 text-xs text-slate-400">
          Also known as: {entity.aliases.join(", ")}
        </p>
      )}
      {entity.description && (
        <p className="mb-3 text-sm text-slate-300">{entity.description}</p>
      )}

      {confidence && (
        <div className="mb-3 rounded-md bg-ink p-3">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Confidence</span>
            <span className="font-mono text-slate-200">
              {(confidence.score * 100).toFixed(0)}%
            </span>
          </div>
          <div className="mt-1 h-1.5 w-full overflow-hidden rounded bg-panel">
            <div className="h-full" style={{ width: `${confidence.score * 100}%`, background: color }} />
          </div>
          <div className="mt-2 flex gap-3 text-[11px] text-slate-400">
            <span>✓ {confidence.supporting_count} supporting</span>
            <span>✗ {confidence.contradicting_count} contradicting</span>
          </div>
          {confidence.is_contradicted && (
            <p className="mt-1 text-[11px] text-amber-400">⚠ Contradictory evidence present</p>
          )}
        </div>
      )}

      {Object.keys(entity.properties).length > 0 && (
        <dl className="mb-3 space-y-1 text-xs">
          {Object.entries(entity.properties).map(([k, v]) => (
            <div key={k} className="flex justify-between gap-2">
              <dt className="text-slate-500">{k}</dt>
              <dd className="truncate text-slate-300">{String(v)}</dd>
            </div>
          ))}
        </dl>
      )}

      {expanded ? (
        <button
          onClick={onCollapse}
          className="w-full rounded-md bg-panel py-2 text-sm ring-1 ring-edge hover:bg-ink"
        >
          Collapse neighbors
        </button>
      ) : (
        <button
          onClick={onExpand}
          className="w-full rounded-md bg-blue-600 py-2 text-sm font-medium hover:bg-blue-500"
        >
          Expand neighbors
        </button>
      )}

      <Link
        href={`/dashboard/${entity.id}`}
        className="mt-2 block w-full rounded-md bg-panel py-2 text-center text-sm ring-1 ring-edge hover:bg-ink"
      >
        Open dashboard →
      </Link>

      <button
        onClick={summarize}
        disabled={summarizing}
        className="mt-2 w-full rounded-md bg-panel py-2 text-sm ring-1 ring-edge hover:bg-ink disabled:opacity-50"
      >
        {summarizing ? "Summarizing…" : "Summarize (AI)"}
      </button>
      {summary && (
        <div className="mt-2 rounded-md bg-ink p-3 text-xs text-slate-300">
          <span className="mb-1 block text-[10px] font-semibold uppercase text-amber-300">
            AI-generated · unverified
          </span>
          {summary}
        </div>
      )}
    </Panel>
  );
}

function Panel({ children }: { children: React.ReactNode }) {
  return (
    <div className="absolute right-4 top-20 z-10 w-80 rounded-xl bg-panel/95 p-4 shadow-2xl ring-1 ring-edge backdrop-blur">
      {children}
    </div>
  );
}
