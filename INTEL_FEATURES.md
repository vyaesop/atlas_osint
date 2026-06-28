# Atlas — Intelligence Feature Backlog & Progress

Tracker for the 52 post-Phase-6 intelligence features. Single source of truth
for what's built vs. pending. Tell me a number to **skip** and I'll mark it `⏭️`.

**Legend:** ⬜ not started · 🟡 partial / foundation exists · 🔨 in progress · ✅ done · ⏭️ skipped

**Constraints:** zero budget — free/open tooling only. Maps = OpenStreetMap/Leaflet.
AI = **Google Gemini** (`AI_PROVIDER=gemini`, `gemini-2.0-flash`), no Claude/paid APIs.

---

## Cluster 1 — Advanced Graph Analytics  (pure backend, NetworkX) ✅ DONE
| # | Feature | Status |
|---|---------|--------|
| 14 | Hidden-broker + missing-intermediary detection | ✅ |
| 16 | Role inference (financier/facilitator/operative) from graph position | ✅ |
| 48 | Graph anomaly detection (structural outliers, new hubs) | ✅ |
| 50 | What-if node-removal / network-fragmentation simulation | ✅ |
| 51 | Influence / diffusion propagation modeling | ✅ |
| 52 | Cross-case subgraph motif mining | ✅ (graph-wide; cross-case once #31 lands) |

**Delivered:** `analytics/advanced.py` (pure NetworkX), 6 new endpoints under
`/api/v1/analytics/` (`brokers`, `roles`, `anomalies`, `resilience`,
`influence`, `motifs`), result schemas, 14 unit + 5 API tests (all green).

## Cluster 2 — Tradecraft & Analytic Rigor ✅ DONE (5/6; #5 still partial)
| # | Feature | Status |
|---|---------|--------|
| 1 | ACH module — competing-hypotheses scoring over evidence/stance | ✅ |
| 2 | ICD-203 estimative-probability vocabulary on confidence scores | ✅ |
| 3 | Source reliability grading (Admiralty A–F × 1–6) | ✅ |
| 4 | Key-assumptions check + devil's-advocacy flags | ✅ (annotations) |
| 5 | Full analytic lineage/provenance graph | 🟡 (deferred — needs a dedicated provenance view) |
| 6 | Analyst dissent / dissenting-footnote capture per node | ✅ (annotations) |

**Delivered:** ACH (`models/ach.py`, `services/ach.py` pure scorer, `crud/ach.py`,
9 endpoints under `/api/v1/ach/`); Admiralty grading (`services/source_grading.py`
+ `Evidence.source_reliability`/`info_credibility` → feeds confidence engine);
ICD-203 estimative language (`services/estimative.py` → confidence summaries gain
`estimative_label`/`probability_band`/`analytic_confidence`); analytic annotations
(`models/annotation.py` kinds: note/assumption/dissent/devils_advocate, 3 endpoints).
Migration `0005_tradecraft`. 21 new tests (all green).

## Cluster 3 — Temporal & Geospatial ✅ DONE
| # | Feature | Status |
|---|---------|--------|
| 7 | Geospatial map view (Leaflet + OpenStreetMap) | ✅ |
| 8 | Spatiotemporal pattern-of-life reconstruction | ✅ |
| 9 | Co-location / co-travel analysis → suggested edges | ✅ |
| 10 | Temporal graph replay (time-scrubber) | ✅ |
| 11 | N-entity swimlane activity timelines | ✅ |

**Delivered:** geo backend (`services/geo.py` + 3 endpoints); frontend `MapView`
(Leaflet/OSM), `Swimlanes` (`/timeline`, N-entity lanes on a shared axis), and
**temporal replay** in the explorer (date scrubber + play/pause; dated edges
appear at their start, ended edges fade). 11 geo tests; `tsc` + `next build` clean.

**Delivered:** `services/geo.py` (flexible coord parsing + haversine + visit
reconstruction), `/api/v1/geo/` endpoints (`map`, `pattern-of-life/{id}`,
`colocation`); frontend `MapView.tsx` (react-leaflet + free OSM tiles, vector
markers, movement polyline, co-location panel), `/map` route + explorer link.
Added deps: `leaflet`, `react-leaflet`, `@types/leaflet`. 11 new tests. Backend
110 passing; frontend `tsc` + `next build` clean.

## Cluster 4 — Relationship & Entity Intelligence ✅ DONE
| # | Feature | Status |
|---|---------|--------|
| 12 | Link prediction / suggested edges (Adamic-Adar, common-neighbor) | ✅ (via `/analytics/brokers` suggested_links) |
| 13 | Entity resolution / deduplication with merge-unmerge audit | ✅ |
| 15 | Cell / org-hierarchy structure inference | ✅ |

**Delivered:** #13 entity resolution — blocked similarity detection
(`services/entity_resolution.py`), reversible **merge/unmerge** via `EntityMerge`
record (migration `0006`), `/api/v1/resolution/` (duplicates, merge, merges,
unmerge). #15 — `analytics/structure.py` chain-of-command hierarchy (MANAGES/
SUPERVISES layering + cycle detection) and cell-topology classification
(hub_and_spoke/clique/chain/distributed) at `/analytics/hierarchy` & `/cells`.
Also hardened a latent `graph_sync` logging bug. 17 new tests; 124 passing.

## Cluster 5 — OSINT & Ingestion  (5/7 done; #20/#21 → Cluster 6 multimodal)
| # | Feature | Status |
|---|---------|--------|
| 17 | Transform/connector framework (Maltego-style enrichment) | ✅ |
| 18 | Sanctions/PEP/watchlist screening (OFAC/UN/EU) | ✅ |
| 19 | RSS/news/feed monitoring (parse + ingest) | ✅ |
| 20 | Image intelligence (EXIF, OCR, reverse search) | ⬜ (→ #6 Gemini vision) |
| 21 | Audio/video transcription → extraction | ⬜ (→ #6 Gemini audio) |
| 22 | Email/chat ingestion (EML/MBOX) for comms networks | ✅ |
| 23 | Cryptocurrency / on-chain flow tracing | ✅ |

**Delivered (offline/stdlib):** #17 transform framework (`transforms/`,
selector extraction, `/transforms` run+persist as ASSET nodes); #18 sanctions
screening (`WatchlistEntry` + migration `0007`, `/sanctions/` watchlist/screen/
scan); #19 RSS/Atom parse + per-item ingest (`/ingestion/feed`); #22 EML/MBOX →
comms network (`/ingestion/email`); #23 crypto wallet-flow import
(`/ingestion/crypto`). 22 new tests; 140 passing. **Scheduled fetching** for #19
is deployment wiring (arq/cron calls the ingest path).

## Cluster 6 — AI / Agentic (Gemini)
| # | Feature | Status |
|---|---------|--------|
| 24 | Natural-language → graph query | ⬜ |
| 25 | RAG over corpus with source citations | ⬜ |
| 26 | Auto-generated intelligence reports / target packages | ⬜ |
| 27 | Agentic investigation assistant | ⬜ |
| 28 | Proactive contradiction/anomaly alert feed | 🟡 |
| 29 | Confidence-aware AI responses (cite + refuse beyond evidence) | 🟡 |
| 30 | Deepfake / synthetic-media detection flag | ⬜ |

## Cluster 7 — Collaboration & Casework
| # | Feature | Status |
|---|---------|--------|
| 31 | Cases/investigations as first-class objects | ⬜ |
| 32 | Tasking & RFI tracking | ⬜ |
| 33 | Real-time multi-analyst collaboration (presence, comments) | ⬜ |
| 34 | Review → dissemination workflow with markings | ⬜ |
| 35 | Analytic notebook with embedded live graph snapshots | ⬜ |
| 36 | Saved views / bookmarks / pinboards | ⬜ |

## Cluster 8 — Security & Governance
| # | Feature | Status |
|---|---------|--------|
| 37 | Classification & handling markings (per entity/evidence) | ⬜ |
| 38 | ABAC + compartmentalization (beyond 3 roles) | 🟡 |
| 39 | Tamper-evident hash-chained audit log | 🟡 |
| 40 | Data retention / purge / legal-hold policies | ⬜ |
| 41 | Redaction & sanitized export | ⬜ |
| 42 | Anomalous-analyst (insider-misuse) detection | ⬜ |

## Cluster 9 — Visualization & UX
| # | Feature | Status |
|---|---------|--------|
| 43 | Synchronized linked views (graph ⇄ map ⇄ timeline ⇄ table) | ⬜ |
| 44 | Graph styling rules engine | 🟡 |
| 45 | WebGL large-graph rendering + semantic zoom/clustering | ⬜ |
| 46 | Histogram/facet brush filters | ⬜ |
| 47 | Network diff ("what changed since last week") | ⬜ |
| 49 | Per-entity risk scoring | ⬜ |

---

## Changelog
- **2026-06-28** — Tracker created. Activated Gemini provider (`AI_PROVIDER=gemini`).
- **2026-06-28** — ✅ Cluster 1 complete: #12, #14, #16, #48, #50, #51, #52.
  `analytics/advanced.py` + 6 endpoints + 19 tests. Full suite 82 passing.
- **2026-06-28** — ✅ Cluster 2 complete: #1, #2, #3, #4, #6 (#5 deferred).
  ACH + Admiralty grading + ICD-203 + annotations. Migration 0005. 103 passing.
- **2026-06-28** — ✅ Cluster 3 geospatial core: #7, #8, #9. `services/geo.py`
  + 3 endpoints + Leaflet/OSM `MapView` + `/map` route. 110 passing, build clean.
- **2026-06-28** — Codebase pushed to github.com/vyaesop/atlas_osint (private).
- **2026-06-28** — ✅ Cluster 3 complete: added #10 temporal replay (explorer
  scrubber) + #11 N-entity swimlanes (`/timeline`). Build clean. Starting Cluster 4.
- **2026-06-28** — ✅ Cluster 4 complete: #13 entity resolution (merge/unmerge,
  migration 0006) + #15 hierarchy & cell-topology inference. 124 tests passing.
- **2026-06-28** — ✅ Cluster 5 offline scope: #17 transforms, #18 sanctions
  (migration 0007), #19 feeds, #22 email comms, #23 crypto. 140 passing.
  #20/#21 deferred to Cluster 6 (Gemini multimodal).
