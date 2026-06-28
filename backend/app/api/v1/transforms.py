"""OSINT transform/connector API (#17)."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache
from app.core.deps import get_current_user, require_researcher
from app.crud import entity as entity_crud
from app.db.session import get_db
from app.models.entity import Entity
from app.models.enums import EntityType, RelationshipType
from app.models.relationship import Relationship
from app.models.user import User
from app.schemas.transform import (
    SelectorRead,
    TransformInfo,
    TransformRunRequest,
    TransformRunResponse,
)
from app.services import graph_sync
from app.transforms.base import REGISTRY

router = APIRouter(prefix="/transforms", tags=["transforms"])


def _entity_text(e: Entity) -> str:
    parts = [e.name, e.description or "", " ".join(e.aliases or [])]
    if e.properties:
        parts.append(json.dumps(e.properties))
    return "\n".join(parts)


@router.get("", response_model=list[TransformInfo])
async def list_transforms(_: User = Depends(get_current_user)):
    return [
        TransformInfo(name=t.name, description=t.description, applies_to=sorted(t.applies_to))
        for t in REGISTRY.values()
    ]


@router.post("/{name}/run", response_model=TransformRunResponse)
async def run_transform(
    name: str,
    payload: TransformRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_researcher),
):
    transform = REGISTRY.get(name)
    if transform is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No transform named '{name}'.")

    source: Entity | None = None
    if payload.entity_id is not None:
        source = await entity_crud.get(db, payload.entity_id)
        if source is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity not found.")
        text = _entity_text(source)
    else:
        text = payload.text or ""

    result = transform.run_text(text)
    response = TransformRunResponse(
        transform=name,
        selectors=[SelectorRead(kind=s.kind, value=s.value) for s in result.selectors],
    )

    if not (payload.persist and source is not None):
        return response

    # Materialize selectors as ASSET nodes linked to the source (AI-generated,
    # unverified — like the ingestion pipeline).
    for sel in result.selectors:
        asset = await entity_crud.get_by_name(db, sel.value, EntityType.ASSET)
        if asset is None:
            asset = Entity(
                type=EntityType.ASSET, name=sel.value, aliases=[], description=None,
                properties={"asset_type": sel.kind}, confidence_score=0.0,
                is_ai_generated=True, created_by=current_user.id,
            )
            db.add(asset)
            await db.flush()
            response.created_entities.append(asset)  # type: ignore[arg-type]
        rel = Relationship(
            type=RelationshipType.ASSOCIATED_WITH, source_id=source.id, target_id=asset.id,
            confidence_score=0.0, notes=f"{sel.kind} selector ({name})", properties={},
            is_ai_generated=True, created_by=current_user.id,
        )
        db.add(rel)
        await db.flush()
        response.created_relationships.append(rel)  # type: ignore[arg-type]

    await db.commit()
    # Best-effort projection.
    for ent in response.created_entities:
        refreshed = await entity_crud.get(db, ent.id)
        if refreshed is not None:
            await graph_sync.upsert_entity(refreshed)
    await cache.invalidate_graph()
    return response
