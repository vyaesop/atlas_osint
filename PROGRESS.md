# Project Atlas — Build Progress

This document tracks implementation across the six planned phases. It is the
single source of truth for "what is actually built" vs. "what is specified."

Legend: ✅ done · 🚧 in progress · ⬜ not started

---

## Phase 1 — Foundation (Auth, CRUD, Neo4j) — 🚧

| Area | Item | Status |
|------|------|--------|
| Architecture | Dual-store design (Postgres source-of-truth + Neo4j projection) | ✅ |
| Architecture | Folder structure & module layout | ✅ |
| Infra | docker-compose (postgres, neo4j, redis, backend) | ✅ |
| Infra | Backend Dockerfile | ✅ |
| Infra | `.env.example` + config via pydantic-settings | ✅ |
| Schema | SQLAlchemy models: users, entities, relationships, evidence, audit | ✅ |
| Schema | Alembic migration setup | ✅ |
| Schema | Unified entity model (JSONB props + type discriminator) | ✅ |
| Neo4j | Async driver wrapper + connection lifecycle | ✅ |
| Neo4j | Graph sync service (upsert/delete entities & relationships) | ✅ |
| Auth | Password hashing (bcrypt) | ✅ |
| Auth | JWT access + refresh tokens | ✅ |
| Auth | RBAC (Admin / Researcher / Viewer) dependencies | ✅ |
| Auth | Audit logging of mutations | ✅ |
| API | Auth endpoints (register, login, refresh, me) | ✅ |
| API | User management endpoints (admin) | ✅ |
| API | Entity CRUD (all node types via unified model) | ✅ |
| API | Relationship CRUD | ✅ |
| API | Evidence CRUD | ✅ |
| API | OpenAPI docs (auto via FastAPI) | ✅ |
| Tests | Auth + CRUD smoke tests | ✅ |
| Tooling | Admin seed script | ✅ |

**Phase 1 exit criteria:** a researcher can register/login, create entities of
any node type, link them with typed relationships, attach evidence, and have all
of it projected into Neo4j — with every mutation written to the audit log.

---

## Phase 2 — Evidence depth, Search, Visualization — 🚧

| Area | Item | Status |
|------|------|--------|
| Evidence | Stance (supports / contradicts / neutral) on evidence | ✅ |
| Evidence | Verification workflow (unverified → verified / disputed) + `verify` endpoint | ✅ |
| Evidence | Migration 0002 (stance, verification cols) | ✅ |
| Confidence | Direction × corroboration scoring engine (pure + tested) | ✅ |
| Confidence | Recompute on evidence create/update/verify/delete; persisted | ✅ |
| Confidence | Contradiction detection + live confidence-summary endpoints | ✅ |
| Search | Pluggable `SearchBackend` (in-memory + OpenSearch) | ✅ |
| Search | Full-text, fuzzy (Levenshtein), alias matching | ✅ |
| Search | Semantic search (embedding cosine; pluggable provider) | ✅ |
| Search | Entity suggestions (type-ahead) | ✅ |
| Search | Index on entity write + admin reindex endpoint | ✅ |
| Search | OpenSearch service in docker-compose + index mappings | ✅ |
| Graph API | 1-hop neighborhood endpoint (powers expand) | ✅ |
| Frontend | Next.js + TS + Tailwind + React Flow scaffold | ✅ |
| Frontend | Auth (login, token refresh, route guard) | ✅ |
| Frontend | Graph explorer: search/focus, expand/collapse, color-coded types, edge labels | ✅ |
| Frontend | Layouts: force-directed, hierarchical (dagre), timeline | ✅ |
| Frontend | Detail panel with live confidence breakdown | ✅ |
| Frontend | Dockerfile + compose service | ✅ |
| Tests | Confidence math, search backend, Phase 2 API flows, graph endpoint | ✅ (29 backend tests) |
| Verify | `tsc --noEmit` clean, `next build` clean | ✅ |

**Relationship suggestions** (suggesting plausible new edges) are deferred to
Phase 3, where graph topology (common-neighbor / adamic-adar) makes them
meaningful. Semantic search currently uses a dependency-free local hashing
embedder; swapping in a transformer/hosted model is a single provider change
(see `app/search/embeddings.py`).

## Phase 3 — Analytics & Graph Algorithms — 🚧

| Area | Item | Status |
|------|------|--------|
| Engine | Pluggable `AnalyticsBackend` (NetworkX now, Neo4j-GDS stub for later) | ✅ |
| Engine | Graph loader from Postgres (type/rel/confidence filters, ego scope, node cap) | ✅ |
| Centrality | Degree, betweenness (NetworkX) | ✅ |
| Centrality | Eigenvector + PageRank (pure-Python power iteration, no scipy/numpy) | ✅ |
| Community | Louvain + modularity + segmentation | ✅ |
| Paths | Shortest (+ k alternatives via Yen) | ✅ |
| Paths | Strongest (widest / bottleneck) | ✅ |
| Paths | Most-likely (max product of confidences) | ✅ |
| API | `/analytics/centrality`, `/communities`, `/paths` | ✅ |
| Cloud-ready | `DATABASE_URL` override for managed/cloud Postgres | ✅ |
| Frontend | Analytics panel: centrality sizing, community coloring, path highlight | ✅ |
| Tests | Centrality, communities, paths (unit + API) — 43 backend tests | ✅ |
| Verify | `tsc --noEmit` + `next build` clean | ✅ |

**Deployment note:** the platform runs fully **local** (NetworkX over Postgres,
in-memory search, Neo4j optional) yet is **cloud-ready** — point `DATABASE_URL`
at a managed Postgres, flip `SEARCH_BACKEND=opensearch`, and (Phase 6)
`ANALYTICS_BACKEND=neo4j_gds` for scale, with no code changes.

The Neo4j-GDS analytics backend is a documented stub; the spec's "GDS" path is
deferred to Phase 6 scaling since NetworkX covers local/moderate graphs and
keeps deployment dependency-light.

## Phase 4 — Document Ingestion & AI Extraction — 🚧

| Area | Item | Status |
|------|------|--------|
| Parsers | TXT / CSV / JSON (stdlib) + PDF / DOCX (lazy `pypdf` / `python-docx`) | ✅ |
| AI | Pluggable `ExtractionProvider` (heuristic default + Anthropic Claude) | ✅ |
| AI | Heuristic extractor (regex/rule-based, dependency-free, local) | ✅ |
| AI | Anthropic provider: `claude-opus-4-8`, structured outputs, adaptive thinking | ✅ |
| Pipeline | Ingest text/file → extract → create AI-labeled entities/relationships | ✅ |
| Provenance | `is_ai_generated` on entities/relationships/evidence; `documents` table; migration 0003 | ✅ |
| Provenance | AI claims attach **unverified** evidence; confidence stays 0 until verified | ✅ |
| Summaries | Entity + timeline summaries, grounded in graph data, labeled AI-generated | ✅ |
| API | `/ingestion/text`, `/ingestion/upload`, `/ai/summarize/*`, `/ai/provider` | ✅ |
| Frontend | AI badge on nodes + detail panel; ingest-text panel; "Summarize (AI)" button | ✅ |
| Tests | Parsers, heuristic extractor, ingestion flow, AI labeling, summaries (55 backend tests) | ✅ |
| Verify | `tsc --noEmit` + `next build` clean | ✅ |

**Local-first / cloud-ready:** the default `heuristic` provider runs entirely
locally with no API key. Set `AI_PROVIDER=anthropic` + `ANTHROPIC_API_KEY` to use
Claude — one config change, no code change. Every AI-produced entity,
relationship, evidence item, and summary is labeled AI-generated and starts
unverified, feeding the Phase 2 verification workflow.

**Bulk ingestion** currently processes one document per request synchronously;
multi-file batch + a background queue are folded into the Phase 6 scaling work.

## Phase 5 — Dashboards & Reporting — 🚧

| Area | Item | Status |
|------|------|--------|
| Dashboard | Aggregation service: sections by entity type + influence metrics | ✅ |
| Dashboard | Person: connections, organizations, events, documents, influence | ✅ |
| Dashboard | Organization/Company: members, partners, events, documents | ✅ |
| Dashboard | Event: participants/related entities, locations, documents | ✅ |
| Dashboard | Influence metrics (degree + PageRank over 2-hop ego, connection breakdown) | ✅ |
| Timeline | Build from attribute dates + dated relationships (start/end) + connected events | ✅ |
| Timeline | Filtering (relationship type, date window) | ✅ |
| API | `/dashboards/entities/{id}`, `/timeline/entities/{id}` | ✅ |
| Frontend | `/dashboard/[id]` route: stat cards, influence, typed sections, document refs | ✅ |
| Frontend | Timeline view + two-entity comparison (`?compare=`) + date filter | ✅ |
| Frontend | "Open dashboard" link from the explorer detail panel; cross-linked sections | ✅ |
| Tests | Dashboard sections by type, members/partners, timeline ordering + filters (59 backend tests) | ✅ |
| Verify | `tsc --noEmit` + `next build` clean (`/dashboard/[id]` route builds) | ✅ |

Dashboards reuse the existing stores — relationships for sections, evidence for
document references, the analytics engine for influence — so there's no new
data model; it's a presentation layer. Timeline "zoom" is expressed as date-range
filtering; richer visual zoom is a frontend polish item for later.

## Phase 6 — Scale, Optimization, Deployment — 🚧

| Area | Item | Status |
|------|------|--------|
| Caching | Redis read-through cache with global graph-version invalidation | ✅ |
| Caching | Applied to centrality, communities, and dashboard endpoints | ✅ |
| Jobs | arq worker + `dispatch` abstraction (inline default / queued when enabled) | ✅ |
| Jobs | Graph projection, search indexing, ingestion offloaded off the request path | ✅ |
| Batch | Bulk import endpoint (`/imports/bulk`) — entities + relationships, one txn, queued projection | ✅ |
| Indexing | Migration 0004: pg_trgm GIN on name (fast ILIKE), JSONB GIN on properties/aliases, audit time index | ✅ |
| Infra | docker-compose `worker` service; jobs + cache enabled in the compose stack | ✅ |
| Infra | Kubernetes manifests (Kustomize): backend/worker/frontend, ConfigMap/Secret, Ingress, HPAs, migrate Job | ✅ |
| Infra | Terraform (AWS reference): VPC, EKS, RDS Postgres, ElastiCache Redis, OpenSearch | ✅ |
| Docs | `infra/README.md` deployment guide (local + cloud) | ✅ |
| Tests | Cache no-op, bulk import (create/dedupe/skip/empty) — 63 backend tests | ✅ |
| Verify | YAML validated (k8s + compose); migration + jobs modules compile | ✅ |

**Backward-compatible by default:** `CACHE_ENABLED` and `JOBS_ENABLED` default to
false, so dev/local/tests keep the synchronous in-process behavior with no Redis
or worker required. The compose stack and k8s manifests turn both on.

**Toward 10M nodes / 100M relationships:** reads are cached + version-invalidated;
writes are queued; bulk load is transactional + batched; hot query paths are
indexed (trigram name search, JSONB GIN); API and worker scale horizontally via
HPA, with Postgres/Redis/OpenSearch as managed, independently-scaled services.

**Reviewed scaffolding, not turn-key:** the application scaling layer is built and
tested; the Terraform/K8s IaC is a reviewed starting point — IAM, TLS, encryption,
backups, network policies, and sizing need a hardening pass before production. A
queue-aware worker autoscaler (KEDA Redis scaler) and a full-reprojection job
(rebuild Neo4j/search from Postgres) are the natural next operational additions.

---

## Decisions Log

- **2026-06-18 — Unified entity table.** Chose a single `entities` table with a
  `type` enum + JSONB `properties` over table-per-node-type. Rationale: matches
  Neo4j's flexible label/property model, keeps CRUD generic, avoids schema
  migrations as new node types/fields appear, and scales better toward the
  10M-node goal. Type-specific validation is enforced in the Pydantic layer.
- **2026-06-18 — Postgres as source of truth, Neo4j as projection.** Keeps every
  fact transactional, auditable, and recoverable; Neo4j is rebuildable from
  Postgres. Sync happens synchronously on write in Phase 1; moves to background
  jobs in Phase 6.
- **2026-06-18 — Async SQLAlchemy + asyncpg.** Single async stack end-to-end to
  avoid thread-pool juggling under load.
- **2026-06-18 (Phase 2) — Confidence = direction × corroboration.** Confidence
  is `(S/(S+C)) · (1 − e^−(S+C)/τ)` over *verified* evidence mass, so agreement
  raises it, contradiction lowers it, and a single source is never read as
  certain. Verified-only by default keeps unverified/AI claims from inflating
  scores. Math is a pure function (`services/confidence.py`), unit-tested.
- **2026-06-18 (Phase 2) — Search behind a backend protocol.** `SearchBackend`
  has an in-memory implementation (dev/tests; full-text + fuzzy + alias +
  semantic, zero deps) and an OpenSearch implementation (production, text + kNN
  vectors). Postgres stays source of truth; the index is rebuildable via the
  admin reindex endpoint. Indexing failures are swallowed like graph-sync.
- **2026-06-18 (Phase 2) — Frontend proxies /api/*.** Next rewrites forward to
  the backend so the browser is same-origin (no CORS in dev). React Flow is
  dynamically imported (`ssr: false`). Layout strategies are pure functions
  returning positions, so switching layout just recomputes coordinates.
- **2026-06-18 (Phase 3) — NetworkX over Postgres, not GDS, for now.** Analytics
  loads a graph snapshot from Postgres (source of truth) and computes locally.
  PageRank/eigenvector are hand-rolled power iteration to avoid scipy/numpy, so
  local install stays light. `AnalyticsBackend` keeps the door open for a Neo4j
  GDS backend at scale (Phase 6) behind the same API.
- **2026-06-18 (Phase 3) — Local-first, cloud-ready.** Per product direction the
  stack runs entirely on a laptop, but every external store is swappable via env
  (`DATABASE_URL`, `SEARCH_BACKEND`, `ANALYTICS_BACKEND`) so a future move to
  managed/cloud databases needs config, not code.
- **2026-06-18 (Phase 3) — Directed PageRank, undirected for the rest.** PageRank
  runs on the directed graph (authority = being pointed to); degree/betweenness/
  eigenvector/community/paths use the confidence-weighted undirected view, which
  matches how investigators read "connectedness."
- **2026-06-18 (Phase 4) — Heuristic extractor as the local default.** AI
  extraction is pluggable; the dependency-free heuristic extractor is the default
  so the platform ingests documents locally with no API key. The Anthropic Claude
  provider (`claude-opus-4-8`, structured outputs via `messages.parse`, adaptive
  thinking) activates via `AI_PROVIDER=anthropic` — same interface, no code change.
- **2026-06-18 (Phase 4) — AI output is unverified by construction.** Extracted
  entities/relationships carry `is_ai_generated=True` and their evidence lands
  `unverified`; since the confidence engine counts only verified evidence, AI
  claims never inflate confidence until a researcher signs off. Documents are
  both a graph node (Entity of type `document`) and a `documents` record holding
  raw text + extraction metadata.
- **2026-06-18 (Phase 5) — Dashboards are a pure presentation layer.** No new
  tables: the dashboard service aggregates relationships into typed sections,
  pulls document refs from evidence sources + DOCUMENT neighbors, and reuses the
  Phase 3 analytics engine for influence (degree + PageRank over the 2-hop ego
  network). The same section payload serves every type; the frontend shows the
  ones relevant to Person / Organization / Event. Timeline comparison is two
  independent timeline fetches rendered side by side.
- **2026-06-19 (Phase 6) — Version-stamped cache, no per-key invalidation.**
  Analytics/dashboards are pure functions of the graph, so cache keys embed a
  single Redis-stored graph version; any write bumps it and instantly orphans
  every cached result. Correct and trivial vs. tracking per-entity dependencies.
- **2026-06-19 (Phase 6) — Jobs behind a dispatch seam, off by default.** Write
  paths call `app.jobs.dispatch.*` instead of graph-sync/search directly. With
  `JOBS_ENABLED` false they run inline (unchanged, tested); true enqueues to arq
  and the worker reloads from Postgres — so the same code path serves both, and
  the queue is the only thing added for scale. Postgres stays source of truth;
  Neo4j/search are rebuildable projections.
- **2026-06-19 (Phase 6) — Gemini provider added.** Per product direction, a
  Google Gemini extraction provider (`AI_PROVIDER=gemini`, `google-genai`,
  structured output) joins heuristic/anthropic behind the same interface.
- **2026-06-19 (Phase 6) — Managed datastores, app on K8s.** Terraform provisions
  Postgres/Redis/OpenSearch as managed services + an EKS cluster; the app
  (backend/worker/frontend) deploys via Kustomize and references datastores by
  host. Neo4j has no first-party AWS managed option — AuraDB or Helm, fed in via
  `NEO4J_URI`.
