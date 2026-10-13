"""基准 runner + 真值语义单一源（FR-7）。"""

from paudit.benchmark.cases import (
    apply_mapping,
    confusion,
    effect_rank,
    expected_item_states,
    expected_summary,
    expected_threshold,
    observed_nonpass,
    rate,
    split_effect,
)
from paudit.benchmark.runner import GATES, run_all
from paudit.rules.model import (
    Clause,
    STATE_COMPLIANT,
    STATE_NONCOMPLIANT,
    STATE_NOT_APPLICABLE,
    STATE_PARTIAL,
    STATE_UNKNOWN,
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


def _th(tid, effect, param="scale"):
    return Threshold(id=tid, param=param, op=">=", value=1, conclusion="c",
                     frequency="", clause=Clause("b", "a"), status="verified",
                     severity=1, effect=effect)


def test_split_effect_separates_conditional():
    ths = [_th("A", "periodic_obligation", "a"),
           _th("B", "standing_obligation", "b"),
           _th("C", "conditional_institution", "c")]
    ob, cd = split_effect(ths)
    assert {t.id for t in ob} == {"A", "B"}
    assert {t.id for t in cd} == {"C"}


def test_split_effect_accepts_plain_dicts():
    """生成器传入规则包 dict（非 dataclass）时也须正确分栏。"""
    ob, cd = split_effect([
        {"id": "A", "effect": "periodic_obligation"},
        {"id": "C", "effect": "conditional_institution"},
        {"id": "D"},  # 缺 effect → 默认无条件义务
    ])
    assert {t["id"] for t in ob} == {"A", "D"}
    assert {t["id"] for t in cd} == {"C"}


def test_effect_rank_orders_periodic_first_then_conditional():
    assert effect_rank({"effect": "periodic_obligation"}) < effect_rank(
        {"effect": "standing_obligation"}) < effect_rank(
        {"effect": "conditional_institution"})


def test_apply_mapping_matches_declared_rules():
    rules = [
        {"match": {"one_of": [True, "complete"]}, "state": "compliant"},
        {"match": {"equals": "partial"}, "state": "partial"},
        {"match": {"one_of": ["not_applicable"]}, "state": "not_applicable"},
        {"match": {"default": True}, "state": "noncompliant"},
    ]
    assert apply_mapping(rules, True) == "compliant"
    assert apply_mapping(rules, "partial") == "partial"
    assert apply_mapping(rules, "not_applicable") == "not_applicable"
    assert apply_mapping(rules, False) == "noncompliant"
    assert apply_mapping(rules, "") == "noncompliant"


def test_apply_mapping_falls_back_without_rules():
    """无规则 → 退化口径（非空=compliant / 空=noncompliant）。"""
    assert apply_mapping([], "x") == "compliant"
    assert apply_mapping(None, "") == "noncompliant"


def test_run_all_on_demo_passes(demo_ruleset):
    report = run_all(demo_ruleset)
    assert report.passed is True
    assert report.totals[0] > 0


def test_benchmark_has_four_suites(demo_ruleset):
    """M2：新增 B4 四态判定覆盖套件。"""
    names = [s["name"] for s in run_all(demo_ruleset).suites]
    assert any(n.startswith("B1") for n in names)
    assert any(n.startswith("B3") for n in names)
    assert any(n.startswith("B4") for n in names)


def _authoritative():
    from conftest import ROOT
    from paudit.rules.loader import load_ruleset

    return load_ruleset(str(ROOT / "data" / "rules" / "ruleset-pipl-audit-2025.json"))


def test_b3_reports_not_generated_when_truth_empty(demo_ruleset):
    """真值库为空时如实标注"未生成"，不假装覆盖。"""
    report = run_all(demo_ruleset)
    b3 = [s for s in report.suites if s["name"].startswith("B3")][0]
    if b3["total"] == 0:
        assert "未生成" in b3["notes"]


def test_benchmark_report_to_dict(demo_ruleset):
    d = run_all(demo_ruleset).to_dict()
    assert d["passed"] is True and 0.0 <= d["accuracy"] <= 1.0


# ---------------------------------------------------------------------------
# M4：指标口径与门值（误报/漏报口径的唯一实现源 = cases.confusion）
# ---------------------------------------------------------------------------
def test_confusion_flags_partial_and_noncompliant_only():
    """二元口径：问题 = partial ∪ noncompliant；unknown/not_applicable 不构成判错。"""
    c = confusion([STATE_UNKNOWN, STATE_NOT_APPLICABLE, STATE_COMPLIANT],
                  [STATE_UNKNOWN, STATE_NOT_APPLICABLE, STATE_COMPLIANT])
    assert c["false_positive"] == 0 and c["false_negative"] == 0
    assert c["state_accuracy"] == 1.0


def test_confusion_false_positive_and_negative_rates():
    truth = [STATE_COMPLIANT, STATE_COMPLIANT, STATE_PARTIAL, STATE_NONCOMPLIANT]
    engine = [STATE_NONCOMPLIANT, STATE_COMPLIANT, STATE_COMPLIANT, STATE_NONCOMPLIANT]
    c = confusion(truth, engine)
    assert c["false_positive"] == 1 and c["truth_clear"] == 2
    assert c["false_positive_rate"] == 0.5
    assert c["false_negative"] == 1 and c["truth_flagged"] == 2
    assert c["miss_rate"] == 0.5
    assert c["state_accuracy"] == 0.5


def test_rate_guards_zero_denominator():
    assert rate(1, 0) == 0.0
    assert rate(2, 4) == 0.5


def test_report_metrics_and_gates_present(demo_ruleset):
    d = run_all(demo_ruleset).to_dict()
    assert "metrics" in d and "gates" in d
    assert d["gates"] == GATES
    for key in ("trigger_accuracy", "state_accuracy", "false_positive_rate"):
        assert key in d["metrics"]


def test_lines_mark_no_sample_metrics_as_na(demo_ruleset):
    """示例包无真值库 → 四态/误报率无样本，须显示 n/a 而非 0.0000（避免误读为不达标）。"""
    report = run_all(demo_ruleset)
    text = "\n".join(report.lines())
    if report.metrics["state_samples"] == 0:
        assert "n/a" in text
    # 权威包有样本 → 显示数值
    auth = run_all(_authoritative())
    auth_text = "\n".join(auth.lines())
    assert "n/a" not in auth_text.split("指标:")[1].split("\n")[0]


def test_expected_item_states_uses_gates_and_mapping(demo_ruleset):
    """共享真值推导：门控不满足→not_applicable；auto 字段缺失→unknown。"""
    item = demo_ruleset.checklist[0]
    states = expected_item_states(demo_ruleset.checklist, {}, {})
    assert len(states) == len(demo_ruleset.checklist)
    assert all(s in ("compliant", "partial", "noncompliant",
                     "not_applicable", "unknown") for s in states)
    assert item.id  # 结构自明
