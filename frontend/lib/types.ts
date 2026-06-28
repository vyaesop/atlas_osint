// Mirrors the backend Pydantic schemas (Phase 1 + 2).

export type EntityType =
  | "person"
  | "organization"
  | "company"
  | "government_agency"
  | "event"
  | "location"
  | "document"
  | "asset";

export type RelationshipType =
  | "WORKS_FOR" | "OWNS" | "FOUNDED" | "MEMBER_OF" | "INVESTED_IN"
  | "PARTNER_OF" | "ATTENDED" | "PARTICIPATED_IN" | "LOCATED_IN"
  | "REPORTED_BY" | "ASSOCIATED_WITH" | "MANAGES" | "SUPERVISES"
  | "FUNDED_BY" | "CONNECTED_TO";

export type Classification =
  | "unclassified" | "official" | "confidential" | "secret" | "top_secret";

export interface Entity {
  id: string;
  type: EntityType;
  name: string;
  aliases: string[];
  description: string | null;
  properties: Record<string, unknown>;
  confidence_score: number;
  is_ai_generated: boolean;
  classification: Classification;
  compartments: string[];
  legal_hold: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface Relationship {
  id: string;
  type: RelationshipType;
  source_id: string;
  target_id: string;
  start_date: string | null;
  end_date: string | null;
  confidence_score: number;
  source_count: number;
  notes: string | null;
  properties: Record<string, unknown>;
  is_ai_generated: boolean;
  created_at: string;
  updated_at: string;
}

export interface IngestionResponse {
  document_id: string;
  document_entity_id: string;
  provider: string;
  summary: {
    entities_created: number;
    relationships_created: number;
    entities_total: number;
    relationships_total: number;
  };
  entities: Entity[];
  relationships: Relationship[];
}

export interface SummaryResponse {
  subject_id: string;
  summary: string;
  provider: string;
  ai_generated: boolean;
}

export interface NeighborRef {
  id: string;
  name: string;
  type: EntityType;
  relationship_id: string;
  relationship_type: RelationshipType;
  direction: "outgoing" | "incoming";
  confidence: number;
  is_ai_generated: boolean;
}

export interface DocumentRef {
  id: string | null;
  title: string;
  source: string | null;
}

export interface InfluenceMetrics {
  total_connections: number;
  degree_centrality: number;
  pagerank: number;
  connections_by_type: Record<string, number>;
}

export interface DashboardStats {
  total_connections: number;
  total_evidence: number;
  total_documents: number;
  confidence_score: number;
}

export interface DashboardSections {
  connections: NeighborRef[];
  organizations: NeighborRef[];
  members: NeighborRef[];
  partners: NeighborRef[];
  events: NeighborRef[];
  locations: NeighborRef[];
  related_entities: NeighborRef[];
  documents: DocumentRef[];
}

export interface DashboardResponse {
  entity: Entity;
  kind: "person" | "organization" | "company" | "event" | "generic";
  stats: DashboardStats;
  influence: InfluenceMetrics;
  sections: DashboardSections;
}

export interface TimelineItem {
  date: string;
  end_date: string | null;
  kind: "attribute" | "relationship" | "event";
  label: string;
  relationship_type: RelationshipType | null;
  related_id: string | null;
  related_name: string | null;
  confidence: number;
}

export interface TimelineResponse {
  entity_id: string;
  entity_name: string;
  items: TimelineItem[];
}

export interface GraphResponse {
  nodes: Entity[];
  edges: Relationship[];
}

export interface SearchHit {
  id: string;
  type: EntityType;
  name: string;
  aliases: string[];
  score: number;
  matched_on: string;
}

export interface Suggestion {
  id: string;
  type: EntityType;
  name: string;
  score: number;
}

export interface ConfidenceSummary {
  score: number;
  support_mass: number;
  contradiction_mass: number;
  supporting_count: number;
  contradicting_count: number;
  neutral_count: number;
  is_contradicted: boolean;
  // ICD-203 estimative language (#2)
  estimative_label: string;
  probability_band: string;
  analytic_confidence: string;
}

// --- Geospatial (#7/#8/#9) ---
export interface GeoFeature {
  id: string;
  name: string;
  type: EntityType;
  lat: number;
  lon: number;
  confidence: number;
  placed_via: "self" | "located_in";
  location_name: string | null;
}

export interface MapResponse {
  count: number;
  features: GeoFeature[];
}

export interface Visit {
  date: string | null;
  location_id: string;
  location_name: string;
  lat: number;
  lon: number;
  source: "located_in" | "event";
  label: string;
}

export interface PatternOfLifeResponse {
  entity_id: string;
  entity_name: string;
  place_count: number;
  total_distance_km: number;
  visits: Visit[];
}

export interface ColocationPair {
  a_id: string;
  a_name: string;
  b_id: string;
  b_name: string;
  location_id: string;
  location_name: string;
  shared_visits: number;
  temporally_overlapping: boolean;
  already_connected: boolean;
  suggested_type: string;
  score: number;
}

export interface ColocationResponse {
  window_days: number;
  pairs: ColocationPair[];
}

export type CentralityMetric = "degree" | "betweenness" | "eigenvector" | "pagerank";
export type PathKind = "shortest" | "strongest" | "most_likely";

export interface RankedNode {
  id: string;
  name: string;
  type: EntityType;
  score: number;
}

export interface CentralityResponse {
  metric: CentralityMetric;
  graph_order: number;
  truncated: boolean;
  results: RankedNode[];
}

export interface Community {
  id: number;
  size: number;
  members: RankedNode[];
}

export interface CommunitiesResponse {
  algorithm: string;
  modularity: number;
  community_count: number;
  graph_order: number;
  truncated: boolean;
  communities: Community[];
}

export interface PathEdge {
  rel_id: string | null;
  source: string;
  target: string;
  type: string | null;
  confidence: number;
}

export interface GraphPath {
  kind: string;
  nodes: RankedNode[];
  edges: PathEdge[];
  length: number;
  score: number;
  bottleneck_confidence: number;
}

export interface PathsResponse {
  found: boolean;
  paths: GraphPath[];
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface CurrentUser {
  id: string;
  email: string;
  full_name: string | null;
  role: "admin" | "researcher" | "viewer";
  is_active: boolean;
}

// --- Cluster 9 insights ---
export interface FacetBucket {
  value: string;
  count: number;
}

export interface Facets {
  total: number;
  by_type: FacetBucket[];
  by_classification: FacetBucket[];
  by_confidence: FacetBucket[];
  by_provenance: FacetBucket[];
  by_month: FacetBucket[];
}

export interface RiskScore {
  entity_id: string;
  name: string;
  score: number;
  band: string;
  factors: Record<string, number>;
  reasons: string[];
}

export interface RiskListResponse {
  count: number;
  results: RiskScore[];
}

export interface DiffItem {
  id: string;
  kind: string;
  label: string;
}

export interface NetworkDiff {
  since: string;
  added_entities: DiffItem[];
  modified_entities: DiffItem[];
  added_relationships: DiffItem[];
  modified_relationships: DiffItem[];
  removed: DiffItem[];
}

export interface LineageNode {
  id: string;
  kind: string;
  label: string;
  ai_generated: boolean;
  verified: boolean | null;
}

export interface LineageEdge {
  source: string;
  target: string;
  relation: string;
}

export interface Lineage {
  entity_id: string;
  summary: string;
  nodes: LineageNode[];
  edges: LineageEdge[];
}
