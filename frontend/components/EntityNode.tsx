import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import { entityColor, ENTITY_LABELS, PATH_HIGHLIGHT } from "@/lib/colors";
import type { EntityType } from "@/lib/types";

export interface EntityNodeData {
  label: string;
  type: EntityType;
  confidence: number;
  expanded: boolean;
  // Analytics overlays (optional):
  metricScore?: number;    // 0..1 normalized centrality, drives the ring scale
  communityColor?: string; // overrides accent when community coloring is on
  colorOverride?: string;  // styling rules engine (#44): color-by attribute
  onPath?: boolean;        // node lies on a highlighted path
  aiGenerated?: boolean;   // extracted by AI, pending verification
}

function EntityNodeComponent({ data, selected }: NodeProps<EntityNodeData>) {
  const accent = data.colorOverride ?? data.communityColor ?? entityColor(data.type);
  const ring = data.onPath
    ? `0 0 0 2px ${PATH_HIGHLIGHT}`
    : selected
      ? `0 0 0 2px ${accent}`
      : undefined;

  // Centrality overlay: scale a halo with the score so influence is visible.
  const haloScale = data.metricScore != null ? 1 + data.metricScore * 0.8 : 1;

  return (
    <div className="relative">
      {data.metricScore != null && (
        <div
          className="absolute left-1/2 top-1/2 -z-10 rounded-full"
          style={{
            width: 180,
            height: 64,
            transform: `translate(-50%, -50%) scale(${haloScale})`,
            background: `${accent}22`,
          }}
        />
      )}
      <div
        className="rounded-lg px-3 py-2 text-left shadow-lg transition"
        style={{
          width: 180,
          background: "#121a2e",
          borderLeft: `4px solid ${accent}`,
          boxShadow: ring,
        }}
      >
        <Handle type="target" position={Position.Left} style={{ background: accent }} />
        <div className="flex items-center justify-between">
          <span
            className="rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
            style={{ background: `${accent}22`, color: accent }}
          >
            {ENTITY_LABELS[data.type]}
          </span>
          {data.metricScore != null ? (
            <span className="text-[10px] font-mono text-slate-400">
              {data.metricScore.toFixed(2)}
            </span>
          ) : (
            data.expanded && <span className="text-[10px] text-slate-500" title="Expanded">●</span>
          )}
        </div>
        <div className="mt-1 flex items-center gap-1">
          <span className="truncate text-sm font-medium text-slate-100" title={data.label}>
            {data.label}
          </span>
          {data.aiGenerated && (
            <span
              className="shrink-0 rounded bg-amber-500/20 px-1 text-[9px] font-semibold text-amber-300"
              title="AI-extracted — pending verification"
            >
              AI
            </span>
          )}
        </div>
        <div className="mt-1 h-1 w-full overflow-hidden rounded bg-ink">
          <div
            className="h-full"
            style={{ width: `${Math.round(data.confidence * 100)}%`, background: accent }}
            title={`Confidence ${(data.confidence * 100).toFixed(0)}%`}
          />
        </div>
        <Handle type="source" position={Position.Right} style={{ background: accent }} />
      </div>
    </div>
  );
}

export const EntityNode = memo(EntityNodeComponent);
