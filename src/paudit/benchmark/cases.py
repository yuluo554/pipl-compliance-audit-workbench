"""基准真值语义的单一实现源（测试与基准共用，防双口径漂移）。

- `expected_threshold`：由门槛规则本身推导边界期望（不硬编码门槛数值）；
- `expected_summary`：由单项状态集推导汇总期望（与引擎 summarize 同语义，独立实现）；
- `observed_nonpass`：取"全部非 pass 状态集"用于对账。
"""

from ..rules.model import (
    APPLICABLE_STATES,
    STATE_COMPLIANT,
    STATE_NONCOMPLIANT,
    STATE_PARTIAL,
    SUMMARY_COMPLIANT,
    SUMMARY_NONCOMPLIANT,
    SUMMARY_NOT_ASSESSED,
    SUMMARY_PARTIAL,
)

# 非 pass（"未通过"）状态集合 = fail ∪ unknown（不含 not_applicable）
NON_PASS_STATES = (STATE_PARTIAL, STATE_NONCOMPLIANT)


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


def expected_threshold(threshold, actual):
    """单条门槛在给定输入下的期望命中与否。"""
    return apply_op(threshold.op, actual, threshold.value)


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
