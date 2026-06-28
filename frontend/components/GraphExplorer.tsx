"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Edge,
  type Node,
  type NodeMouseHandler,
} from "reactflow";
import "reactflow/dist/style.css";

import { api } from "@/lib/api";
import { communityColor, entityColor, PATH_HIGHLIGHT } from "@/lib/colors";
import { computeLayout, type LayoutKind, type Positions } from "@/lib/layout";
import type { Entity, GraphPath, GraphResponse, Relationship } from "@/lib/types";
import { EntityNode, type EntityNodeData } from "./EntityNode";
import { DetailPanel } from "./DetailPanel";
import { AnalyticsPanel, type CentralityMap, type CommunityMap } from "./AnalyticsPanel";
import { IngestPanel } from "./IngestPanel";
import { Legend, Toolbar } from "./Toolbar";
import { SearchBar } from "./SearchBar";

const nodeTypes = { entity: EntityNode };

function prettyRel(type: string): string {
  return type.replace(/_/g, " ").toLowerCase();
}

function Explorer({ onLogout }: { onLogout: () => void }) {
  const [entities, setEntities] = useState<Record<string, Entity>>({});
  const [rels, setRels] = useState<Record<string, Relationship>>({});
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<string | null>(null);
  const [layout, setLayout] = useState<LayoutKind>("force");
  const [positions, setPositions] = useState<Positions>({});

  // Panels.
  const [showAnalytics, setShowAnalytics] = useState(false);
  const [showIngest, setShowIngest] = useState(false);
  const [centralityMap, setCentralityMap] = useState<CentralityMap | null>(null);
  const [communityMap, setCommunityMap] = useState<CommunityMap | null>(null);
  const [pathNodeIds, setPathNodeIds] = useState<Set<string>>(new Set());
  const [pathEdgeIds, setPathEdgeIds] = useState<Set<string>>(new Set());

  // Temporal replay (#10).
  const [replayOn, setReplayOn] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [cutoff, setCutoff] = useState(0); // epoch ms

  const [rfNodes, setRfNodes, onNodesChange] = useNodesState<EntityNodeData>([]);
  const [rfEdges, setRfEdges, onEdgesChange] = useEdgesState([]);
  const { fitView } = useReactFlow();

  const mergeGraph = useCallback((g: Partial<GraphResponse>) => {
    if (g.nodes?.length) {
      setEntities((prev) => {
        const next = { ...prev };
        g.nodes!.forEach((n) => (next[n.id] = n));
        return next;
      });
    }
    if (g.edges?.length) {
      setRels((prev) => {
        const next = { ...prev };
        g.edges!.forEach((e) => (next[e.id] = e));
        return next;
      });
    }
  }, []);

  const focus = useCallback(
    async (id: string) => {
      const entity = await api.getEntity(id);
      mergeGraph({ nodes: [entity] });
      setSelected(id);
    },
    [mergeGraph],
  );

  const expand = useCallback(
    async (id: string) => {
      const graph = await api.neighbors(id);
      mergeGraph(graph);
      setExpanded((prev) => new Set(prev).add(id));
    },
    [mergeGraph],
  );

  const collapse = useCallback(
    (id: string) => {
      const incident = Object.values(rels).filter(
        (r) => r.source_id === id || r.target_id === id,
      );
      const neighborIds = new Set(
        incident.flatMap((r) => [r.source_id, r.target_id]).filter((x) => x !== id),
      );
      const remaining = Object.values(rels).filter(
        (r) => r.source_id !== id && r.target_id !== id,
      );

      setExpanded((prev) => {
        const n = new Set(prev);
        n.delete(id);
        return n;
      });
      setRels(() => Object.fromEntries(remaining.map((r) => [r.id, r])));
      setEntities((prev) => {
        const next = { ...prev };
        neighborIds.forEach((nid) => {
          const stillConnected = remaining.some(
            (r) => r.source_id === nid || r.target_id === nid,
          );
          if (!stillConnected && !expanded.has(nid) && nid !== selected) {
            delete next[nid];
          }
        });
        return next;
      });
    },
    [rels, expanded, selected],
  );

  const reset = useCallback(() => {
    setEntities({});
    setRels({});
    setExpanded(new Set());
    setSelected(null);
    setCentralityMap(null);
    setCommunityMap(null);
    setPathNodeIds(new Set());
    setPathEdgeIds(new Set());
  }, []);

  // Load any path nodes/edges not already on the canvas, then highlight them.
  const applyPath = useCallback(async (path: GraphPath | null) => {
    if (!path) {
      setPathNodeIds(new Set());
      setPathEdgeIds(new Set());
      return;
    }
    const missingNodes = path.nodes.filter((n) => !(n.id in entities));
    const fetchedNodes = await Promise.all(
      missingNodes.map((n) => api.getEntity(n.id).catch(() => null)),
    );
    const relIds = path.edges.map((e) => e.rel_id).filter((id): id is string => !!id);
    const missingRels = relIds.filter((id) => !(id in rels));
    const fetchedRels = await Promise.all(
      missingRels.map((id) => api.getRelationship(id).catch(() => null)),
    );
    mergeGraph({
      nodes: fetchedNodes.filter((n): n is Entity => n !== null),
      edges: fetchedRels.filter((r): r is Relationship => r !== null),
    });
    setPathNodeIds(new Set(path.nodes.map((n) => n.id)));
    setPathEdgeIds(new Set(relIds));
  }, [entities, rels, mergeGraph]);

  // Recompute positions only when topology or layout changes.
  useEffect(() => {
    setPositions(computeLayout(layout, Object.values(entities), Object.values(rels)));
  }, [entities, rels, layout]);

  // --- Temporal replay (#10) ---
  const dateBounds = useMemo(() => {
    const times: number[] = [];
    for (const r of Object.values(rels)) {
      for (const d of [r.start_date, r.end_date]) {
        if (d) {
          const t = new Date(d).getTime();
          if (!Number.isNaN(t)) times.push(t);
        }
      }
    }
    if (times.length === 0) return null;
    return { min: Math.min(...times), max: Math.max(...times) };
  }, [rels]);

  // Which nodes/edges are visible at the current cutoff (null ⇒ show all).
  const replayVisible = useMemo(() => {
    if (!replayOn) return null;
    const edgeIds = new Set<string>();
    const endedIds = new Set<string>();
    const nodeIds = new Set<string>();
    const allRels = Object.values(rels);
    const connected = new Set<string>();
    for (const r of allRels) {
      connected.add(r.source_id);
      connected.add(r.target_id);
      const start = r.start_date ? new Date(r.start_date).getTime() : null;
      // Undated edges are an always-present baseline; dated edges appear at start.
      if (start !== null && start > cutoff) continue;
      edgeIds.add(r.id);
      const end = r.end_date ? new Date(r.end_date).getTime() : null;
      if (end !== null && end < cutoff) endedIds.add(r.id);
      nodeIds.add(r.source_id);
      nodeIds.add(r.target_id);
    }
    if (selected) nodeIds.add(selected);
    // Standalone nodes (never connected) remain visible.
    for (const id of Object.keys(entities)) {
      if (!connected.has(id)) nodeIds.add(id);
    }
    return { edgeIds, endedIds, nodeIds };
  }, [replayOn, cutoff, rels, entities, selected]);

  // Advance the cutoff while playing.
  useEffect(() => {
    if (!playing || !replayOn || !dateBounds) return;
    const span = dateBounds.max - dateBounds.min || 1;
    const id = setInterval(() => {
      setCutoff((c) => {
        const next = c + span / 60;
        if (next >= dateBounds.max) {
          setPlaying(false);
          return dateBounds.max;
        }
        return next;
      });
    }, 200);
    return () => clearInterval(id);
  }, [playing, replayOn, dateBounds]);

  const toggleReplay = useCallback(() => {
    setReplayOn((v) => {
      const next = !v;
      if (next && dateBounds) setCutoff(dateBounds.max);
      if (!next) setPlaying(false);
      return next;
    });
  }, [dateBounds]);

  const playPause = useCallback(() => {
    if (!dateBounds) return;
    setPlaying((p) => {
      if (!p && cutoff >= dateBounds.max) setCutoff(dateBounds.min);
      return !p;
    });
  }, [dateBounds, cutoff]);

  // Build React Flow nodes from domain state + positions + selection + overlays.
  useEffect(() => {
    const visibleEntities = replayVisible
      ? Object.values(entities).filter((e) => replayVisible.nodeIds.has(e.id))
      : Object.values(entities);
    const nodes: Node<EntityNodeData>[] = visibleEntities.map((e) => ({
      id: e.id,
      type: "entity",
      position: positions[e.id] ?? { x: 0, y: 0 },
      selected: e.id === selected,
      data: {
        label: e.name,
        type: e.type,
        confidence: e.confidence_score,
        expanded: expanded.has(e.id),
        metricScore: centralityMap?.get(e.id),
        communityColor:
          communityMap?.has(e.id) ? communityColor(communityMap.get(e.id)!) : undefined,
        onPath: pathNodeIds.has(e.id),
        aiGenerated: e.is_ai_generated,
      },
    }));
    setRfNodes(nodes);
  }, [entities, positions, expanded, selected, centralityMap, communityMap, pathNodeIds, replayVisible, setRfNodes]);

  useEffect(() => {
    const visibleRels = replayVisible
      ? Object.values(rels).filter((r) => replayVisible.edgeIds.has(r.id))
      : Object.values(rels);
    const edges: Edge[] = visibleRels.map((r) => {
      const onPath = pathEdgeIds.has(r.id);
      const ended = replayVisible?.endedIds.has(r.id) ?? false;
      return {
        id: r.id,
        source: r.source_id,
        target: r.target_id,
        label: prettyRel(r.type),
        animated: onPath,
        markerEnd: { type: MarkerType.ArrowClosed, color: onPath ? PATH_HIGHLIGHT : "#64748b" },
        style: {
          stroke: onPath ? PATH_HIGHLIGHT : "#475569",
          strokeWidth: onPath ? 3 : 1.5,
          // Relationships that have ended by the cutoff fade out and dash.
          opacity: ended ? 0.35 : 1,
          strokeDasharray: ended ? "4 4" : undefined,
        },
        labelStyle: { fill: onPath ? PATH_HIGHLIGHT : "#94a3b8", fontSize: 10 },
        labelBgStyle: { fill: "#0b1020", fillOpacity: 0.85 },
      };
    });
    setRfEdges(edges);
  }, [rels, pathEdgeIds, replayVisible, setRfEdges]);

  // Fit the view whenever the node count changes (focus / expand / collapse).
  const nodeCount = Object.keys(entities).length;
  useEffect(() => {
    if (nodeCount > 0) {
      const t = setTimeout(() => fitView({ duration: 400, padding: 0.2 }), 60);
      return () => clearTimeout(t);
    }
  }, [nodeCount, layout, fitView]);

  const onNodeClick = useCallback<NodeMouseHandler>((_, node) => setSelected(node.id), []);
  const onNodeDoubleClick = useCallback<NodeMouseHandler>(
    (_, node) => {
      if (expanded.has(node.id)) collapse(node.id);
      else void expand(node.id);
    },
    [expanded, expand, collapse],
  );

  const isExpanded = selected ? expanded.has(selected) : false;
  const empty = nodeCount === 0;

  const minimapColor = useMemo(
    () => (node: Node) => entityColor((node.data as EntityNodeData).type),
    [],
  );

  return (
    <div className="relative h-screen w-screen">
      <header className="absolute left-0 right-0 top-0 z-10 flex items-center justify-between gap-4 px-4 py-3">
        <div className="flex items-center gap-4">
          <span className="text-sm font-semibold text-slate-200">Atlas</span>
          <SearchBar onSelect={(id) => void focus(id)} />
          <button
            onClick={toggleReplay}
            disabled={!dateBounds}
            title={dateBounds ? "Replay the network over time" : "No dated relationships to replay"}
            className={`rounded px-2 py-1 text-xs ${
              replayOn ? "bg-amber-600 text-white" : "bg-panel text-slate-300"
            } disabled:opacity-40`}
          >
            ⏱ Replay
          </button>
        </div>
        <Toolbar
          layout={layout}
          onLayoutChange={setLayout}
          onReset={reset}
          onLogout={onLogout}
          analyticsOpen={showAnalytics}
          onToggleAnalytics={() => {
            setShowAnalytics((v) => !v);
            setShowIngest(false);
          }}
          ingestOpen={showIngest}
          onToggleIngest={() => {
            setShowIngest((v) => !v);
            setShowAnalytics(false);
          }}
        />
      </header>

      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onNodeDoubleClick={onNodeDoubleClick}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.1}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#1e293b" gap={24} />
        <Controls className="!bg-panel !text-slate-200" />
        <MiniMap pannable zoomable nodeColor={minimapColor} maskColor="rgba(11,16,32,0.7)" />
      </ReactFlow>

      {showAnalytics && (
        <AnalyticsPanel
          selectedId={selected}
          onCentrality={setCentralityMap}
          onCommunities={setCommunityMap}
          onPath={(p) => void applyPath(p)}
          onClose={() => setShowAnalytics(false)}
        />
      )}

      {showIngest && (
        <IngestPanel
          onIngested={(result) =>
            mergeGraph({ nodes: result.entities, edges: result.relationships })
          }
          onClose={() => setShowIngest(false)}
        />
      )}

      <div className="absolute bottom-4 left-4 z-10">
        <Legend />
      </div>

      {replayOn && dateBounds && (
        <div className="absolute bottom-4 left-1/2 z-20 flex w-[28rem] max-w-[80vw] -translate-x-1/2 items-center gap-3 rounded-lg border border-slate-700 bg-panel/95 px-4 py-2 shadow-lg">
          <button
            onClick={playPause}
            className="rounded bg-amber-600 px-2 py-1 text-xs font-semibold text-white hover:bg-amber-500"
          >
            {playing ? "❚❚" : "▶"}
          </button>
          <input
            type="range"
            min={dateBounds.min}
            max={dateBounds.max}
            value={cutoff}
            onChange={(e) => {
              setPlaying(false);
              setCutoff(Number(e.target.value));
            }}
            className="flex-1 accent-amber-500"
          />
          <time className="w-24 shrink-0 text-right font-mono text-xs text-amber-300">
            {new Date(cutoff).toISOString().slice(0, 10)}
          </time>
        </div>
      )}

      {empty && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <p className="text-sm text-slate-500">
            Search for an entity above, then double-click a node to expand its connections.
          </p>
        </div>
      )}

      {selected && (
        <DetailPanel
          key={selected}
          entityId={selected}
          expanded={isExpanded}
          onExpand={() => void expand(selected)}
          onCollapse={() => collapse(selected)}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}

export function GraphExplorer({ onLogout }: { onLogout: () => void }) {
  return (
    <ReactFlowProvider>
      <Explorer onLogout={onLogout} />
    </ReactFlowProvider>
  );
}
