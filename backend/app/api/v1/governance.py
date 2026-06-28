"""Security & governance API: audit-chain verification (#39), retention/purge
(#40), sanitized export (#41), insider-misuse detection (#42)."""
from __future__ import annotations

import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_admin, require_researcher
from app.db.session import get_db
from app.models.casework import Case
from app.models.user import User
from app.schemas.governance import (
    ChainStatusRead,
    ExportPackageRead,
    InsiderFindingRead,
    InsiderResponse,
    PurgeResult,
    RetentionPreview,
)
from app.services import audit, governance

router = APIRouter(prefix="/governance", tags=["governance"])


@router.get("/audit/verify", response_model=ChainStatusRead)
async def verify_audit_chain(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Recompute the audit hash chain and report any tampering (#39)."""
    status_ = await audit.verify_chain(db)
    return ChainStatusRead(valid=status_.valid, entries_checked=status_.entries_checked,
                           broken_at=status_.broken_at)


@router.get("/retention/preview", response_model=RetentionPreview)
async def retention_preview(
    older_than_days: int = Query(default=365, ge=0),
    ai_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Preview entities eligible for purge (excludes legal-hold) (#40)."""
    candidates = await governance.retention_preview(db, older_than_days=older_than_days, ai_only=ai_only)
    return RetentionPreview(
        older_than_days=older_than_days, ai_only=ai_only,
        count=len(candidates), entity_ids=[c.id for c in candidates],
    )


@router.post("/retention/purge", response_model=PurgeResult)
async def retention_purge(
    older_than_days: int = Query(default=365, ge=0),
    ai_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Purge eligible entities (respecting legal holds) (#40)."""
    purged = await governance.retention_purge(db, older_than_days=older_than_days, ai_only=ai_only)
    await db.commit()
    return PurgeResult(older_than_days=older_than_days, ai_only=ai_only, purged=purged)


@router.get("/cases/{case_id}/export", response_model=ExportPackageRead)
async def export_case(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_researcher),
):
    """Sanitized export of a case, redacting objects above the requester's
    clearance/compartments (#41)."""
    if await db.get(Case, case_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found.")
    pkg = await governance.export_case(db, case_id, current_user)
    return ExportPackageRead(
        case_id=pkg.case_id, redacted_count=pkg.redacted_count,
        entities=[asdict(e) for e in pkg.entities],
        relationships=[asdict(r) for r in pkg.relationships],
    )


@router.get("/insider-threat", response_model=InsiderResponse)
async def insider_threat(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Flag analysts with anomalous audit behaviour (volume, deletions, off-hours) (#42)."""
    findings = await governance.detect_insider_anomalies(db)
    return InsiderResponse(
        count=len(findings),
        findings=[InsiderFindingRead(**asdict(f)) for f in findings],
    )
