"""Attribute-based access control & compartmentalization (#38).

Access is granted only when the subject's **clearance** dominates the object's
**classification** *and* the subject holds every **compartment** (need-to-know
tag) the object requires. This is an axis orthogonal to the RBAC role — a user
can be an admin yet still lack the clearance/compartment for a given object.
"""
from __future__ import annotations

from app.models.enums import Classification

_RANK: dict[Classification, int] = {
    Classification.UNCLASSIFIED: 0,
    Classification.OFFICIAL: 1,
    Classification.CONFIDENTIAL: 2,
    Classification.SECRET: 3,
    Classification.TOP_SECRET: 4,
}


def rank(level: Classification) -> int:
    return _RANK[level]


def can_access(
    *, clearance: Classification, compartments: list[str] | None,
    classification: Classification, required_compartments: list[str] | None,
) -> bool:
    if rank(clearance) < rank(classification):
        return False
    needed = set(required_compartments or [])
    if needed and not needed.issubset(set(compartments or [])):
        return False
    return True


def user_can_access(user, *, classification: Classification, compartments: list[str] | None) -> bool:
    return can_access(
        clearance=getattr(user, "clearance", Classification.UNCLASSIFIED),
        compartments=getattr(user, "compartments", []),
        classification=classification, required_compartments=compartments,
    )
