import type { EntityType } from "./types";

// Color-coding per entity type, used by nodes and the legend.
export const ENTITY_COLORS: Record<EntityType, string> = {
  person: "#4f8cff",
  organization: "#9b6bff",
  company: "#22c55e",
  government_agency: "#ef4444",
  event: "#f59e0b",
  location: "#14b8a6",
  document: "#a8a29e",
  asset: "#ec4899",
};

export const ENTITY_LABELS: Record<EntityType, string> = {
  person: "Person",
  organization: "Organization",
  company: "Company",
  government_agency: "Gov. Agency",
  event: "Event",
  location: "Location",
  document: "Document",
  asset: "Asset",
};

export function entityColor(type: EntityType): string {
  return ENTITY_COLORS[type] ?? "#64748b";
}

// Distinct palette for community coloring (cycled by community index).
export const COMMUNITY_PALETTE = [
  "#4f8cff", "#22c55e", "#f59e0b", "#ec4899", "#14b8a6",
  "#9b6bff", "#ef4444", "#84cc16", "#06b6d4", "#f97316",
];

export function communityColor(index: number): string {
  return COMMUNITY_PALETTE[index % COMMUNITY_PALETTE.length];
}

// Amber used to highlight a discovered path.
export const PATH_HIGHLIGHT = "#fbbf24";
