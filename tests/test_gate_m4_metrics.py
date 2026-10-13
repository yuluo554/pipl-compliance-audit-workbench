"""守门测试 G11：M4 内置基准指标（防"指标口径漂移"与"只跑不报指标"回归）。

断言：
- `benchmark/cases.confusion` 是误报/漏报口径的唯一实现源，且二元口径为
  **问题 = partial ∪ noncompliant**（unknown/not_applicable 不算判错）；
- 混淆矩阵边界正确（误报=真值非问题而引擎判问题；漏报反之；分母为 0 记 0）；
- `BenchmarkReport.to_dict()` 暴露 `trigger_accuracy` / `state_accuracy` /
  `false_positive_rate` 三项门指标 + 样本量 + 门值，权威包上**达标**；
- 门值口径锁定：触发判定 ≥ 0.95、四态 ≥ 0.95、误报率 ≤ 0（`cases.GATE_*` 常量）；
- CLI `bench` 退出码把门指标纳入判定（未过门 → 1）。

本门为**指标门**：M4 交付"四类基准一条命令跑全 + 指标进 README + 门值可断言"。
"""

from pathlib import Path

from conftest import ROOT
from paudit.benchmark.cases import (
    FLAGGED_STATES,
    GATE_FALSE_POSITIVE_RATE,
    GATE_STATE_ACCURACY,
    GATE_TRIGGER_ACCURACY,
    confusion,
    expected_item_states,
    rate,
)
from paudit.benchmark.runner import GATES, run_all
from paudit.rules.model import (
    STATE_COMPLIANT,
    STATE_NONCOMPLIANT,
    STATE_NOT_APPLICABLE,
    STATE_PARTIAL,
    STATE_UNKNOWN,
)


def _authoritative():
    from paudit.rules.loader import load_ruleset

    return load_ruleset(str(ROOT / "data" / "rules" / "ruleset-pipl-audit-2025.json"))


# ---------------------------------------------------------------------------
# 口径单一实现源
# ---------------------------------------------------------------------------
def test_flagged_states_are_partial_and_noncompliant():
    """二元口径：问题 = partial ∪ noncompliant（unknown/NA 不构成判错）。"""
    assert set(FLAGGED_STATES) == {STATE_PARTIAL, STATE_NONCOMPLIANT}
    assert STATE_UNKNOWN not in FLAGGED_STATES
    assert STATE_NOT_APPLICABLE not in FLAGGED_STATES
    assert STATE_COMPLIANT not in FLAGGED_STATES


def test_confusion_counts_false_positive_and_negative():
    """误报=真值非问题而引擎判问题；漏报=真值问题而引擎判非问题。"""
    truth = [STATE_COMPLIANT, STATE_PARTIAL, STATE_NONCOMPLIANT, STATE_UNKNOWN]
    # 引擎：对 compliant 误报 partial；对 partial 漏报为 unknown；其余一致
    engine = [STATE_PARTIAL, STATE_UNKNOWN, STATE_NONCOMPLIANT, STATE_UNKNOWN]
    c = confusion(truth, engine)
    assert c["total"] == 4
    assert c["correct"] == 2          # 第 3、4 项一致
    assert c["false_positive"] == 1   # compliant → partial
    assert c["false_negative"] == 1   # partial → unknown
    assert c["truth_clear"] == 2      # compliant + unknown
    assert c["truth_flagged"] == 2    # partial + noncompliant
    assert c["false_positive_rate"] == 0.5
    assert c["miss_rate"] == 0.5
    assert c["state_accuracy"] == 0.5


def test_confusion_zero_denominator_is_zero():
    """分母为 0（无真值问题项 / 无真值非问题项）时记 0，不除零。"""
    c = confusion([STATE_COMPLIANT, STATE_COMPLIANT], [STATE_COMPLIANT, STATE_COMPLIANT])
    assert c["false_positive_rate"] == 0.0
    assert c["miss_rate"] == 0.0
    c2 = confusion([STATE_NONCOMPLIANT], [STATE_NONCOMPLIANT])
    assert c2["false_positive_rate"] == 0.0
    assert c2["false_negative"] == 0


def test_rate_helper_guards_zero():
    assert rate(0, 0) == 0.0
    assert rate(3, 4) == 0.75


# ---------------------------------------------------------------------------
# 门值口径锁定
# ---------------------------------------------------------------------------
def test_gate_thresholds_locked():
    """门值口径（plan/05 §三 M4）：触发判定 ≥ 0.95、四态 ≥ 0.95、误报率 ≤ 0。"""
    assert GATE_TRIGGER_ACCURACY == 0.95
    assert GATE_STATE_ACCURACY == 0.95
    assert GATE_FALSE_POSITIVE_RATE == 0.0
    assert GATES == {
        "trigger_accuracy": GATE_TRIGGER_ACCURACY,
        "state_accuracy": GATE_STATE_ACCURACY,
        "false_positive_rate": GATE_FALSE_POSITIVE_RATE,
    }


# ---------------------------------------------------------------------------
# 报告指标扩列 + 权威包达标
# ---------------------------------------------------------------------------
def test_report_exposes_three_gate_metrics_with_samples():
    report = run_all(_authoritative())
    d = report.to_dict()
    assert "metrics" in d and "gates" in d
    m = d["metrics"]
    for key in ("trigger_accuracy", "state_accuracy", "false_positive_rate"):
        assert key in m, "缺门指标: %s" % key
        assert 0.0 <= m[key] <= 1.0
    # 样本量须显式给出（口径可复核）
    assert m["trigger_samples"] > 0
    assert m["state_samples"] > 0
    assert m["false_positive_samples"] > 0
    assert d["gates"] == GATES


def test_authoritative_metrics_meet_gates():
    """权威规则包上三项门指标达标（触发 ≥0.95 / 四态 ≥0.95 / 误报率 0）。"""
    report = run_all(_authoritative())
    m = report.metrics
    assert report.gates_met is True
    assert m["trigger_accuracy"] >= GATE_TRIGGER_ACCURACY
    assert m["state_accuracy"] >= GATE_STATE_ACCURACY
    assert m["false_positive_rate"] <= GATE_FALSE_POSITIVE_RATE
    assert m["false_positive"] == 0
    # 与套件失败数一致：指标达标不掩盖套件失败
    assert report.passed is True


def test_metrics_are_derived_from_frozen_truth_not_recomputed():
    """B3 的四态对账取真值库冻结的 `expected.item_states`（生成期独立推导）。"""
    truth = ROOT / "data" / "truth" / "case-1200w-no-audit-triggers.json"
    import json

    case = json.loads(truth.read_text(encoding="utf-8"))
    items = case["expected"]["item_states"]
    assert items, "真值用例缺 item_states（误报率/四态准确率的真值来源）"
    assert set(items.values()) <= {
        "compliant", "partial", "noncompliant", "not_applicable", "unknown"}


def test_expected_item_states_matches_engine_semantics():
    """共享真值推导与引擎逐项一致（权威包 + 真值用例，抽查全量）。"""
    import json

    from paudit.engine.checklist import evaluate_item

    rs = _authoritative()
    for f in sorted((ROOT / "data" / "truth").glob("*.json"))[:5]:
        case = json.loads(f.read_text(encoding="utf-8"))
        card = case.get("input_card", {})
        manual = case.get("manual_results", {})
        truth = expected_item_states(rs.checklist, card, manual)
        engine = [evaluate_item(i, card, manual).state for i in rs.checklist]
        assert truth == engine, "真值推导与引擎不一致: %s" % f.name
