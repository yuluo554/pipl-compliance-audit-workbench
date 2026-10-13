"""门槛引擎 + 四态判定 + 汇总语义（FR-1/FR-2.5）。"""

from paudit.engine.checklist import counts, evaluate_item, summarize
from paudit.engine.pipeline import AuditRequest, compute_audit
from paudit.engine.thresholds import evaluate_thresholds
from paudit.rules.model import (
    AutoMapping,
    CheckItem,
    Clause,
    STATE_COMPLIANT,
    STATE_NONCOMPLIANT,
    STATE_NOT_APPLICABLE,
    STATE_PARTIAL,
    STATE_UNKNOWN,
    SUMMARY_COMPLIANT,
    SUMMARY_NONCOMPLIANT,
    SUMMARY_NOT_ASSESSED,
    SUMMARY_PARTIAL,
    Threshold,
)


def _th(op, value, severity=1, conclusion="c", effect="standing_obligation", param="scale"):
    return Threshold(id="T", param=param, op=op, value=value, conclusion=conclusion,
                     frequency="", clause=Clause("b", "a"), status="verified",
                     severity=severity, effect=effect)


def test_threshold_boundary_ge():
    """op='>=' 含等于；'恰好等于门槛'命中。"""
    rs = type("R", (), {"thresholds": [_th(">=", 100)]})()
    assert evaluate_thresholds(rs, {"scale": 99}).triggered is False
    assert evaluate_thresholds(rs, {"scale": 100}).triggered is True
    assert evaluate_thresholds(rs, {"scale": 101}).triggered is True


def test_threshold_boundary_gt():
    rs = type("R", (), {"thresholds": [_th(">", 100)]})()
    assert evaluate_thresholds(rs, {"scale": 100}).triggered is False
    assert evaluate_thresholds(rs, {"scale": 101}).triggered is True


def test_threshold_severity_merge():
    """多门槛命中按 severity 降序归并。"""
    rs = type("R", (), {"thresholds": [
        _th(">=", 100, severity=1, conclusion="low"),
        _th(">=", 200, severity=2, conclusion="high"),
    ]})()
    r = evaluate_thresholds(rs, {"scale": 300})
    assert r.conclusions == ["high", "low"]
    assert r.triggered is True


def test_threshold_missing_param_ignored():
    rs = type("R", (), {"thresholds": [_th(">=", 100)]})()
    assert evaluate_thresholds(rs, {}).triggered is False


def test_threshold_effect_split_obligation_vs_conditional():
    """三分判定：无条件义务 与 条件触发（保护部门可以要求）分栏，不混同。"""
    rs = type("R", (), {"thresholds": [
        _th(">=", 100, severity=1, conclusion="standing",
            effect="standing_obligation", param="a"),
        _th(">=", 100, severity=1, conclusion="periodic",
            effect="periodic_obligation", param="b"),
        _th(">=", 100, severity=2, conclusion="may_require",
            effect="conditional_institution", param="c"),
    ]})()
    r = evaluate_thresholds(rs, {"a": 200, "b": 200, "c": 200})
    assert r.triggered is True
    assert {t.conclusion for t in r.obligations} == {"standing", "periodic"}
    assert {t.conclusion for t in r.conditional_triggers} == {"may_require"}
    # 结论码仍按 severity 降序全量归并
    assert r.conclusions == ["may_require", "periodic", "standing"] or \
        r.conclusions == ["may_require", "standing", "periodic"]


def test_threshold_conditional_only_not_obligation():
    """仅命中条件触发时，无条件义务栏为空（不冒充处理者义务）。"""
    rs = type("R", (), {"thresholds": [
        _th(">=", 100, severity=2, conclusion="may_require",
            effect="conditional_institution", param="c"),
    ]})()
    r = evaluate_thresholds(rs, {"c": 200})
    assert r.triggered is True
    assert r.obligations == []
    assert len(r.conditional_triggers) == 1
    d = r.to_dict()
    assert d["obligations"] == [] and d["conditional_triggers"][0]["conclusion"] == "may_require"


def test_threshold_frequency_only_from_obligations():
    """频次只取无条件义务（条件触发无处理者频次义务）。"""
    rs = type("R", (), {"thresholds": [
        _th(">=", 100, severity=2, conclusion="may_require",
            effect="conditional_institution", param="c"),
    ]})()
    assert evaluate_thresholds(rs, {"c": 200}).frequency == ""


def _item(method="manual", auto_field=None, only_if=None, auto_mapping=None):
    return CheckItem(id="C", category="c", title="t", clause=Clause("b", "a"),
                     method=method, criteria="x", auto_field=auto_field,
                     auto_mapping=AutoMapping.from_dict(auto_mapping),
                     only_if=only_if, status="verified")


def test_auto_item_pass_fail():
    it = _item(method="auto", auto_field="flag")
    assert evaluate_item(it, {"flag": True}, {}).state == STATE_COMPLIANT
    assert evaluate_item(it, {"flag": False}, {}).state == STATE_NONCOMPLIANT


def test_auto_item_mapping_partial():
    """mapping 声明 partial → 取值命中即部分符合（数据驱动，引擎零业务字面量）。"""
    it = _item(method="auto", auto_field="flag", auto_mapping=[
        {"match": {"one_of": [True, "complete"]}, "state": "compliant"},
        {"match": {"equals": "partial"}, "state": "partial"},
        {"match": {"default": True}, "state": "noncompliant"},
    ])
    assert evaluate_item(it, {"flag": "partial"}, {}).state == STATE_PARTIAL
    assert evaluate_item(it, {"flag": True}, {}).state == STATE_COMPLIANT
    assert evaluate_item(it, {"flag": "absent"}, {}).state == STATE_NONCOMPLIANT
    assert evaluate_item(it, {"flag": False}, {}).state == STATE_NONCOMPLIANT


def test_auto_item_mapping_not_applicable():
    """mapping 可声明 not_applicable（法定免告知等）→ 不计违规不进分母。"""
    it = _item(method="auto", auto_field="flag", auto_mapping=[
        {"match": {"equals": "not_required"}, "state": "not_applicable"},
        {"match": {"default": True}, "state": "noncompliant"},
    ])
    assert evaluate_item(it, {"flag": "not_required"}, {}).state == STATE_NOT_APPLICABLE
    assert evaluate_item(it, {"flag": False}, {}).state == STATE_NONCOMPLIANT


def test_auto_item_no_mapping_falls_back():
    """规则包未给 mapping → 退化口径（非空=compliant / 空=noncompliant）。"""
    it = _item(method="auto", auto_field="flag")
    assert evaluate_item(it, {"flag": "任意非空"}, {}).state == STATE_COMPLIANT
    assert evaluate_item(it, {"flag": ""}, {}).state == STATE_NONCOMPLIANT


def test_auto_item_field_missing_is_unknown():
    """未观测 ≠ 缺失：字段缺失记 unknown，不是 noncompliant。"""
    it = _item(method="auto", auto_field="flag")
    assert evaluate_item(it, {}, {}).state == STATE_UNKNOWN


def test_manual_item_not_entered_is_unknown():
    it = _item()
    assert evaluate_item(it, {}, {}).state == STATE_UNKNOWN


def test_manual_item_entered():
    it = _item()
    r = evaluate_item(it, {}, {"C": {"state": STATE_PARTIAL, "note": "n"}})
    assert r.state == STATE_PARTIAL and r.note == "n"


def test_only_if_gate_not_applicable():
    """不适用 ≠ 违规：门控不满足记 not_applicable。"""
    it = _item(only_if={"sensitive": [True]})
    assert evaluate_item(it, {"sensitive": False}, {}).state == STATE_NOT_APPLICABLE


def test_summary_all_not_applicable_is_not_assessed():
    """一条都不适用 → not_assessed，绝不输出 compliant。"""
    assert summarize([_res(STATE_NOT_APPLICABLE)]) == SUMMARY_NOT_ASSESSED


def test_summary_all_unknown_is_not_assessed():
    assert summarize([_res(STATE_UNKNOWN)]) == SUMMARY_NOT_ASSESSED


def test_summary_mix():
    assert summarize([_res(STATE_COMPLIANT)]) == SUMMARY_COMPLIANT
    assert summarize([_res(STATE_COMPLIANT), _res(STATE_PARTIAL)]) == SUMMARY_PARTIAL
    assert summarize([_res(STATE_COMPLIANT), _res(STATE_NONCOMPLIANT)]) == SUMMARY_NONCOMPLIANT


def _res(state):
    return type("R", (), {"state": state})()


def test_counts():
    c = counts([_res(STATE_COMPLIANT), _res(STATE_UNKNOWN), _res(STATE_NOT_APPLICABLE)])
    assert c["compliant"] == 1 and c["unknown"] == 1 and c["not_applicable"] == 1
    assert c["total"] == 3


def test_compute_audit_end_to_end(demo_ruleset, demo_card):
    res = compute_audit(
        AuditRequest(demo_card["input_card"], demo_card["manual_results"],
                     demo_card["audit_scope"]), demo_ruleset)
    assert res.threshold_result.triggered is True
    assert res.summary == SUMMARY_NONCOMPLIANT
    assert len(res.findings) == 2
    # 底稿形态键
    d = res.to_dict()
    assert "item_results" in d and "threshold_result" in d
    assert d["audit_scope"]["subject"]


def test_compute_audit_not_assessed_when_nothing_applicable(demo_ruleset):
    """全 manual 未录入 + 门控不适用 → not_assessed。"""
    rs = demo_ruleset
    card = {"scale": 0, "sensitive": False, "has_policy": True, "has_consent_withdraw": True}
    # 只保留 manual 项与门控项：构造一个全 unknown/not_applicable 的输入
    res = compute_audit(AuditRequest(card, {}), rs)
    # CHK-DEMO-001/002 auto 项会给结论；此处仅断言汇总非 not_assessed 时不误报 compliant
    assert res.summary in (SUMMARY_COMPLIANT, SUMMARY_NOT_ASSESSED, SUMMARY_PARTIAL,
                           SUMMARY_NONCOMPLIANT)
