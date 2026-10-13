"""基准真值语义的单一实现源（测试与基准共用，防双口径漂移）。

- `apply_op`：门槛算子求值（与引擎 `thresholds._OPS` 互验的独立实现）；
- `apply_mapping`：auto 项"取值 → 四态"求值（与引擎 `checklist._map_auto` 互验的独立实现）；
- `expected_threshold`：由门槛规则本身推导边界期望（不硬编码门槛数值）；
- `split_effect`：按门槛义务类型分栏（与引擎 `ThresholdResult` 互验）；
- `expected_summary`：由单项状态集推导汇总期望（与引擎 summarize 同语义，独立实现）；
- `observed_nonpass`：取"全部非 pass 状态集"用于对账；
- `expected_item_states`：逐检查项四态真值推导（与引擎 `evaluate_item` 互验的独立实现，
  供真值库生成器与基准共用——真值库 `expected.item_states` 即由此产出）；
- `confusion`：真值 vs 引擎的混淆矩阵与派生率（**误报率口径的唯一实现源**）。
"""

from ..rules.model import (
    ALL_STATES,
    APPLICABLE_STATES,
    EFFECT_CONDITIONAL_INSTITUTION,
    EFFECT_PERIODIC_OBLIGATION,
    EFFECT_STANDING_OBLIGATION,
    METHOD_AUTO,
    METHOD_MANUAL,
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

# 非 pass（"未通过"）状态集合 = fail ∪ unknown（不含 not_applicable）
NON_PASS_STATES = (STATE_PARTIAL, STATE_NONCOMPLIANT)

# "判为问题"的二元口径：问题 = partial ∪ noncompliant（unknown/not_applicable 不构成判错）。
# 误报率/漏报率一律在此口径下计算（与 NON_PASS_STATES 同集，语义单一源）。
FLAGGED_STATES = (STATE_PARTIAL, STATE_NONCOMPLIANT)

# 指标门值（plan/05 §三 M4）：触发判定准确率、四态准确率、误报率上限。
# 仅门槛值（非政策字面量），供测试与 README 口径对齐。
GATE_TRIGGER_ACCURACY = 0.95
GATE_STATE_ACCURACY = 0.95
GATE_FALSE_POSITIVE_RATE = 0.0


def apply_op(op, actual, value):
    """门槛算子求值（基准独立实现，与引擎 thresholds._OPS 互验）。"""
    return {
        ">": actual > value,
        ">=": actual >= value,
        "<": actual < value,
        "<=": actual <= value,
        "==": actual == value,
        "!=": actual != value,
    }[op]


def _is_empty(value):
    return value is None or value is False or (
        isinstance(value, str) and not value.strip())


def _rule_hits(match, value):
    """单条 match 子句命中判定（独立实现，词表与模型一致）。"""
    if match.get("default"):
        return True
    if "empty" in match and bool(match["empty"]) != _is_empty(value):
        return False
    if "nonempty" in match and bool(match["nonempty"]) == _is_empty(value):
        return False
    if "equals" in match and value != match["equals"]:
        return False
    if "one_of" in match and value not in match["one_of"]:
        return False
    return True


def apply_mapping(rules, value, fallback_compliant=STATE_COMPLIANT,
                  fallback_noncompliant=STATE_NONCOMPLIANT):
    """按规则表求四态（独立实现）；无规则/无命中 → 退化口径（非空=compliant）。"""
    for rule in rules or []:
        if _rule_hits(rule.get("match", {}), value):
            state = rule.get("state")
            if state in ALL_STATES:
                return state
    return fallback_compliant if not _is_empty(value) else fallback_noncompliant


def expected_threshold(threshold, actual):
    """单条门槛在给定输入下的期望命中与否。"""
    return apply_op(threshold.op, actual, threshold.value)


def _effect_of(t):
    """读取门槛义务类型：兼容 dataclass 对象与规则包 dict。"""
    if isinstance(t, dict):
        return t.get("effect", EFFECT_STANDING_OBLIGATION)
    return t.effect


def effect_rank(t):
    """分栏内排序序（与引擎 thresholds._effect_rank 同序）：周期性 < 持续性 < 条件触发。"""
    effect = _effect_of(t)
    if effect == EFFECT_PERIODIC_OBLIGATION:
        return 0
    if effect == EFFECT_STANDING_OBLIGATION:
        return 1
    if effect == EFFECT_CONDITIONAL_INSTITUTION:
        return 2
    return 3


def split_effect(thresholds):
    """按义务类型分栏：无条件义务（周期性 + 持续性）/ 条件触发。"""
    unconditional = (EFFECT_PERIODIC_OBLIGATION, EFFECT_STANDING_OBLIGATION)
    obligations = [t for t in thresholds if _effect_of(t) in unconditional]
    conditional = [t for t in thresholds if _effect_of(t) not in unconditional]
    return obligations, conditional


def expected_summary(states):
    """由单项状态集推导汇总（独立实现，与引擎 summarize 互验）。"""
    applicable = [s for s in states if s in APPLICABLE_STATES]
    if not applicable:
        return SUMMARY_NOT_ASSESSED
    if any(s == STATE_NONCOMPLIANT for s in applicable):
        return SUMMARY_NONCOMPLIANT
    if any(s == STATE_PARTIAL for s in applicable):
        return SUMMARY_PARTIAL
    return SUMMARY_COMPLIANT


def observed_nonpass(states):
    """对账口径：全部非 pass 状态集（不含 not_applicable / compliant）。"""
    return sorted(s for s in states if s in NON_PASS_STATES)


def _field(item, name, default=None):
    """兼容两种检查项载体：CheckItem dataclass（引擎/基准）与规则包原生 dict（生成器）。"""
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _auto_rules(item):
    """取 auto 映射规则列表（dict 载体为原生 list；dataclass 载体为 AutoMapping.rules）。"""
    if isinstance(item, dict):
        return item.get("auto_mapping") or []
    mapping = getattr(item, "auto_mapping", None)
    return mapping.to_dict().get("rules") if mapping else []


def expected_item_state(item, input_card, manual_results):
    """独立推导单检查项四态真值（与引擎 `evaluate_item` 互验的独立实现）。

    判定序与引擎一致：only_if 门控 → method=auto（读字段按映射）→ manual（读录入）。
    真值库生成器与基准共用本函数，确保"生成的真值"与"对账用的真值"同源。
    """
    gate = _field(item, "only_if")
    if gate:
        for key, allowed in gate.items():
            if input_card.get(key) not in allowed:
                return STATE_NOT_APPLICABLE
    if _field(item, "method", METHOD_MANUAL) == METHOD_AUTO:
        field = _field(item, "auto_field")
        if field is None or field not in input_card:
            return STATE_UNKNOWN
        return apply_mapping(_auto_rules(item), input_card[field])
    rec = manual_results.get(_field(item, "id"))
    if rec is None:
        return STATE_UNKNOWN
    state = rec.get("state", STATE_UNKNOWN)
    return state if state in ALL_STATES else STATE_UNKNOWN


def expected_item_states(checklist, input_card, manual_results):
    """逐检查项四态真值（有序，与 checklist 同序）。"""
    return [expected_item_state(i, input_card, manual_results) for i in checklist]


def rate(num, den):
    """比率（分母为 0 时返回 0.0，避免除零与 NaN）。"""
    return (num / den) if den else 0.0


def confusion(truth_states, engine_states):
    """真值 vs 引擎的逐项混淆矩阵与派生率（**误报率口径的唯一实现源**）。

    二元口径（见 `FLAGGED_STATES`）：**问题 = partial ∪ noncompliant**；
    compliant / not_applicable / unknown 均视为"非问题"（不构成判错）。
    - **误报 FP**：真值非问题而引擎判问题（引擎多报）；
    - **漏报 FN**：真值为问题而引擎判非问题（引擎漏报）；
    - 逐项四态一致数 → `state_accuracy`（四态准确率）。
    误报率 = FP / 真值非问题项数；漏报率 = FN / 真值问题项数（分母为 0 时记 0）。
    """
    total = correct = fp = fn = tp = tn = 0
    for truth, engine in zip(truth_states, engine_states):
        total += 1
        if truth == engine:
            correct += 1
        t_flag = truth in FLAGGED_STATES
        e_flag = engine in FLAGGED_STATES
        if t_flag and e_flag:
            tp += 1
        elif not t_flag and not e_flag:
            tn += 1
        elif e_flag:
            fp += 1
        else:
            fn += 1
    truth_flagged, truth_clear = tp + fn, tn + fp
    return {
        "total": total,
        "correct": correct,
        "state_accuracy": rate(correct, total),
        "truth_flagged": truth_flagged,
        "truth_clear": truth_clear,
        "true_positive": tp,
        "true_negative": tn,
        "false_positive": fp,
        "false_negative": fn,
        "false_positive_rate": rate(fp, truth_clear),
        "miss_rate": rate(fn, truth_flagged),
    }
