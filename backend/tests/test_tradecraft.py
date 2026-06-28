"""Unit tests for Cluster 2 tradecraft: estimative language (#2), Admiralty
source grading (#3), and ACH scoring (#1). Pure functions, no DB."""
from __future__ import annotations

import pytest

from app.models.enums import AchConsistency, InfoCredibility, SourceReliability
from app.services import ach, estimative, source_grading


# --- #2 ICD 203 estimative language --------------------------------------- #

@pytest.mark.parametrize("score,term", [
    (0.02, "almost no chance"),
    (0.10, "very unlikely"),
    (0.30, "unlikely"),
    (0.50, "roughly even chance"),
    (0.70, "likely"),
    (0.90, "very likely"),
    (0.98, "almost certain"),
    (1.0, "almost certain"),
])
def test_estimative_label_bands(score, term):
    assert estimative.estimative_label(score)[0] == term


def test_analytic_confidence_levels():
    assert estimative.analytic_confidence(3.0, 0.0, is_contradicted=False) == "high"
    assert estimative.analytic_confidence(1.5, 0.0, is_contradicted=False) == "moderate"
    assert estimative.analytic_confidence(0.5, 0.0, is_contradicted=False) == "low"
    # Contradiction caps confidence at moderate even with lots of mass.
    assert estimative.analytic_confidence(5.0, 1.0, is_contradicted=True) == "moderate"


# --- #3 Admiralty source grading ------------------------------------------ #

def test_admiralty_best_grade_is_one():
    assert source_grading.admiralty_weight(SourceReliability.A, InfoCredibility.C1) == 1.0


def test_admiralty_geometric_mean_and_code():
    # A (1.0) × C3 (0.6) → sqrt(0.6) ≈ 0.7746
    w = source_grading.admiralty_weight(SourceReliability.A, InfoCredibility.C3)
    assert w == pytest.approx(0.7746, abs=1e-3)
    assert source_grading.admiralty_code(SourceReliability.B, InfoCredibility.C2) == "B2"


def test_unreliable_source_drags_weight_down():
    assert source_grading.admiralty_weight(SourceReliability.E, InfoCredibility.C1) < 0.4


# --- #1 ACH scoring ------------------------------------------------------- #

def _h(i):
    return ach._Hypothesis(id=f"h{i}", text=f"Hypothesis {i}")


def _i(i, weight=1.0):
    return ach._Item(id=f"e{i}", text=f"Evidence {i}", weight=weight)


def test_ach_least_inconsistent_hypothesis_wins():
    hyps = [_h(1), _h(2)]
    items = [_i(1), _i(2)]
    # h1 is consistent with all; h2 is inconsistent with both.
    ratings = {
        ("h1", "e1"): AchConsistency.CONSISTENT,
        ("h1", "e2"): AchConsistency.CONSISTENT,
        ("h2", "e1"): AchConsistency.INCONSISTENT,
        ("h2", "e2"): AchConsistency.INCONSISTENT,
    }
    result = ach.score(hyps, items, ratings)
    assert result.most_likely_hypothesis_id == "h1"
    assert result.hypotheses[0].hypothesis_id == "h1"
    assert result.hypotheses[0].rank == 1
    assert result.hypotheses[1].inconsistency_score > 0


def test_ach_diagnosticity_zero_when_all_agree():
    hyps = [_h(1), _h(2)]
    items = [_i(1)]
    ratings = {
        ("h1", "e1"): AchConsistency.CONSISTENT,
        ("h2", "e1"): AchConsistency.CONSISTENT,
    }
    result = ach.score(hyps, items, ratings)
    assert result.items[0].diagnosticity == 0.0


def test_ach_diagnostic_item_ranks_high():
    hyps = [_h(1), _h(2)]
    items = [_i(1), _i(2)]
    ratings = {
        # e1 splits the hypotheses (diagnostic); e2 agrees (not diagnostic).
        ("h1", "e1"): AchConsistency.CONSISTENT,
        ("h2", "e1"): AchConsistency.INCONSISTENT,
        ("h1", "e2"): AchConsistency.CONSISTENT,
        ("h2", "e2"): AchConsistency.CONSISTENT,
    }
    result = ach.score(hyps, items, ratings)
    assert result.items[0].item_id == "e1"
    assert result.items[0].diagnosticity > result.items[1].diagnosticity


def test_ach_empty_is_safe():
    assert ach.score([], [], {}).most_likely_hypothesis_id is None
