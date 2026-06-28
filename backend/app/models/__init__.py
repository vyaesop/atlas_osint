"""ORM models. Importing this package registers all tables on ``Base.metadata``
so that Alembic autogenerate and ``create_all`` see them.
"""
from app.models.ach import AchAnalysis, AchHypothesis, AchItem, AchRating
from app.models.annotation import Annotation
from app.models.audit import AuditLog
from app.models.casework import Case, CaseItem, Comment, Task
from app.models.document import Document
from app.models.entity import Entity
from app.models.entity_merge import EntityMerge
from app.models.evidence import Evidence
from app.models.relationship import Relationship
from app.models.user import User
from app.models.watchlist import WatchlistEntry
from app.models.workspace import Notebook, NotebookBlock, SavedView

__all__ = [
    "User", "Entity", "Relationship", "Evidence", "AuditLog", "Document",
    "AchAnalysis", "AchHypothesis", "AchItem", "AchRating", "Annotation",
    "EntityMerge", "WatchlistEntry",
    "Case", "CaseItem", "Task", "Comment",
    "SavedView", "Notebook", "NotebookBlock",
]
