"""基准 runner + 真值语义单一源（FR-7）。"""

from paudit.benchmark.cases import expected_summary, expected_threshold, observed_nonpass
from paudit.benchmark.runner import run_all
from paudit.rules.model import (
    Clause,
    STATE_NONCOMPLIANT,
    STATE_NOT_APPLICABLE,
    STATE_PARTIAL,
    SUMMARY_NOT_ASSESSED,
    SUMMARY_PARTIAL,
    Threshold,
)


def test_expected_summary_matches_engine_semantics():
    assert expected_summary([STATE_NOT_APPLICABLE]) == SUMMARY_NOT_ASSESSED
    assert expected_summary([STATE_PARTIAL]) == SUMMARY_PARTIAL


def test_observed_nonpass_excludes_not_applicable():
    """对账口径：非 pass = fail ∪ unknown，不含 not_applicable。"""
    assert observed_nonpass([STATE_PARTIAL, STATE_NOT_APPLICABLE]) == [STATE_PARTIAL]
    assert observed_nonpass([STATE_NONCOMPLIANT]) == [STATE_NONCOMPLIANT]


def test_expected_threshold_boundary():
    th = Threshold(id="T", param="scale", op=">=", value=100, conclusion="c",
                   frequency="", clause=Clause("b", "a"), status="verified", severity=1)
    assert expected_threshold(th, 99) is False
    assert expected_threshold(th, 100) is True


def test_run_all_on_demo_passes(demo_ruleset):
    report = run_all(demo_ruleset)
    assert report.passed is True
    assert report.totals[0] > 0


def test_b3_reports_not_generated_when_truth_empty(demo_ruleset):
    """真值库为空时如实标注"未生成"，不假装覆盖。"""
    report = run_all(demo_ruleset)
    b3 = [s for s in report.suites if s["name"].startswith("B3")][0]
    if b3["total"] == 0:
        assert "未生成" in b3["notes"]


def test_benchmark_report_to_dict(demo_ruleset):
    d = run_all(demo_ruleset).to_dict()
    assert d["passed"] is True and 0.0 <= d["accuracy"] <= 1.0
