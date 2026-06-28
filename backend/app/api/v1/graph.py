from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.entity import Entity
from app.models.relationship import Relationship
from app.models.user import User
from app.schemas.graph import GraphResponse

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/entities/{entity_id}/neighbors", response_model=GraphResponse)
async def neighbors(
    entity_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500, description="Max edges to expand"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return the 1-hop neighborhood of an entity in a single payload.

    Powers click-to-expand in the graph explorer: the center node, every edge
    touching it (up to ``limit``), and all entities on the far end of those
    edges — fetched in three queries rather than N+1.
    """
    center = await db.get(Entity, entity_id)
    if center is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity not found.")

    edges_result = await db.execute(
        select(Relationship)
        .where(or_(Relationship.source_id == entity_id, Relationship.target_id == entity_id))
        .limit(limit)
    )
    edges = list(edges_result.scalars().all())

    neighbor_ids = {
        nid
        for edge in edges
        for nid in (edge.source_id, edge.target_id)
        if nid != entity_id
    }

    nodes = [center]
    if neighbor_ids:
        nodes_result = await db.execute(
            select(Entity).where(Entity.id.in_(neighbor_ids))
        )
        nodes.extend(nodes_result.scalars().all())

    return GraphResponse(nodes=nodes, edges=edges)
