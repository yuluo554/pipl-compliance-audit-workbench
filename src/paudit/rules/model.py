"""规则包数据模型（仅标准库，dataclass）。

四态判定与门槛判定的**业务语义一律来自规则包数据**（本模块只承载词汇表，
不含任何条款/门槛内容）：`auto_mapping` 的取值→状态映射、`trigger_type` 的
义务类型，均由规则包声明，引擎按声明求值（NFR-5）。
"""

from dataclasses import dataclass, field
from typing import List, Optional

STATUS_VERIFIED = "verified"
STATUS_PENDING = "pending"

# 检查项核查方式
METHOD_AUTO = "auto"
METHOD_MANUAL = "manual"

# 单项判定状态
STATE_COMPLIANT = "compliant"
STATE_PARTIAL = "partial"
STATE_NONCOMPLIANT = "noncompliant"
STATE_NOT_APPLICABLE = "not_applicable"
STATE_UNKNOWN = "unknown"

# 汇总状态
SUMMARY_COMPLIANT = "compliant"
SUMMARY_PARTIAL = "partial"
SUMMARY_NONCOMPLIANT = "noncompliant"
SUMMARY_NOT_ASSESSED = "not_assessed"

# 适用项集合（进分母的状态）
APPLICABLE_STATES = (STATE_COMPLIANT, STATE_PARTIAL, STATE_NONCOMPLIANT)

# 单项全部合法状态（人工录入校验用）
ALL_STATES = APPLICABLE_STATES + (STATE_NOT_APPLICABLE, STATE_UNKNOWN)

# 门槛义务类型（effect）——引擎按声明分栏呈现，不含条款内容
#   periodic_obligation      周期性义务（处理者无条件，带频次）
#   standing_obligation      持续性义务（处理者无条件，无频次）
#   conditional_institution  条件触发（保护部门"可以要求"，非处理者无条件义务）
EFFECT_PERIODIC_OBLIGATION = "periodic_obligation"
EFFECT_STANDING_OBLIGATION = "standing_obligation"
EFFECT_CONDITIONAL_INSTITUTION = "conditional_institution"

# auto_mapping 匹配词表（结构性词，非政策字面量）：
#   {"equals": v} / {"one_of": [v...]} / {"empty": bool} / {"nonempty": bool}
MATCH_EQUALS = "equals"
MATCH_ONE_OF = "one_of"
MATCH_EMPTY = "empty"
MATCH_NONEMPTY = "nonempty"


@dataclass(frozen=True)
class Source:
    channel: str = ""
    url: str = ""
    checked_at: str = ""

    @classmethod
    def from_dict(cls, d):
        d = d or {}
        return cls(
            channel=d.get("channel", ""),
            url=d.get("url", ""),
            checked_at=d.get("checked_at", ""),
        )

    def is_attributed(self):
        """出处是否可用：channel 与 checked_at 必填，url 可空（标准全文公开页需登录）。"""
        return bool(self.channel and self.checked_at)


@dataclass(frozen=True)
class Clause:
    basis: str
    article: str
    point: str = ""

    @classmethod
    def from_dict(cls, d):
        d = d or {}
        return cls(
            basis=d.get("basis", ""),
            article=d.get("article", ""),
            point=d.get("point", ""),
        )

    def label(self):
        return "%s %s" % (self.basis, self.article)


@dataclass(frozen=True)
class Basis:
    code: str
    title: str
    effective_date: Optional[str] = None
    status: str = STATUS_PENDING
    source: Source = field(default_factory=Source)

    @classmethod
    def from_dict(cls, d):
        return cls(
            code=d.get("code", ""),
            title=d.get("title", ""),
            effective_date=d.get("effective_date"),
            status=d.get("status", STATUS_PENDING),
            source=Source.from_dict(d.get("source")),
        )


@dataclass(frozen=True)
class AutoMapping:
    """auto 项的"取值 → 四态"映射规则（数据驱动，引擎零业务字面量）。

    rules 为有序列表，每条 `{"match": {...}, "state": "<四态>"}`；按序取**首个命中**。
    末尾可挂 `{"match": {"default": true}, "state": "..."}` 作兜底。
    未给规则（空）时引擎退化为旧口径（非空=True → compliant / 否则 noncompliant），
    以兼容未细化的规则包（示例包）。
    """

    rules: List[dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d):
        if not d:
            return cls(rules=[])
        if isinstance(d, list):
            return cls(rules=list(d))
        return cls(rules=list(d.get("rules", [])))

    def is_empty(self):
        return not self.rules

    def match(self, value):
        """返回首个命中规则的 state；无命中返回 None。"""
        for rule in self.rules:
            m = rule.get("match", {})
            if _match_rule(m, value):
                return rule.get("state")
        return None

    def to_dict(self):
        return {"rules": [dict(r) for r in self.rules]}


def _match_rule(m, value):
    if m.get("default"):
        return True
    if MATCH_EMPTY in m:
        empty = value is None or value is False or (
            isinstance(value, str) and not value.strip())
        if bool(m[MATCH_EMPTY]) != empty:
            return False
    if MATCH_NONEMPTY in m:
        empty = value is None or value is False or (
            isinstance(value, str) and not value.strip())
        if bool(m[MATCH_NONEMPTY]) == empty:
            return False
    if MATCH_EQUALS in m and value != m[MATCH_EQUALS]:
        return False
    if MATCH_ONE_OF in m and value not in m[MATCH_ONE_OF]:
        return False
    return True


@dataclass(frozen=True)
class Threshold:
    id: str
    param: str
    op: str
    value: int
    conclusion: str
    frequency: str
    clause: Clause
    status: str
    severity: int = 0
    effect: str = EFFECT_STANDING_OBLIGATION
    source: Source = field(default_factory=Source)

    @classmethod
    def from_dict(cls, d):
        return cls(
            id=d["id"],
            param=d["param"],
            op=d["op"],
            value=d["value"],
            conclusion=d["conclusion"],
            frequency=d.get("frequency", ""),
            clause=Clause.from_dict(d.get("clause")),
            status=d.get("status", STATUS_PENDING),
            severity=d.get("severity", 0),
            effect=d.get("effect", EFFECT_STANDING_OBLIGATION),
            source=Source.from_dict(d.get("source")),
        )

    def is_conditional(self):
        """是否为"条件触发"（保护部门可以要求，非处理者无条件义务）。"""
        return self.effect == EFFECT_CONDITIONAL_INSTITUTION


@dataclass(frozen=True)
class CheckItem:
    id: str
    category: str
    title: str
    clause: Clause
    method: str
    criteria: str = ""
    auto_field: Optional[str] = None
    auto_mapping: AutoMapping = field(default_factory=AutoMapping)
    evidence_required: bool = True
    only_if: Optional[dict] = None
    status: str = STATUS_PENDING
    source: Source = field(default_factory=Source)

    @classmethod
    def from_dict(cls, d):
        return cls(
            id=d["id"],
            category=d.get("category", ""),
            title=d.get("title", ""),
            clause=Clause.from_dict(d.get("clause")),
            method=d.get("method", METHOD_MANUAL),
            criteria=d.get("criteria", ""),
            auto_field=d.get("auto_field"),
            auto_mapping=AutoMapping.from_dict(d.get("auto_mapping")),
            evidence_required=d.get("evidence_required", True),
            only_if=d.get("only_if"),
            status=d.get("status", STATUS_PENDING),
            source=Source.from_dict(d.get("source")),
        )


@dataclass(frozen=True)
class Ruleset:
    schema_version: str
    ruleset_id: str
    version: str
    generated_at: str
    basis: List[Basis]
    thresholds: List[Threshold]
    checklist: List[CheckItem]
    path: Optional[str] = None

    @classmethod
    def from_dict(cls, d, path=None):
        return cls(
            schema_version=d.get("schema_version", ""),
            ruleset_id=d.get("ruleset_id", ""),
            version=d.get("version", ""),
            generated_at=d.get("generated_at", ""),
            basis=[Basis.from_dict(x) for x in d.get("basis", [])],
            thresholds=[Threshold.from_dict(x) for x in d.get("thresholds", [])],
            checklist=[CheckItem.from_dict(x) for x in d.get("checklist", [])],
            path=str(path) if path else None,
        )

    def pending_entries(self):
        """列出 status != verified 的条目（门槛 + 检查项）。"""
        out = []
        for t in self.thresholds:
            if t.status != STATUS_VERIFIED:
                out.append("threshold:%s" % t.id)
        for c in self.checklist:
            if c.status != STATUS_VERIFIED:
                out.append("checklist:%s" % c.id)
        return out

    def unattributed_entries(self):
        """列出 status=verified 但缺出处（channel/checked_at 为空）的条目。

        "已核对"必须可追溯：缺出处的 verified 条目视为未核对，不得进入判定路径。
        """
        out = []
        for b in self.basis:
            if b.status == STATUS_VERIFIED and not b.source.is_attributed():
                out.append("basis:%s" % b.code)
        for t in self.thresholds:
            if t.status == STATUS_VERIFIED and not t.source.is_attributed():
                out.append("threshold:%s" % t.id)
        for c in self.checklist:
            if c.status == STATUS_VERIFIED and not c.source.is_attributed():
                out.append("checklist:%s" % c.id)
        return out
