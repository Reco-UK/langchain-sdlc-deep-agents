"""Unit tests for app.agent.conditions."""

from __future__ import annotations

from app.agent.conditions import (
    MAX_REVIEW_ITERATIONS,
    QUALITY_THRESHOLD,
    check_approval,
    quality_threshold,
)


def test_quality_threshold_approves_high_score() -> None:
    state = {"review_report": {"score": QUALITY_THRESHOLD}, "iteration_count": 0}
    assert quality_threshold(state) == "approved"  # type: ignore[arg-type]


def test_quality_threshold_sends_low_score_back_to_coder() -> None:
    state = {"review_report": {"score": 10}, "iteration_count": 0}
    assert quality_threshold(state) == "needs_work"  # type: ignore[arg-type]


def test_quality_threshold_escalates_after_max_iterations() -> None:
    state = {"review_report": {"score": 10}, "iteration_count": MAX_REVIEW_ITERATIONS}
    assert quality_threshold(state) == "reject"  # type: ignore[arg-type]


def test_quality_threshold_defaults_missing_report_to_zero() -> None:
    assert quality_threshold({}) == "needs_work"  # type: ignore[arg-type]


def test_check_approval_accepts_case_insensitive() -> None:
    assert check_approval({"human_decision": "Approved"}) == "approved"  # type: ignore[arg-type]


def test_check_approval_rejects_missing_decision() -> None:
    assert check_approval({}) == "rejected"  # type: ignore[arg-type]
