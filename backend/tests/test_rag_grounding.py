"""RAG refuses beyond its evidence (Task 15).

The dangerous failure for a retrieval-augmented answer is a fluent, 'cited'
response the corpus does not actually support. These tests pin the guardrails:
no corpus → no answer; weak retrieval → explicit refusal; strong retrieval →
grounded answer.
"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.services import rag


async def _add_doc(db: AsyncSession, title: str, text: str) -> None:
    db.add(Document(title=title, raw_text=text))
    await db.commit()


async def test_empty_corpus_refuses(db_session: AsyncSession):
    result = await rag.answer(db_session, "What does the Helios facility process?")
    assert result.grounded is False
    assert result.citations == []


async def test_weak_overlap_refuses_not_guesses(db_session: AsyncSession):
    # A document that shares only an incidental stopword-ish token with the query.
    await _add_doc(db_session, "Bakery", "A bakery opened downtown selling croissants today.")
    result = await rag.answer(
        db_session, "What uranium enrichment occurs at the Helios facility?"
    )
    # Either no citation clears retrieval, or the top score is below the floor →
    # refusal, never a fabricated answer.
    assert result.grounded is False
    assert rag._REFUSAL in result.answer or "No documents" in result.answer


async def test_strong_overlap_answers_grounded(db_session: AsyncSession):
    await _add_doc(db_session, "Helios dossier",
                   "The Helios facility processes uranium in Karaganda.")
    result = await rag.answer(db_session, "What does the Helios facility process uranium?")
    assert result.grounded is True
    assert result.citations
    assert result.citations[0].title == "Helios dossier"
    assert result.citations[0].score >= rag.MIN_GROUNDING_SCORE
