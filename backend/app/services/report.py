"""Automated intelligence report / target package (#26).

Assembles a grounded dossier from existing services (dashboard aggregation,
confidence, timeline) — a deterministic, testable core — then asks the
configured AI provider for a narrative grounded *only* in that assembled
context, with confidence caveats (the #29 confidence-aware discipline). Every
report is labelled AI-assisted; nothing is asserted beyond the recorded data.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.service import ai_service
from app.schemas.dashboard import DashboardResponse
from app.services import confidence, timeline
from app.services.confidence import ConfidenceResult
from app.services.dashboards import build_dashboard


@dataclass(slots=True)
class ReportResult:
    dashboard: DashboardResponse
    confidence: ConfidenceResult
    key_findings: list[str] = field(default_factory=list)
    timeline_event_count: int = 0
    narrative: str = ""
    provider: str = "heuristic"


def _key_findings(dash: DashboardResponse, conf: ConfidenceResult) -> list[str]:
    e = dash.entity
    findings = [f"{dash.stats.total_connections} recorded connections; "
                f"{dash.stats.total_evidence} evidence items; "
                f"{dash.stats.total_documents} source documents."]
    est = conf.as_dict()
    findings.append(
        f"Confidence {conf.score:.2f} — '{est['estimative_label']}', "
        f"{est['analytic_confidence']} analytic confidence."
    )
    if conf.is_contradicted:
        findings.append("⚠ Subject carries contradicting verified evidence — treat as disputed.")
    findings.append(
        f"Influence: PageRank {dash.influence.pagerank:.4f}, "
        f"degree centrality {dash.influence.degree_centrality:.4f}."
    )
    top = [c.name for c in dash.sections.connections[:5]]
    if top:
        findings.append("Key connections: " + ", ".join(top) + ".")
    return findings


def _context(dash: DashboardResponse, conf: ConfidenceResult, n_events: int) -> str:
    est = conf.as_dict()
    lines = [
        f"Subject: {dash.entity.name} (type: {dash.entity.type.value}).",
        f"Confidence score {conf.score:.2f} ({est['estimative_label']}, "
        f"{est['analytic_confidence']} analytic confidence; "
        f"contradicted: {conf.is_contradicted}).",
        f"Connections: {dash.stats.total_connections}; evidence: {dash.stats.total_evidence}; "
        f"documents: {dash.stats.total_documents}; timeline events: {n_events}.",
        f"Influence: PageRank {dash.influence.pagerank:.4f}, "
        f"degree centrality {dash.influence.degree_centrality:.4f}.",
    ]
    if dash.sections.connections:
        lines.append("Connections: " + ", ".join(
            f"{c.name} ({c.relationship_type})" for c in dash.sections.connections[:10]
        ))
    if dash.sections.documents:
        lines.append("Documents: " + ", ".join(d.title for d in dash.sections.documents[:10]))
    lines.append(
        "Write a concise intelligence brief using ONLY the facts above. State "
        "uncertainty where confidence is low or contradicted; do not invent details."
    )
    return "\n".join(lines)


async def build_report(db: AsyncSession, entity_id: uuid.UUID) -> ReportResult | None:
    dash = await build_dashboard(db, entity_id)
    if dash is None:
        return None
    conf = await confidence.summarize_entity(db, entity_id)
    tl = await timeline.build_timeline(db, entity_id)
    n_events = len(tl.items) if tl else 0

    narrative = await ai_service.summarize(
        f"intelligence report on {dash.entity.name}", _context(dash, conf, n_events)
    )
    return ReportResult(
        dashboard=dash, confidence=conf, key_findings=_key_findings(dash, conf),
        timeline_event_count=n_events, narrative=narrative,
        provider=ai_service.provider_name,
    )
