"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { api } from "@/lib/api";
import { classificationColor, entityColor, RISK_COLORS } from "@/lib/colors";
import type { EntityType, Facets, NetworkDiff, RiskScore } from "@/lib/types";

function FacetBars({
  title,
  buckets,
  colorFor,
}: {
  title: string;
  buckets: { value: string; count: number }[];
  colorFor?: (value: string) => string;
}) {
  const max = Math.max(1, ...buckets.map((b) => b.count));
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/60 p-3">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</h3>
      {buckets.length === 0 ? (
        <p className="text-xs text-slate-600">no data</p>
      ) : (
        <ul className="space-y-1">
          {buckets.map((b) => (
            <li key={b.value} className="flex items-center gap-2 text-xs">
              <span className="w-28 shrink-0 truncate text-slate-300" title={b.value}>
                {b.value}
              </span>
              <span className="relative h-3 flex-1 overflow-hidden rounded bg-slate-900">
                <span
                  className="absolute inset-y-0 left-0 rounded"
                  style={{
                    width: `${(b.count / max) * 100}%`,
                    background: colorFor ? colorFor(b.value) : "#4f8cff",
                  }}
                />
              </span>
              <span className="w-8 text-right font-mono text-slate-400">{b.count}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function InsightsDashboard({ onLogout }: { onLogout?: () => void }) {
  const [facets, setFacets] = useState<Facets | null>(null);
  const [risk, setRisk] = useState<RiskScore[]>([]);
  const [diff, setDiff] = useState<NetworkDiff | null>(null);
  const [since, setSince] = useState(() => {
    const d = new Date(Date.now() - 7 * 86400_000);
    return d.toISOString().slice(0, 10);
  });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [f, r] = await Promise.all([api.facets(), api.topRisk(10)]);
        setFacets(f);
        setRisk(r.results);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load insights");
      }
    })();
  }, []);

  async function runDiff() {
    try {
      setDiff(await api.diff(new Date(`${since}T00:00:00Z`).toISOString()));
    } catch {
      setDiff(null);
    }
  }

  const changeCounts = useMemo(() => {
    if (!diff) return null;
    return {
      added: diff.added_entities.length + diff.added_relationships.length,
      modified: diff.modified_entities.length + diff.modified_relationships.length,
      removed: diff.removed.length,
    };
  }, [diff]);

  return (
    <main className="min-h-screen bg-slate-900 text-slate-100">
      <header className="flex items-center justify-between border-b border-slate-800 px-4 py-2">
        <div className="flex items-center gap-4">
          <h1 className="text-sm font-semibold">Atlas · Insights</h1>
          <Link href="/explore" className="text-xs text-sky-400 hover:underline">← Graph explorer</Link>
        </div>
        {onLogout && (
          <button onClick={onLogout} className="text-xs text-slate-400 hover:text-slate-200">Log out</button>
        )}
      </header>

      {error && <div className="m-4 rounded bg-red-900/70 px-3 py-2 text-xs">{error}</div>}

      <div className="grid grid-cols-1 gap-4 p-4 lg:grid-cols-3">
        {/* #49 risk leaderboard */}
        <section className="rounded-lg border border-slate-700 bg-slate-800/60 p-3">
          <h2 className="mb-2 text-sm font-semibold text-rose-300">Top risk (#49)</h2>
          {risk.length === 0 ? (
            <p className="text-xs text-slate-600">No entities scored yet.</p>
          ) : (
            <ul className="space-y-2">
              {risk.map((r) => (
                <li key={r.entity_id} className="text-xs">
                  <div className="flex items-center justify-between">
                    <Link href={`/dashboard/${r.entity_id}`} className="truncate text-slate-200 hover:underline">
                      {r.name}
                    </Link>
                    <span
                      className="ml-2 shrink-0 rounded px-1.5 py-0.5 font-mono"
                      style={{ background: `${RISK_COLORS[r.band]}33`, color: RISK_COLORS[r.band] }}
                    >
                      {r.score.toFixed(2)} {r.band}
                    </span>
                  </div>
                  {r.reasons[0] && <div className="text-slate-500">{r.reasons[0]}</div>}
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* #46 facet brush filters */}
        {facets && (
          <>
            <FacetBars title={`By type · ${facets.total} total`} buckets={facets.by_type}
              colorFor={(v) => entityColor(v as EntityType)} />
            <FacetBars title="By classification" buckets={facets.by_classification}
              colorFor={classificationColor} />
            <FacetBars title="By confidence" buckets={facets.by_confidence} />
            <FacetBars title="By provenance" buckets={facets.by_provenance} />
            <FacetBars title="By month" buckets={facets.by_month} />
          </>
        )}

        {/* #47 network diff */}
        <section className="rounded-lg border border-slate-700 bg-slate-800/60 p-3 lg:col-span-3">
          <div className="mb-2 flex items-center gap-3">
            <h2 className="text-sm font-semibold text-emerald-300">What changed (#47)</h2>
            <input
              type="date"
              value={since}
              onChange={(e) => setSince(e.target.value)}
              className="rounded bg-slate-900 px-2 py-1 text-xs text-slate-200"
            />
            <button onClick={runDiff} className="rounded bg-emerald-700 px-3 py-1 text-xs hover:bg-emerald-600">
              Compare
            </button>
            {changeCounts && (
              <span className="text-xs text-slate-400">
                +{changeCounts.added} added · {changeCounts.modified} modified · −{changeCounts.removed} removed
              </span>
            )}
          </div>
          {diff && (
            <div className="grid grid-cols-1 gap-3 text-xs md:grid-cols-3">
              <DiffList title="Added" items={[...diff.added_entities, ...diff.added_relationships]} color="#22c55e" />
              <DiffList title="Modified" items={[...diff.modified_entities, ...diff.modified_relationships]} color="#f59e0b" />
              <DiffList title="Removed" items={diff.removed} color="#ef4444" />
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

function DiffList({ title, items, color }: { title: string; items: { id: string; kind: string; label: string }[]; color: string }) {
  return (
    <div>
      <div className="mb-1 font-semibold" style={{ color }}>{title} ({items.length})</div>
      <ul className="max-h-48 space-y-0.5 overflow-auto">
        {items.slice(0, 50).map((i, idx) => (
          <li key={`${i.id}-${idx}`} className="truncate text-slate-300">
            <span className="text-slate-500">[{i.kind}]</span> {i.label}
          </li>
        ))}
        {items.length === 0 && <li className="text-slate-600">none</li>}
      </ul>
    </div>
  );
}
