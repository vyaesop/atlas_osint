"""Unit tests for entity-resolution similarity (#13), pure functions."""
from __future__ import annotations

from app.services import entity_resolution as er


def test_identical_normalized_name():
    score, _ = er.similarity("John Smith", [], "john  smith", [])
    assert score == 1.0


def test_alias_match():
    score, reason = er.similarity("Bob", ["Robert Jones"], "Robert Jones", [])
    assert score >= 0.9
    assert "alias" in reason


def test_token_reorder():
    score, _ = er.similarity("John Smith", [], "Smith John", [])
    assert score >= 0.9  # same token set


def test_dissimilar_names_low():
    score, _ = er.similarity("Alice", [], "Zentech Corp", [])
    assert score < 0.5


def test_levenshtein_close():
    score, _ = er.similarity("Mohammed", [], "Mohamed", [])
    assert score > 0.8
