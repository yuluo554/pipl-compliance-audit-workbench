"""门槛判定引擎（确定性内核）。

判定参数与门槛值一律从规则包读取（NFR-5：引擎源码零门槛字面量）。
比较在整数域进行，无浮点尾差。

三分判定（M2，FR-1.2）：按规则包声明的 `effect` 把命中的门槛分栏——
- **无条件义务**（处理者自身的法定义务）：周期性义务（带频次）/ 持续性义务；
- **条件触发**（保护部门"可以要求"，非处理者无条件义务）：如委托专业机构。
两栏分开呈现，结论不混同；`triggered` 仅表示命中任一门槛。
"""

from ..rules.model import (
    EFFECT_CONDITIONAL_INSTITUTION,
    EFFECT_PERIODIC_OBLIGATION,
    EFFECT_STANDING_OBLIGATION,
)

_OPS = {
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


class ThresholdResult:
    """门槛判定结论。

    - `triggered`：是否命中任一门槛（含条件触发）；
    - `obligations`：命中的**无条件义务**（处理者自身义务，按 severity 降序）；
    - `conditional_triggers`：命中的**条件触发**（保护部门可以要求）；
    - `conclusions`：全部门槛结论码（去重保序，按 severity 降序）。
    """

    def __init__(self, triggered, conclusions, matched):
        self.triggered = triggered
        self.conclusions = conclusions
        self.matched = matched

    @property
    def obligations(self):
        return [t for t in self.matched if not t.is_conditional()]

    @property
    def conditional_triggers(self):
        return [t for t in self.matched if t.is_conditional()]

    @property
    def frequency(self):
        for t in self.obligations:
            if t.frequency:
                return t.frequency
        return ""

    @property
    def clauses(self):
        out, seen = [], set()
        for t in self.matched:
            key = (t.clause.basis, t.clause.article)
            if key not in seen:
                seen.add(key)
                out.append(t.clause)
        return out

    def _entries(self, thresholds):
        return [{
            "threshold_id": t.id,
            "conclusion": t.conclusion,
            "frequency": t.frequency,
            "clause": {"basis": t.clause.basis, "article": t.clause.article,
                       "point": t.clause.point},
        } for t in thresholds]

    def to_dict(self):
        return {
            "triggered": self.triggered,
            "conclusions": list(self.conclusions),
            "frequency": self.frequency,
            "obligations": self._entries(self.obligations),
            "conditional_triggers": self._entries(self.conditional_triggers),
            "clauses": [
                {"basis": c.basis, "article": c.article, "point": c.point}
                for c in self.clauses
            ],
        }


def _effect_rank(t):
    """分栏内排序序：周期性义务优先于持续性义务。"""
    if t.effect == EFFECT_PERIODIC_OBLIGATION:
        return 0
    if t.effect == EFFECT_STANDING_OBLIGATION:
        return 1
    if t.effect == EFFECT_CONDITIONAL_INSTITUTION:
        return 2
    return 3


def evaluate_thresholds(ruleset, input_card):
    """按规则包门槛规则判定；命中多个时按 severity 降序归并（同级按义务类型序）。"""
    matched = []
    for th in ruleset.thresholds:
        if th.param not in input_card:
            continue
        actual = input_card[th.param]
        op = _OPS.get(th.op)
        if op is None:
            continue
        try:
            hit = op(actual, th.value)
        except TypeError:
            continue
        if hit:
            matched.append(th)

    matched.sort(key=lambda t: (-t.severity, _effect_rank(t)))
    conclusions, seen = [], set()
    for t in matched:
        if t.conclusion not in seen:
            seen.add(t.conclusion)
            conclusions.append(t.conclusion)

    triggered = any(t.severity > 0 for t in matched)
    return ThresholdResult(triggered=triggered, conclusions=conclusions, matched=matched)
