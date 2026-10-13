"""门槛判定引擎（确定性内核）。

判定参数与门槛值一律从规则包读取（NFR-5：引擎源码零门槛字面量）。
比较在整数域进行，无浮点尾差。
"""

from ..rules.model import Clause

_OPS = {
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


class ThresholdResult:
    """门槛判定结论。"""

    def __init__(self, triggered, conclusions, matched):
        self.triggered = triggered          # bool：是否触发审计义务
        self.conclusions = conclusions      # 命中的结论码列表（按 severity 降序）
        self.matched = matched              # 命中的门槛规则列表

    @property
    def frequency(self):
        for t in self.matched:
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

    def to_dict(self):
        return {
            "triggered": self.triggered,
            "conclusions": list(self.conclusions),
            "frequency": self.frequency,
            "clauses": [
                {"basis": c.basis, "article": c.article, "point": c.point}
                for c in self.clauses
            ],
        }


def evaluate_thresholds(ruleset, input_card):
    """按规则包门槛规则判定；命中多个时按 severity 降序归并。"""
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

    matched.sort(key=lambda t: t.severity, reverse=True)
    conclusions, seen = [], set()
    for t in matched:
        if t.conclusion not in seen:
            seen.add(t.conclusion)
            conclusions.append(t.conclusion)

    triggered = any(t.severity > 0 for t in matched)
    return ThresholdResult(triggered=triggered, conclusions=conclusions, matched=matched)
