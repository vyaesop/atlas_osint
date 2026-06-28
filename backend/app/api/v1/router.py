from fastapi import APIRouter

from app.api.v1 import (
    ach,
    ai,
    alerts,
    analytics,
    annotations,
    auth,
    casework,
    dashboards,
    entities,
    evidence,
    geo,
    governance,
    graph,
    imports,
    ingestion,
    relationships,
    resolution,
    sanctions,
    search,
    transforms,
    users,
    workspace,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(entities.router)
api_router.include_router(relationships.router)
api_router.include_router(evidence.router)
api_router.include_router(search.router)
api_router.include_router(graph.router)
api_router.include_router(analytics.router)
api_router.include_router(ingestion.router)
api_router.include_router(ai.router)
api_router.include_router(dashboards.router)
api_router.include_router(imports.router)
api_router.include_router(ach.router)
api_router.include_router(annotations.router)
api_router.include_router(geo.router)
api_router.include_router(resolution.router)
api_router.include_router(transforms.router)
api_router.include_router(sanctions.router)
api_router.include_router(alerts.router)
api_router.include_router(casework.router)
api_router.include_router(workspace.router)
api_router.include_router(governance.router)
