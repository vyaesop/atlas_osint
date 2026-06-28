"""Dependency-free in-memory search backend.

Combines four signals into one ranked result set:

* **lexical**  — fraction of query tokens present in the document's text
* **fuzzy**    — best normalized edit-distance similarity vs. name/aliases
                 (so typos still match)
* **alias**    — exact alias hit (boosts and tags the match)
* **semantic** — cosine similarity of query/document embeddings

Enabled signals are blended with fixed weights; ``matched_on`` reports the
dominant signal so callers can explain *why* a result surfaced.
"""
from __future__ import annotations

import re

from app.search.embeddings import cosine_similarity, get_embedder
from app.search.models import SearchDocument, SearchHit, Suggestion

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Blend weights for the active signals.
_W_LEXICAL = 0.5
_W_FUZZY = 0.25
_W_SEMANTIC = 0.25
_SCORE_FLOOR = 0.05


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = curr
    return prev[-1]


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    longest = max(len(a), len(b))
    return 1.0 - _levenshtein(a, b) / longest


class InMemorySearchBackend:
    def __init__(self) -> None:
        self._docs: dict[str, SearchDocument] = {}

    async def ensure_ready(self) -> None:  # nothing to provision
        return None

    async def index(self, doc: SearchDocument) -> None:
        self._docs[doc.id] = doc

    async def delete(self, doc_id: str) -> None:
        self._docs.pop(doc_id, None)

    def clear(self) -> None:
        self._docs.clear()

    async def search(
        self,
        query: str,
        *,
        types: list[str] | None = None,
        limit: int = 20,
        fuzzy: bool = True,
        semantic: bool = True,
    ) -> list[SearchHit]:
        query = query.strip()
        if not query:
            return []

        q_tokens = set(_tokens(query))
        q_lower = query.lower()
        q_embedding = get_embedder().embed(query) if semantic else None

        # Normalize weights by which signals are active.
        weights = {"lexical": _W_LEXICAL}
        if fuzzy:
            weights["fuzzy"] = _W_FUZZY
        if semantic:
            weights["semantic"] = _W_SEMANTIC
        total_w = sum(weights.values()) or 1.0

        hits: list[SearchHit] = []
        for doc in self._docs.values():
            if types and doc.type not in types:
                continue

            doc_tokens = set(_tokens(doc.text_blob()))
            lexical = len(q_tokens & doc_tokens) / len(q_tokens) if q_tokens else 0.0

            alias_exact = any(q_lower == a.lower() for a in doc.aliases)
            name_exact = q_lower == doc.name.lower()

            fuzzy_score = 0.0
            if fuzzy:
                candidates = [doc.name, *doc.aliases]
                fuzzy_score = max((_similarity(q_lower, c.lower()) for c in candidates), default=0.0)

            semantic_score = 0.0
            if semantic and q_embedding is not None and doc.embedding:
                semantic_score = max(0.0, cosine_similarity(q_embedding, doc.embedding))

            subscores = {"lexical": lexical}
            if fuzzy:
                subscores["fuzzy"] = fuzzy_score
            if semantic:
                subscores["semantic"] = semantic_score

            score = sum(weights[k] * v for k, v in subscores.items()) / total_w
            if name_exact or alias_exact:
                score = min(1.0, score + 0.4)  # exact match boost

            if score < _SCORE_FLOOR:
                continue

            dominant = max(subscores, key=subscores.get)
            matched_on = "alias" if alias_exact and not name_exact else dominant
            hits.append(
                SearchHit(
                    id=doc.id, type=doc.type, name=doc.name,
                    aliases=list(doc.aliases), score=round(score, 4),
                    matched_on=matched_on,
                )
            )

        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:limit]

    async def suggest(self, prefix: str, *, limit: int = 10) -> list[Suggestion]:
        prefix = prefix.strip().lower()
        if not prefix:
            return []
        out: list[Suggestion] = []
        for doc in self._docs.values():
            names = [doc.name, *doc.aliases]
            best = 0.0
            for n in names:
                nl = n.lower()
                if nl.startswith(prefix):
                    best = max(best, 1.0)
                elif prefix in nl:
                    best = max(best, 0.6)
            if best > 0:
                out.append(Suggestion(id=doc.id, type=doc.type, name=doc.name, score=best))
        out.sort(key=lambda s: (s.score, -len(s.name)), reverse=True)
        return out[:limit]
