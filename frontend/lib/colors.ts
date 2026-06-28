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

// Classification markings (#37) — used by the styling rules engine (#44).
export const CLASSIFICATION_COLORS: Record<string, string> = {
  unclassified: "#64748b",
  official: "#0ea5e9",
  confidential: "#f59e0b",
  secret: "#ef4444",
  top_secret: "#b91c1c",
};

export function classificationColor(level: string): string {
  return CLASSIFICATION_COLORS[level] ?? "#64748b";
}

// Risk bands (#49).
export const RISK_COLORS: Record<string, string> = {
  low: "#22c55e",
  medium: "#f59e0b",
  high: "#ef4444",
};
