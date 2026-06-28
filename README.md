# Project Atlas

A graph-based intelligence and knowledge platform for mapping evidence-backed
relationships between people, organizations, companies, events, locations, and
documents.

## Who this is for

**Atlas is built for the solo OSINT researcher** — one analyst, self-hosting,
zero budget, working from open sources. Every design decision serves that user:

- **Runs fully local & offline by default** — no API keys, no cloud, no Redis or
  Neo4j required (SQLite + in-memory search + the deterministic heuristic
  extractor). Your collection never leaves your machine unless you opt in.
- **Free tooling only** — maps via OpenStreetMap/Leaflet; optional AI via Google
  Gemini's free tier (`AI_PROVIDER=gemini`, the default), which **degrades
  gracefully to the offline heuristic** when no key is set.
- **Trust over volume** — evidence-driven, source-independent confidence
  (sock-puppet-resistant), ICD-203 estimative language, Admiralty source
  grading, and one-click provenance from any number back to its source.
- **OpSec-aware** — ingestion is paste/upload based; the backend never fetches
  target URLs, so opening a case doesn't beacon your interest. See
  [SECURITY.md](./SECURITY.md) for the egress audit and the Gemini ⇄ OpSec
  trade-off.

The enterprise/agency features (ABAC compartments, classification markings,
multi-analyst casework) are present and enforced, but they are *optional depth*
— not the primary use case. For sensitive work, run with
`AI_PROVIDER=heuristic`, `SEARCH_BACKEND=inmemory`, `NEO4J_ENABLED=false`.

> **Start a guided investigation** at `/investigate`: ingest → resolve
> duplicates → review confidence/provenance → generate a sourced report.

> **Status:** All six phases implemented. Phases 1–5 (auth, CRUD, PostgreSQL,
> Neo4j, evidence-driven confidence, search, graph explorer, analytics, document
> ingestion + AI extraction, dashboards + timeline) plus **Phase 6 scaling &
> deployment** — Redis caching, background-job workers (arq), batch import,
> scaling indexes, and Kubernetes + Terraform infrastructure
> ([infra/](./infra)). Runs **fully local** by default (no API keys, no Redis/
> worker) and is **cloud-ready** via config: point
> `DATABASE_URL`/`SEARCH_BACKEND`/`ANALYTICS_BACKEND`/`AI_PROVIDER` and flip
> `CACHE_ENABLED`/`JOBS_ENABLED`. See [PROGRESS.md](./PROGRESS.md).

---

## Architecture Overview

Atlas uses a **dual-store** model:

| Store        | Role                                                                 |
|--------------|----------------------------------------------------------------------|
| PostgreSQL   | System of record. Entities, relationships, evidence, users, audit log. Strong consistency, rich querying, transactional writes. |
| Neo4j        | Graph projection. Optimized for traversal, path-finding, and graph analytics (Phase 3). Kept in sync from PostgreSQL on write. |

Every write goes to PostgreSQL first (source of truth), then is **projected**
into Neo4j via a graph-sync service. This keeps facts traceable, auditable, and
recoverable while still giving us a fast graph engine.

```
                +-------------------+
   HTTP  --->   |   FastAPI (app)   |
                +---------+---------+
                          |
              writes      |      reads (analytics/traversal)
                          v
              +-----------+-----------+
              |                       |
        +-----v-----+          +------v------+
        | PostgreSQL|  sync -> |    Neo4j    |
        | (records) |          | (graph proj)|
        +-----------+          +-------------+
```

### Domain model (unified entity model)

Rather than one SQL table per node type, Atlas stores all nodes in a single
`entities` table with an `entity_type` discriminator and a JSONB `properties`
column for type-specific fields. Common fields (confidence score, timestamps,
soft-delete) are first-class columns. This mirrors Neo4j's label + property
model, keeps CRUD generic, and scales toward the 10M-node goal without schema
churn. The same approach is used for `relationships`.

---

## Tech Stack (Phase 1)

- **Backend:** FastAPI, Python 3.11, SQLAlchemy 2.0, Pydantic v2, Alembic
- **Records DB:** PostgreSQL 16
- **Graph DB:** Neo4j 5
- **Cache / jobs:** Redis 7
- **Auth:** JWT (access + refresh), bcrypt, role-based access control
- **Search:** OpenSearch 2 (text + kNN vector index); pluggable in-memory backend for dev
- **Analytics:** NetworkX (local) behind a backend protocol; Neo4j GDS as a future swap
- **AI extraction:** pluggable — heuristic (local, default) or Anthropic Claude (`claude-opus-4-8`)
- **Frontend:** Next.js 14 (App Router), React 18, TypeScript, TailwindCSS, React Flow
- **Infra:** Docker + docker-compose

Dashboards/reporting and K8s/Terraform scaling are scoped to later phases — see
[PROGRESS.md](./PROGRESS.md).

---

## Quick Start

```bash
cp .env.example .env          # adjust secrets before anything real
docker compose up --build     # starts postgres, neo4j, redis, backend

# Run migrations (first boot)
docker compose exec backend alembic upgrade head

# Seed an initial admin user
docker compose exec backend python -m app.scripts.seed_admin
```

- API:        http://localhost:8000
- API docs:   http://localhost:8000/docs (Swagger) and `/redoc`
- Neo4j:      http://localhost:7474 (browser)

### Local (without Docker)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

You'll need Postgres, Neo4j, and Redis reachable at the URLs in your `.env`.

---

## Project Layout

```
atlas/
├── docker-compose.yml
├── .env.example
├── PROGRESS.md                # roadmap + phase tracking
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/               # DB migrations
│   └── app/
│       ├── main.py            # FastAPI entrypoint
│       ├── core/              # config, security, RBAC
│       ├── db/                # SQLAlchemy session + Neo4j driver
│       ├── models/            # SQLAlchemy ORM models
│       ├── schemas/           # Pydantic request/response models
│       ├── crud/              # data-access layer
│       ├── services/          # graph sync, audit
│       ├── api/v1/            # route handlers
│       └── scripts/           # seed scripts
└── frontend/                  # (Phase 2+)
```

---

## Testing

```bash
cd backend
pytest
```

## License

Internal / TBD.
