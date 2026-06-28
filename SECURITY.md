# Atlas — Security, Egress & OpSec Review

Audience: a **solo OSINT researcher** self-hosting Atlas. This document is the
output of Task 16 (egress/OpSec audit) and Task 17 (auth/ABAC/export review),
plus the concrete fixes made in the same change set.

---

## 1. Egress / OpSec audit (Task 16)

> **The question that matters for an operative:** *what does running Atlas reveal
> about the investigator, and to whom?*

### How data enters Atlas

All ingestion is **paste-/upload-based**. The backend parses content you give it
— pasted text, an uploaded TXT/PDF/DOCX, EML/MBOX bytes, RSS/Atom **XML you
supply**, crypto transactions — it does **not** fetch target URLs itself. This is
a deliberate OpSec property: opening a case on a target does **not** cause Atlas
to beacon that target (no server-side URL fetch that could reveal your interest).

The `extract-selectors` transform and sanctions/watchlist screening are **fully
local** (regex + local watchlist tables); they make no outbound calls.

### Outbound network calls (the complete list)

| Egress | When | What leaves | Who sees it | Mitigation |
|--------|------|-------------|-------------|------------|
| **Google Gemini API** | `AI_PROVIDER=gemini` (the default) — extraction, summaries, RAG answers, image/audio analysis, NL→query | Document text, entity context, your questions | Google | Set `AI_PROVIDER=heuristic` for **fully offline** operation (see §1.1) |
| **OpenSearch** | `SEARCH_BACKEND=opensearch` | Entity names/aliases for indexing | Your search cluster | Use the default `inmemory` backend, or self-host OpenSearch on the same trust boundary |
| **Seed scripts** (`seed_ethiopia_*`) | Operator runs them manually | Place/entity name lookups | Wikidata / GeoNames | One-off, operator-initiated; run from a non-attributable network if needed |
| Postgres / Neo4j / Redis | Always | All data | Your infrastructure | Self-host; do not point at managed cloud DBs for sensitive work |

### 1.1 The Gemini ⇄ OpSec tension (read this)

Gemini is the **default** because it makes the platform capable out of the box
with a free API key. But **everything sent to Gemini is seen by Google** — that
includes the substance of your collection and, by inference, your priorities.

For OpSec-sensitive investigations, set:

```
AI_PROVIDER=heuristic
```

This keeps **100% of processing on your machine** (deterministic extractor, local
RAG retrieval, no API key, no outbound AI calls). You lose extraction quality, not
functionality. The provider abstraction degrades gracefully — a missing/disabled
key already falls back to the heuristic (Task 5), so there is no accidental
"silent Gemini call" if you forget to set a key.

**Recommendation:** treat `AI_PROVIDER` as a per-investigation OpSec decision, not
a global default. Sensitive target → `heuristic`. Low-sensitivity / public-record
work → `gemini` is fine.

### Local hardening checklist

- [ ] Bind the API + frontend to `127.0.0.1` (or a WireGuard interface), never `0.0.0.0` on an untrusted network.
- [ ] Run inside a VM/namespace with no ambient cloud credentials.
- [ ] Set a strong `SECRET_KEY` (`openssl rand -hex 32`); the default `change-me` must never ship.
- [ ] Rotate `FIRST_ADMIN_PASSWORD` immediately after seeding.
- [ ] For maximum OpSec, run with `AI_PROVIDER=heuristic`, `SEARCH_BACKEND=inmemory`, `NEO4J_ENABLED=false`.

---

## 2. Auth / ABAC / export review (Task 17)

### Model

- **AuthN:** JWT access + refresh (`core/security.py`); bcrypt password hashing.
- **AuthZ (RBAC):** `viewer < researcher < admin` enforced by `require_role`.
- **AuthZ (ABAC, #38):** orthogonal clearance × need-to-know compartments
  (`core/abac.py`). An object is visible only when the subject's clearance
  dominates its classification **and** the subject holds every required
  compartment. Reads **404-hide** (not 403) so existence isn't disclosed.

### Findings & fixes (this change set)

| # | Severity | Finding | Status |
|---|----------|---------|--------|
| F-1 | **High** | `/insights/facets` aggregated **all** entities — the histogram leaked the existence/volume of classified & compartmented data to lower-clearance users. | **Fixed** — facets are ABAC-filtered by the caller. |
| F-2 | **High** | `/insights/risk` (leaderboard) returned entity **names** with no ABAC filter. | **Fixed** — `top_risky(user=…)` filters before scoring. |
| F-3 | **High** | `/insights/diff` listed added/modified entities (and edges) with no ABAC filter. | **Fixed** — entities filtered; an edge is withheld unless **both** endpoints are releasable. |
| F-4 | **Medium** | `/insights/risk/{id}` and `/insights/lineage/{id}` had no clearance gate — a direct id fetch returned a compartmented entity's score/provenance. | **Fixed** — both 404-hide via `_require_access`. |
| F-5 | Verified-good | Sanitized export (#41) correctly redacts above-clearance entities and withholds edges touching redacted nodes. | **Proven** by `tests/test_export_leak.py`. |

The leak class behind F-1…F-4 is the same: **aggregate/derived endpoints must
re-apply ABAC**, because row-level checks elsewhere don't cover them. Tests now
pin this (`tests/test_export_leak.py`, `tests/test_insights_abac.py`).

### Known limitations / backlog (not regressions)

- **Tokens in `localStorage`** (frontend) are XSS-exfiltratable; httpOnly-cookie
  storage + refresh rotation is tracked for a later phase (noted in `lib/auth.ts`).
- **RAG corpus is not compartmented.** `Document` rows carry no classification, so
  RAG retrieval is not ABAC-filtered. For sensitive work, keep classified material
  out of the ingested document corpus, or extend `Document` with a classification
  column and filter `rag.retrieve` — recommended next step.
- **CORS** `allow_origins` must be set explicitly in production (empty by default).

---

## 3. How to re-run these checks

```bash
cd backend
pytest tests/test_export_leak.py tests/test_insights_abac.py tests/test_redteam.py
python -m app.scripts.redteam_corpus   # seed adversarial scenarios into a live instance
```
