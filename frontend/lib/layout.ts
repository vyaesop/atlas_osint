// Layout strategies for the graph explorer. Each takes the current entities and
// relationships and returns an absolute position per node id. React Flow then
// renders those positions; switching layout is just recomputing positions.

import dagre from "dagre";
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force";

import type { Entity, Relationship } from "./types";

export type LayoutKind = "force" | "hierarchical" | "timeline";

export interface XY {
  x: number;
  y: number;
}

export type Positions = Record<string, XY>;

const NODE_W = 180;
const NODE_H = 64;

function forceLayout(nodes: Entity[], edges: Relationship[]): Positions {
  interface SimNode extends SimulationNodeDatum {
    id: string;
  }
  const simNodes: SimNode[] = nodes.map((n) => ({ id: n.id }));
  const byId = new Map(simNodes.map((n) => [n.id, n]));
  const links: SimulationLinkDatum<SimNode>[] = edges
    .filter((e) => byId.has(e.source_id) && byId.has(e.target_id))
    .map((e) => ({ source: e.source_id, target: e.target_id }));

  const sim = forceSimulation<SimNode>(simNodes)
    .force("charge", forceManyBody().strength(-400))
    .force("link", forceLink<SimNode, SimulationLinkDatum<SimNode>>(links)
      .id((d) => d.id)
      .distance(180))
    .force("center", forceCenter(0, 0))
    .force("collide", forceCollide(NODE_W / 2))
    .stop();

  // Run synchronously to a settled state (no animation frame loop).
  const ticks = Math.ceil(Math.log(0.001) / Math.log(1 - 0.0228));
  for (let i = 0; i < ticks; i += 1) sim.tick();

  const positions: Positions = {};
  for (const n of simNodes) positions[n.id] = { x: n.x ?? 0, y: n.y ?? 0 };
  return positions;
}

function hierarchicalLayout(nodes: Entity[], edges: Relationship[]): Positions {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "TB", nodesep: 60, ranksep: 100 });
  g.setDefaultEdgeLabel(() => ({}));

  for (const n of nodes) g.setNode(n.id, { width: NODE_W, height: NODE_H });
  for (const e of edges) {
    if (nodes.some((n) => n.id === e.source_id) && nodes.some((n) => n.id === e.target_id)) {
      g.setEdge(e.source_id, e.target_id);
    }
  }
  dagre.layout(g);

  const positions: Positions = {};
  for (const n of nodes) {
    const node = g.node(n.id);
    // dagre returns center coords; React Flow uses top-left.
    positions[n.id] = { x: node.x - NODE_W / 2, y: node.y - NODE_H / 2 };
  }
  return positions;
}

// Best-effort date extraction for timeline mode.
function entityDate(e: Entity): number | null {
  const candidates = [
    (e.properties as Record<string, string>)?.date,
    (e.properties as Record<string, string>)?.founded_date,
    (e.properties as Record<string, string>)?.birth_date,
    (e.properties as Record<string, string>)?.publication_date,
    e.created_at,
  ];
  for (const c of candidates) {
    if (!c) continue;
    const t = Date.parse(c);
    if (!Number.isNaN(t)) return t;
  }
  return null;
}

function timelineLayout(nodes: Entity[]): Positions {
  const dated = nodes
    .map((n) => ({ id: n.id, t: entityDate(n) }))
    .filter((d): d is { id: string; t: number } => d.t !== null);

  const positions: Positions = {};
  if (dated.length === 0) {
    nodes.forEach((n, i) => (positions[n.id] = { x: i * 220, y: 0 }));
    return positions;
  }

  const times = dated.map((d) => d.t);
  const min = Math.min(...times);
  const max = Math.max(...times);
  const span = max - min || 1;
  const WIDTH = Math.max(900, dated.length * 160);

  // Sort by time, then stack vertically to avoid overlap at similar dates.
  dated.sort((a, b) => a.t - b.t);
  dated.forEach((d, i) => {
    const x = ((d.t - min) / span) * WIDTH;
    const y = (i % 5) * (NODE_H + 28);
    positions[d.id] = { x, y };
  });

  // Undated nodes get parked in a row beneath the timeline.
  let parked = 0;
  for (const n of nodes) {
    if (!(n.id in positions)) {
      positions[n.id] = { x: parked * 220, y: 6 * (NODE_H + 28) };
      parked += 1;
    }
  }
  return positions;
}

export function computeLayout(
  kind: LayoutKind,
  nodes: Entity[],
  edges: Relationship[],
): Positions {
  switch (kind) {
    case "hierarchical":
      return hierarchicalLayout(nodes, edges);
    case "timeline":
      return timelineLayout(nodes);
    case "force":
    default:
      return forceLayout(nodes, edges);
  }
}
