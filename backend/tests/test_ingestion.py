"""Unit tests for document parsers and the heuristic extractor (no DB)."""
from __future__ import annotations

import json

import pytest

from app.ai.heuristic import HeuristicExtractor
from app.ingestion.parsers import UnsupportedDocumentError, parse_document
from app.models.enums import EntityType, RelationshipType

extractor = HeuristicExtractor()


def test_parse_txt():
    p = parse_document(b"Hello world.", filename="note.txt")
    assert p.kind == "txt"
    assert p.text == "Hello world."


def test_parse_csv_flattens_rows():
    p = parse_document(b"name,role\nJane,CEO\n", filename="data.csv")
    assert p.kind == "csv"
    assert "Jane, CEO" in p.text


def test_parse_json_flattens():
    body = json.dumps({"person": {"name": "Jane Powell", "role": "CEO"}}).encode()
    p = parse_document(body, filename="rec.json")
    assert "name: Jane Powell" in p.text


def test_unsupported_extension():
    with pytest.raises(UnsupportedDocumentError):
        parse_document(b"...", filename="image.xyz")


def test_content_type_fallback():
    p = parse_document(b"plain", filename=None, content_type="text/plain")
    assert p.kind == "txt"


@pytest.mark.asyncio
async def test_extractor_finds_entities_and_relationships():
    text = (
        "Dr. Jane Powell founded Globex Corporation. "
        "Jane Powell works for Globex Corporation. "
        "Globex Corporation partnered with Initech Inc."
    )
    result = await extractor.extract(text)

    names = {e.name for e in result.entities}
    assert any("Globex Corporation" == n for n in names)
    assert any("Powell" in n for n in names)

    types = {e.type for e in result.entities}
    assert EntityType.COMPANY in types

    rel_types = {r.type for r in result.relationships}
    assert RelationshipType.FOUNDED in rel_types
    assert RelationshipType.PARTNER_OF in rel_types
    # Every relationship carries the sentence it came from (evidence quote).
    assert all(r.supporting_text for r in result.relationships)


@pytest.mark.asyncio
async def test_extractor_empty_text():
    result = await extractor.extract("")
    assert result.entities == []
    assert result.relationships == []
