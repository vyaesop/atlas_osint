"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { communityColor } from "@/lib/colors";
import type {
  CentralityMetric,
  CommunitiesResponse,
  GraphPath,
  PathKind,
  RankedNode,
} from "@/lib/types";
import { SearchBar } from "./SearchBar";

export type CentralityMap = Map<string, number>;
export type CommunityMap = Map<string, number>;

interface Props {
  selectedId: string | null;
  onCentrality: (map: CentralityMap | null) => void;
  onCommunities: (map: CommunityMap | null) => void;
  onPath: (path: GraphPath | null) => void;
  onClose: () => void;
}

const METRICS: { value: CentralityMetric; label: string }[] = [
  { value: "degree", label: "Degree" },
  { value: "betweenness", label: "Betweenness" },
  { value: "eigenvector", label: "Eigenvector" },
  { value: "pagerank", label: "PageRank" },
];

const PATH_KINDS: { value: PathKind; label: string }[] = [
  { value: "shortest", label: "Shortest" },
  { value: "strongest", label: "Strongest" },
  { value: "most_likely", label: "Most likely" },
];

export function AnalyticsPanel({ selectedId, onCentrality, onCommunities, onPath, onClose }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [metric, setMetric] = useState<CentralityMetric>("degree");
  const [topNodes, setTopNodes] = useState<RankedNode[] | null>(null);
  const [communities, setCommunities] = useState<CommunitiesResponse | null>(null);

  const [target, setTarget] = useState<{ id: string; name: string } | null>(null);
  const [pathKind, setPathKind] = useState<PathKind>("strongest");
  const [pathInfo, setPathInfo] = useState<GraphPath | "none" | null>(null);

  async function run<T>(fn: () => Promise<T>): Promise<T | undefined> {
    setBusy(true);
    setError(null);
    try {
      return await fn();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Request failed");
      return undefined;
    } finally {
      setBusy(false);
    }
  }

  async function runCentrality() {
    const res = await run(() =>
      api.centrality(metric, { egoEntityId: selectedId ?? undefined }),
    );
    if (!res) return;
    const max = res.results[0]?.score || 1;
    const map: CentralityMap = new Map(res.results.map((r) => [r.id, r.score / max]));
    setTopNodes(res.results.slice(0, 8));
    setCommunities(null);
    onCommunities(null);
    onCentrality(map);
  }

  async function runCommunities() {
    const res = await run(() => api.communities({ egoEntityId: selectedId ?? undefined }));
    if (!res) return;
    const map: CommunityMap = new Map();
    res.communities.forEach((c) => c.members.forEach((m) => map.set(m.id, c.id)));
    setCommunities(res);
    setTopNodes(null);
    onCentrality(null);
    onCommunities(map);
  }

  async function runPath() {
    if (!selectedId || !target) return;
    const res = await run(() => api.paths(selectedId, target.id, pathKind));
    if (!res) return;
    if (!res.found || res.paths.length === 0) {
      setPathInfo("none");
      onPath(null);
      return;
    }
    setPathInfo(res.paths[0]);
    onPath(res.paths[0]);
  }

  function clearAll() {
    setTopNodes(null);
    setCommunities(null);
    setPathInfo(null);
    onCentrality(null);
    onCommunities(null);
    onPath(null);
  }

  return (
    <div className="absolute left-4 top-20 z-10 w-80 rounded-xl bg-panel/95 p-4 shadow-2xl ring-1 ring-edge backdrop-blur">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-200">Analytics</h2>
        <button onClick={onClose} className="text-slate-500 hover:text-slate-300">✕</button>
      </div>

      {selectedId ? (
        <p className="mb-3 text-[11px] text-slate-500">
          Scoped to the selected node&apos;s neighborhood.
        </p>
      ) : (
        <p className="mb-3 text-[11px] text-amber-400">
          Select a node to scope analysis; otherwise the whole graph is used.
        </p>
      )}

      {/* Centrality */}
      <section className="mb-4">
        <div className="mb-1 text-xs font-medium text-slate-300">Centrality</div>
        <div className="flex gap-2">
          <select
            value={metric}
            onChange={(e) => setMetric(e.target.value as CentralityMetric)}
            className="flex-1 rounded-md bg-ink px-2 py-1.5 text-xs ring-1 ring-edge outline-none"
          >
            {METRICS.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
          <button
            onClick={runCentrality}
            disabled={busy}
            className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium hover:bg-blue-500 disabled:opacity-50"
          >
            Run
          </button>
        </div>
        {topNodes && (
          <ol className="mt-2 space-y-1 text-xs">
            {topNodes.map((n, i) => (
              <li key={n.id} className="flex justify-between text-slate-400">
                <span className="truncate">{i + 1}. {n.name}</span>
                <span className="font-mono text-slate-300">{n.score.toFixed(3)}</span>
              </li>
            ))}
          </ol>
        )}
      </section>

      {/* Communities */}
      <section className="mb-4">
        <div className="mb-1 text-xs font-medium text-slate-300">Communities</div>
        <button
          onClick={runCommunities}
          disabled={busy}
          className="w-full rounded-md bg-panel py-1.5 text-xs ring-1 ring-edge hover:bg-ink disabled:opacity-50"
        >
          Detect (Louvain)
        </button>
        {communities && (
          <div className="mt-2 text-xs text-slate-400">
            <p>
              {communities.community_count} communities · modularity{" "}
              <span className="font-mono text-slate-300">{communities.modularity.toFixed(3)}</span>
            </p>
            <div className="mt-1 flex flex-wrap gap-1">
              {communities.communities.slice(0, 10).map((c) => (
                <span
                  key={c.id}
                  className="rounded px-1.5 py-0.5 text-[10px]"
                  style={{ background: `${communityColor(c.id)}33`, color: communityColor(c.id) }}
                >
                  {c.size}
                </span>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* Path discovery */}
      <section>
        <div className="mb-1 text-xs font-medium text-slate-300">Path discovery</div>
        <div className="mb-2">
          <SearchBar onSelect={(id) => setTarget({ id, name: id })} />
        </div>
        {target && (
          <p className="mb-2 truncate text-[11px] text-slate-400">Target set ✓</p>
        )}
        <div className="flex gap-2">
          <select
            value={pathKind}
            onChange={(e) => setPathKind(e.target.value as PathKind)}
            className="flex-1 rounded-md bg-ink px-2 py-1.5 text-xs ring-1 ring-edge outline-none"
          >
            {PATH_KINDS.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
          <button
            onClick={runPath}
            disabled={busy || !selectedId || !target}
            className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium hover:bg-blue-500 disabled:opacity-50"
            title={!selectedId ? "Select a source node first" : !target ? "Choose a target" : ""}
          >
            Find
          </button>
        </div>
        {pathInfo === "none" && <p className="mt-2 text-xs text-amber-400">No path found.</p>}
        {pathInfo && pathInfo !== "none" && (
          <p className="mt-2 text-xs text-slate-400">
            {pathInfo.length} hops · score{" "}
            <span className="font-mono text-slate-300">{pathInfo.score.toFixed(3)}</span>
            {" · "}bottleneck {pathInfo.bottleneck_confidence.toFixed(2)}
          </p>
        )}
      </section>

      {error && <p className="mt-3 text-xs text-red-400">{error}</p>}

      <button
        onClick={clearAll}
        className="mt-4 w-full rounded-md bg-panel py-1.5 text-xs text-slate-300 ring-1 ring-edge hover:bg-ink"
      >
        Clear overlays
      </button>
    </div>
  );
}
