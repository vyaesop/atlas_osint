// Typed API client. Calls are proxied to the backend via next.config rewrites,
// so the browser only ever talks to same-origin /api/*.

import { clearTokens, getAccessToken, getRefreshToken, setTokens } from "./auth";
import type {
  CentralityMetric,
  CentralityResponse,
  ColocationResponse,
  CommunitiesResponse,
  ConfidenceSummary,
  CurrentUser,
  DashboardResponse,
  Entity,
  Facets,
  GraphResponse,
  IngestionResponse,
  Lineage,
  MapResponse,
  NetworkDiff,
  PathKind,
  PathsResponse,
  PatternOfLifeResponse,
  Relationship,
  RiskListResponse,
  RiskScore,
  SearchHit,
  Suggestion,
  SummaryResponse,
  TimelineResponse,
  TokenPair,
  ConfidenceProvenance,
  DuplicatesResponse,
  EntityReport,
} from "./types";

const BASE = "/api/v1";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  const headers = new Headers(options.headers);
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${BASE}${path}`, { ...options, headers });

  // Transparently refresh once on a 401.
  if (res.status === 401 && retry && getRefreshToken()) {
    const refreshed = await tryRefresh();
    if (refreshed) return request<T>(path, options, false);
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

async function tryRefresh(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) return false;
  const res = await fetch(`${BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!res.ok) {
    clearTokens();
    return false;
  }
  const tokens = (await res.json()) as TokenPair;
  setTokens(tokens.access_token, tokens.refresh_token);
  return true;
}

export const api = {
  async login(email: string, password: string): Promise<TokenPair> {
    // OAuth2 password flow expects form-encoded body.
    const form = new URLSearchParams({ username: email, password });
    const res = await fetch(`${BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form,
    });
    if (!res.ok) throw new ApiError(res.status, "Invalid email or password");
    const tokens = (await res.json()) as TokenPair;
    setTokens(tokens.access_token, tokens.refresh_token);
    return tokens;
  },

  me: () => request<CurrentUser>("/auth/me"),

  search: (q: string, opts: { types?: string[]; fuzzy?: boolean; semantic?: boolean } = {}) => {
    const params = new URLSearchParams({ q });
    if (opts.fuzzy === false) params.set("fuzzy", "false");
    if (opts.semantic === false) params.set("semantic", "false");
    (opts.types ?? []).forEach((t) => params.append("type", t));
    return request<SearchHit[]>(`/search?${params.toString()}`);
  },

  suggest: (q: string) =>
    request<Suggestion[]>(`/search/suggest?q=${encodeURIComponent(q)}`),

  getEntity: (id: string) => request<Entity>(`/entities/${id}`),

  neighbors: (id: string, limit = 100) =>
    request<GraphResponse>(`/graph/entities/${id}/neighbors?limit=${limit}`),

  entityConfidence: (id: string) =>
    request<ConfidenceSummary>(`/entities/${id}/confidence`),

  getRelationship: (id: string) => request<Relationship>(`/relationships/${id}`),

  listRelationships: (entityId: string) =>
    request<Relationship[]>(`/relationships?entity_id=${entityId}`),

  centrality: (metric: CentralityMetric, opts: { egoEntityId?: string; limit?: number } = {}) => {
    const params = new URLSearchParams({ metric, limit: String(opts.limit ?? 100) });
    if (opts.egoEntityId) params.set("ego_entity_id", opts.egoEntityId);
    return request<CentralityResponse>(`/analytics/centrality?${params.toString()}`);
  },

  communities: (opts: { egoEntityId?: string; minSize?: number } = {}) => {
    const params = new URLSearchParams({ min_size: String(opts.minSize ?? 2) });
    if (opts.egoEntityId) params.set("ego_entity_id", opts.egoEntityId);
    return request<CommunitiesResponse>(`/analytics/communities?${params.toString()}`);
  },

  paths: (source: string, target: string, kind: PathKind, k = 1) => {
    const params = new URLSearchParams({ source, target, kind, k: String(k) });
    return request<PathsResponse>(`/analytics/paths?${params.toString()}`);
  },

  aiProvider: () => request<{ provider: string }>("/ai/provider"),

  ingestText: (title: string, text: string) =>
    request<IngestionResponse>("/ingestion/text", {
      method: "POST",
      body: JSON.stringify({ title, text }),
    }),

  summarizeEntity: (id: string) =>
    request<SummaryResponse>(`/ai/summarize/entity/${id}`, { method: "POST" }),

  dashboard: (id: string) =>
    request<DashboardResponse>(`/dashboards/entities/${id}`),

  timeline: (id: string, opts: { dateFrom?: string; dateTo?: string } = {}) => {
    const params = new URLSearchParams();
    if (opts.dateFrom) params.set("date_from", opts.dateFrom);
    if (opts.dateTo) params.set("date_to", opts.dateTo);
    const qs = params.toString();
    return request<TimelineResponse>(`/timeline/entities/${id}${qs ? `?${qs}` : ""}`);
  },

  // --- Geospatial (#7/#8/#9) ---
  geoMap: (types: string[] = []) => {
    const params = new URLSearchParams();
    types.forEach((t) => params.append("type", t));
    const qs = params.toString();
    return request<MapResponse>(`/geo/map${qs ? `?${qs}` : ""}`);
  },

  patternOfLife: (id: string) =>
    request<PatternOfLifeResponse>(`/geo/pattern-of-life/${id}`),

  colocation: (opts: { windowDays?: number; limit?: number } = {}) => {
    const params = new URLSearchParams({
      window_days: String(opts.windowDays ?? 7),
      limit: String(opts.limit ?? 50),
    });
    return request<ColocationResponse>(`/geo/colocation?${params.toString()}`);
  },

  // --- Cluster 9 insights ---
  facets: (type?: string) =>
    request<Facets>(`/insights/facets${type ? `?type=${type}` : ""}`),

  topRisk: (limit = 25) => request<RiskListResponse>(`/insights/risk?limit=${limit}`),

  entityRisk: (id: string) => request<RiskScore>(`/insights/risk/${id}`),

  diff: (sinceIso: string) =>
    request<NetworkDiff>(`/insights/diff?since=${encodeURIComponent(sinceIso)}`),

  lineage: (id: string) => request<Lineage>(`/insights/lineage/${id}`),

  // --- Golden workflow (Task 7) ---
  confidenceProvenance: (id: string) =>
    request<ConfidenceProvenance>(`/entities/${id}/confidence/provenance`),

  duplicates: (threshold = 0.82) =>
    request<DuplicatesResponse>(`/resolution/duplicates?threshold=${threshold}`),

  report: (id: string) =>
    request<EntityReport>(`/ai/report/entity/${id}`, { method: "POST" }),
};
