"""Unit tests for app.agent.nodes.parse_review_report."""

from __future__ import annotations

from app.agent.nodes import parse_review_report

SAMPLE_REPORT = """
Score: 85
Summary: Clean implementation, matches the plan.
Issues:
- Missing a docstring on `fetch_issue_details`
- No test for the empty-input case
Security Notes: No critical vulnerabilities found.
"""


def test_parse_review_report_extracts_all_fields() -> None:
    report = parse_review_report(SAMPLE_REPORT)
    assert report["score"] == 85
    assert "Clean implementation" in report["summary"]
    assert len(report["issues"]) == 2
    assert report["security_notes"] == "No critical vulnerabilities found."


def test_parse_review_report_treats_none_as_no_issues() -> None:
    text = "Score: 90\nSummary: Great.\nIssues:\n- None\nSecurity Notes: None found."
    report = parse_review_report(text)
    assert report["issues"] == []


def test_parse_review_report_defaults_when_unparseable() -> None:
    report = parse_review_report("The model said something unexpected.")
    assert report["score"] == 0
    assert report["summary"] == ""
