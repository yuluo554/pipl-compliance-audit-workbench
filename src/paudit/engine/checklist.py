"""检查单引擎：四态判定 + 汇总语义。

关键语义（FR-2.5）：
- 不适用（门控不满足）记 not_applicable，不计违规、不进分母；
- 未观测（人工项未录入）记 unknown，不计违规但计入"待人工确认"；
- 无任何适用项被评 → 汇总 not_assessed，绝不输出 compliant。

auto 项判定为**数据驱动**：按规则包 `auto_mapping` 声明的"取值 → 四态"规则求值，
引擎零业务字面量；规则包未给映射时退化为旧口径（非空=compliant / 空=noncompliant）。
"""

from ..rules.model import (
    ALL_STATES,
    APPLICABLE_STATES,
    METHOD_AUTO,
    STATE_COMPLIANT,
    STATE_NONCOMPLIANT,
    STATE_NOT_APPLICABLE,
    STATE_PARTIAL,
    STATE_UNKNOWN,
    SUMMARY_COMPLIANT,
    SUMMARY_NONCOMPLIANT,
    SUMMARY_NOT_ASSESSED,
    SUMMARY_PARTIAL,
)


class ItemResult:
    def __init__(self, item, state, note=""):
        self.item = item
        self.state = state
        self.note = note

    def to_dict(self):
        return {
            "item_id": self.item.id,
            "category": self.item.category,
            "title": self.item.title,
            "state": self.state,
            "note": self.note,
            "clause": {
                "basis": self.item.clause.basis,
                "article": self.item.clause.article,
                "point": self.item.clause.point,
            },
        }


def _is_present(value):
    """非空判定：True 或非空白字符串视为"有"，None/False/空串视为"无"。"""
    return value is True or (isinstance(value, str) and bool(value.strip()))


def _gated_out(item, input_card):
    """only_if 门控：返回 True 表示不适用。"""
    gate = item.only_if
    if not gate:
        return False
    for key, allowed in gate.items():
        actual = input_card.get(key)
        if actual not in allowed:
            return True
    return False


def _map_auto(item, value):
    """按规则包 auto_mapping 判定；规则包未给映射时退化旧口径。"""
    mapping = item.auto_mapping
    if mapping is not None and not mapping.is_empty():
        state = mapping.match(value)
        if state in ALL_STATES:
            return state
    return STATE_COMPLIANT if _is_present(value) else STATE_NONCOMPLIANT


def evaluate_item(item, input_card, manual_results):
    """单检查项判定。

    - method=auto：读 input_card[auto_field]，按规则包 auto_mapping 映射为四态
      （规则包未给映射时：非空=compliant / 空=False → noncompliant）；
    - method=manual：读 manual_results[item.id]，缺失记 unknown。
    """
    if _gated_out(item, input_card):
        return ItemResult(item, STATE_NOT_APPLICABLE, "门控不满足，不适用")

    if item.method == METHOD_AUTO:
        field = item.auto_field
        if field is None or field not in input_card:
            return ItemResult(item, STATE_UNKNOWN, "自动核查字段缺失，未观测")
        val = input_card[field]
        state = _map_auto(item, val)
        return ItemResult(item, state, _AUTO_NOTES.get(state, "自动核查"))

    # manual
    rec = manual_results.get(item.id)
    if rec is None:
        return ItemResult(item, STATE_UNKNOWN, "未录入，待人工确认")
    state = rec.get("state", STATE_UNKNOWN)
    if state not in APPLICABLE_STATES + (STATE_NOT_APPLICABLE, STATE_UNKNOWN):
        state = STATE_UNKNOWN
    return ItemResult(item, state, rec.get("note", ""))


_AUTO_NOTES = {
    STATE_COMPLIANT: "自动核查通过",
    STATE_PARTIAL: "自动核查部分符合",
    STATE_NONCOMPLIANT: "自动核查未通过",
    STATE_NOT_APPLICABLE: "自动核查判定为不适用",
    STATE_UNKNOWN: "自动核查未能判定",
}


def summarize(results):
    """汇总：applicable 为空 → not_assessed。"""
    applicable = [r for r in results if r.state in APPLICABLE_STATES]
    if not applicable:
        return SUMMARY_NOT_ASSESSED
    if any(r.state == STATE_NONCOMPLIANT for r in applicable):
        return SUMMARY_NONCOMPLIANT
    if any(r.state == STATE_PARTIAL for r in applicable):
        return SUMMARY_PARTIAL
    return SUMMARY_COMPLIANT


def counts(results):
    """各状态计数（供报告与基准）。"""
    c = {s: 0 for s in (
        STATE_COMPLIANT, STATE_PARTIAL, STATE_NONCOMPLIANT,
        STATE_NOT_APPLICABLE, STATE_UNKNOWN)}
    for r in results:
        c[r.state] = c.get(r.state, 0) + 1
    c["total"] = len(results)
    return c
