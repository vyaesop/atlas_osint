# Project Atlas — Infrastructure & Deployment (Phase 6)

Local-first, cloud-ready. The same images run under `docker compose` locally and
on Kubernetes in the cloud; only configuration (env / ConfigMap / Secret) changes.

```
infra/
├── k8s/          # Kubernetes manifests (Kustomize)
└── terraform/    # AWS reference IaC for the managed datastores + EKS
```

---

## Scaling architecture (toward 10M nodes / 100M relationships)

| Concern | Mechanism | Where |
|---------|-----------|-------|
| Read latency | **Redis cache** with global graph-version invalidation — analytics/dashboard results are cached and atomically invalidated on any write | `app/core/cache.py`, `CACHE_ENABLED` |
| Write latency | **Background jobs** (arq) — Neo4j projection, search indexing, and ingestion run off the request path | `app/jobs/`, `JOBS_ENABLED` |
| Bulk load | **Batch import** endpoint (`POST /api/v1/imports/bulk`) — entities + relationships in one transaction, projection queued | `app/services/bulk_import.py` |
| Query speed | **Indexes** — pg_trgm GIN on `entities.name` (fast ILIKE), JSONB GIN on `properties`/`aliases` | migration `0004` |
| Horizontal scale | **HPA** on the API and worker; managed Postgres/Redis/OpenSearch scale independently | `k8s/*.yaml`, `terraform/` |

Both `CACHE_ENABLED` and `JOBS_ENABLED` default to **off** (synchronous, in-process)
so local dev and the test suite need no Redis/worker. `docker compose` and the
k8s manifests turn them on.

---

## Local (full stack with worker + cache)

```bash
docker compose up --build          # now includes the `worker` service
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.scripts.seed_admin
```

`backend` and `worker` run with `JOBS_ENABLED=true`; writes enqueue projection
jobs that the worker drains. `CACHE_ENABLED=true` caches analytics/dashboards in
Redis.

---

## Cloud (AWS reference)

### 1. Provision infrastructure

```bash
cd infra/terraform
export TF_VAR_db_password="$(openssl rand -base64 24)"
terraform init
terraform apply
```

This creates a VPC, EKS cluster, RDS Postgres (Multi-AZ), ElastiCache Redis, and
an OpenSearch domain. **Neo4j** has no first-party AWS managed service — use
[Neo4j AuraDB](https://neo4j.com/cloud/aura/) or the Neo4j Helm chart on EKS, and
set `NEO4J_URI` accordingly. Read the connection values from the outputs:

```bash
terraform output postgres_host redis_url opensearch_endpoint
```

### 2. Configure & deploy the app

Put the Terraform outputs into `k8s/config.yaml` (hosts) and create the real
`atlas-secrets` Secret from your secret manager (do **not** commit secrets).
Build & push images, then:

```bash
kubectl apply -k infra/k8s            # namespace, config, backend, worker, frontend, ingress
kubectl -n atlas apply -f infra/k8s/migrate-job.yaml   # alembic upgrade head
```

The `atlas-backend` and `atlas-worker` Deployments autoscale via HPA (CPU). For
queue-aware worker scaling, add a KEDA Redis scaler.

### Image build

```bash
docker build -t ghcr.io/your-org/atlas-backend:latest ./backend
docker build -t ghcr.io/your-org/atlas-frontend:latest ./frontend
docker push ghcr.io/your-org/atlas-backend:latest
docker push ghcr.io/your-org/atlas-frontend:latest
```

---

## Status

This is production-shaped scaffolding: review IAM, security groups, TLS,
encryption, backup/restore, network policies, and resource sizing before a real
deployment. The application layer (caching, jobs, batch import, indexes) is
implemented and tested; the IaC is a reviewed starting point, not a turn-key
stack.
