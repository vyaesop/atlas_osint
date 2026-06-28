"""Unit tests for the in-memory search backend (full-text, fuzzy, alias, semantic)."""
from __future__ import annotations

import pytest

from app.search.embeddings import LocalHashingEmbedder, cosine_similarity
from app.search.inmemory import InMemorySearchBackend
from app.search.models import SearchDocument


def _doc(id_, name, *, aliases=None, description=None) -> SearchDocument:
    embedder = LocalHashingEmbedder(dim=256)
    d = SearchDocument(id=id_, type="person", name=name,
                       aliases=aliases or [], description=description)
    d.embedding = embedder.embed(d.text_blob())
    return d


@pytest.fixture
async def backend():
    b = InMemorySearchBackend()
    await b.index(_doc("1", "Vladimir Petrov", aliases=["V. Petrov"],
                       description="oil executive"))
    await b.index(_doc("2", "Petra Industries", description="energy company"))
    await b.index(_doc("3", "John Smith", aliases=["Johnny"]))
    return b


async def test_exact_name_ranks_first(backend):
    hits = await backend.search("Vladimir Petrov")
    assert hits[0].id == "1"
    assert hits[0].score >= 0.9


async def test_fuzzy_typo_matches(backend):
    # "Vladmir" (missing i) should still find Vladimir via fuzzy matching.
    hits = await backend.search("Vladmir Petrov", semantic=False)
    assert any(h.id == "1" for h in hits)


async def test_alias_match(backend):
    hits = await backend.search("Johnny")
    top = hits[0]
    assert top.id == "3"
    assert top.matched_on in {"alias", "lexical"}


async def test_type_filter(backend):
    await backend.index(SearchDocument(id="9", type="company", name="Vladimir Holdings"))
    hits = await backend.search("Vladimir", types=["company"])
    assert {h.id for h in hits} == {"9"}


async def test_suggest_prefix(backend):
    sugg = await backend.suggest("petr")
    names = {s.name for s in sugg}
    assert "Petra Industries" in names


async def test_semantic_similarity_orders_related_terms():
    embedder = LocalHashingEmbedder(dim=256)
    base = embedder.embed("oil and gas energy company")
    close = embedder.embed("energy company oil")
    far = embedder.embed("classical violin music")
    assert cosine_similarity(base, close) > cosine_similarity(base, far)
