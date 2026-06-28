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

  // Build React Flow nodes from domain state + positions + selection + overlays.
  useEffect(() => {
    const nodes: Node<EntityNodeData>[] = Object.values(entities).map((e) => ({
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
  }, [entities, positions, expanded, selected, centralityMap, communityMap, pathNodeIds, setRfNodes]);

  useEffect(() => {
    const edges: Edge[] = Object.values(rels).map((r) => {
      const onPath = pathEdgeIds.has(r.id);
      return {
        id: r.id,
        source: r.source_id,
        target: r.target_id,
        label: prettyRel(r.type),
        animated: onPath,
        markerEnd: { type: MarkerType.ArrowClosed, color: onPath ? PATH_HIGHLIGHT : "#64748b" },
        style: { stroke: onPath ? PATH_HIGHLIGHT : "#475569", strokeWidth: onPath ? 3 : 1.5 },
        labelStyle: { fill: onPath ? PATH_HIGHLIGHT : "#94a3b8", fontSize: 10 },
        labelBgStyle: { fill: "#0b1020", fillOpacity: 0.85 },
      };
    });
    setRfEdges(edges);
  }, [rels, pathEdgeIds, setRfEdges]);

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
