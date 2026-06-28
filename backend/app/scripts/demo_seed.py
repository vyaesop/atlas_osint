"""Seed a small, illustrative graph into whatever DB ``settings`` points at.

Designed for the local SQLite demo (set DATABASE_URL=sqlite+aiosqlite:///./demo.db).
Creates tables directly via metadata (no Alembic, so it works on SQLite), an
admin user, and a handful of interconnected entities/relationships/evidence so
the explorer and analytics have something to show.

    DATABASE_URL=sqlite+aiosqlite:///./demo.db python -m app.scripts.demo_seed
"""
from __future__ import annotations

import asyncio

from app.core.config import settings
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
import app.models  # noqa: F401  -- register tables
from app.crud import user as user_crud
from app.models.entity import Entity
from app.models.enums import (
    EntityType,
    EvidenceStance,
    RelationshipType,
    Role,
    VerificationStatus,
)
from app.models.evidence import Evidence
from app.models.relationship import Relationship
from app.schemas.user import UserCreate
from app.services import confidence


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Admin user.
        admin = await user_crud.create(
            db,
            UserCreate(
                email=settings.FIRST_ADMIN_EMAIL,
                full_name="Atlas Administrator",
                password=settings.FIRST_ADMIN_PASSWORD,
                role=Role.ADMIN,
            ),
            role=Role.ADMIN,
        )
        await db.flush()

        def ent(name, type_, **props) -> Entity:
            e = Entity(
                type=type_, name=name, aliases=props.pop("aliases", []),
                description=props.pop("description", None), properties=props,
                created_by=admin.id,
            )
            db.add(e)
            return e

        jane = ent("Jane Powell", EntityType.PERSON, occupation="CEO",
                   nationality="British", aliases=["J. Powell"])
        viktor = ent("Viktor Stone", EntityType.PERSON, occupation="Investor",
                     aliases=["V. Stone"])
        amir = ent("Amir Haddad", EntityType.PERSON, occupation="Journalist")
        globex = ent("Globex Corporation", EntityType.COMPANY, industry="Energy",
                     market_value=4.2e9, aliases=["Globex"])
        initech = ent("Initech", EntityType.COMPANY, industry="Software")
        foundation = ent("Atlas Foundation", EntityType.ORGANIZATION,
                         org_type="NGO")
        davos = ent("Davos Summit 2024", EntityType.EVENT, location="Davos")
        geneva = ent("Geneva", EntityType.LOCATION, country="Switzerland")
        await db.flush()

        def rel(s, t, type_, conf=0.0) -> Relationship:
            r = Relationship(type=type_, source_id=s.id, target_id=t.id,
                             confidence_score=conf, created_by=admin.id)
            db.add(r)
            return r

        r_jane_globex = rel(jane, globex, RelationshipType.WORKS_FOR)
        r_viktor_initech = rel(viktor, initech, RelationshipType.FOUNDED)
        r_globex_initech = rel(globex, initech, RelationshipType.PARTNER_OF)
        rel(viktor, globex, RelationshipType.INVESTED_IN)
        rel(jane, davos, RelationshipType.ATTENDED)
        rel(viktor, davos, RelationshipType.ATTENDED)
        rel(globex, geneva, RelationshipType.LOCATED_IN)
        rel(jane, viktor, RelationshipType.ASSOCIATED_WITH)
        rel(foundation, globex, RelationshipType.FUNDED_BY)
        rel(amir, globex, RelationshipType.REPORTED_BY)
        await db.flush()

        # A few verified evidence items so confidence is non-zero.
        def evid(title, *, rel_id=None, entity_id=None, reliability=0.8,
                 stance=EvidenceStance.SUPPORTS):
            db.add(Evidence(
                title=title, reliability_score=reliability, stance=stance,
                verification_status=VerificationStatus.VERIFIED,
                verified_by=admin.id, relationship_id=rel_id, entity_id=entity_id,
                source="Demo dataset", created_by=admin.id,
            ))

        evid("Corporate filing 2024", rel_id=r_jane_globex.id, reliability=0.9)
        evid("Press release", rel_id=r_jane_globex.id, reliability=0.7)
        evid("Founder interview", rel_id=r_viktor_initech.id, reliability=0.95)
        evid("Partnership announcement", rel_id=r_globex_initech.id, reliability=0.6)
        evid("Contradicting report", rel_id=r_globex_initech.id, reliability=0.5,
             stance=EvidenceStance.CONTRADICTS)
        evid("Profile in major outlet", entity_id=jane.id, reliability=0.85)
        await db.flush()

        # Recompute confidence for everything we attached evidence to.
        for rid in (r_jane_globex.id, r_viktor_initech.id, r_globex_initech.id):
            await confidence.recompute_relationship_confidence(db, rid)
        await confidence.recompute_entity_confidence(db, jane.id)

        await db.commit()

    print("Demo data seeded.")
    print(f"  Login: {settings.FIRST_ADMIN_EMAIL} / {settings.FIRST_ADMIN_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())
