"""Proactive alert feed (#28).

Fuses signals the platform already computes into a single ranked feed an analyst
can triage: evidentiary **contradictions** (confidence engine), **structural
anomalies** (Cluster 1), and **sanctions/watchlist hits** (#18). Fully
deterministic — no AI call — so it is cheap to poll and easy to test.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics import advanced
from app.analytics.graph_loader import GraphFilters, load_graph
from app.models.entity import Entity
from app.models.evidence import Evidence
from app.services import confidence, sanctions

_SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}


@dataclass(slots=True)
class Alert:
    kind: str            # contradiction | anomaly | sanctions
    severity: str        # high | medium | low
    title: str
    detail: str
    score: float
    entity_id: str | None = None


async def _contradiction_alerts(db: AsyncSession) -> list[Alert]:
    entity_ids = [
        eid for eid in (await db.execute(
            select(distinct(Evidence.entity_id)).where(Evidence.entity_id.isnot(None))
        )).scalars().all()
    ]
    alerts: list[Alert] = []
    for eid in entity_ids:
        result = await confidence.summarize_entity(db, eid)
        if result.is_contradicted:
            entity = await db.get(Entity, eid)
            name = entity.name if entity else str(eid)
            alerts.append(Alert(
                kind="contradiction", severity="high",
                title=f"Contradicted: {name}",
                detail=(f"{result.supporting_count} supporting vs "
                        f"{result.contradicting_count} contradicting verified sources"),
                score=round(result.contradiction_mass, 4), entity_id=str(eid),
            ))
    return alerts


async def _anomaly_alerts(db: AsyncSession) -> list[Alert]:
    graph = await load_graph(db, GraphFilters())
    result = advanced.detect_anomalies(graph, z_threshold=2.0, limit=20)
    sev = {"hub": "medium", "bridge": "medium", "isolate": "low"}
    return [
        Alert(kind="anomaly", severity=sev.get(a.kind, "low"),
              title=f"Structural anomaly ({a.kind}): {a.name}",
              detail=a.reason, score=a.score, entity_id=a.id)
        for a in result.anomalies
    ]


async def _sanctions_alerts(db: AsyncSession) -> list[Alert]:
    hits = await sanctions.scan_all(db, threshold=0.9, limit=50)
    return [
        Alert(kind="sanctions", severity="high",
              title=f"Watchlist match: {h.entity_name}",
              detail=f"matches {h.entry_name}" + (f" ({h.program})" if h.program else ""),
              score=h.score, entity_id=h.entity_id)
        for h in hits
    ]


async def compute_alerts(
    db: AsyncSession, *, kinds: set[str] | None = None, limit: int = 100
) -> list[Alert]:
    alerts: list[Alert] = []
    if kinds is None or "contradiction" in kinds:
        alerts += await _contradiction_alerts(db)
    if kinds is None or "anomaly" in kinds:
        alerts += await _anomaly_alerts(db)
    if kinds is None or "sanctions" in kinds:
        alerts += await _sanctions_alerts(db)

    alerts.sort(key=lambda a: (_SEVERITY_RANK.get(a.severity, 0), a.score), reverse=True)
    return alerts[:limit]
