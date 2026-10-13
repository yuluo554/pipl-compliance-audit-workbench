"""规则包数据模型（仅标准库，dataclass）。"""

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
            source=Source.from_dict(d.get("source")),
        )


@dataclass(frozen=True)
class CheckItem:
    id: str
    category: str
    title: str
    clause: Clause
    method: str
    criteria: str = ""
    auto_field: Optional[str] = None
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
