"""编排层：CLI 与 GUI 共用的唯一审计编排源。

AuditRequest（参数卡 + 人工录入）→ compute_audit() → AuditResult。
`AuditResult.to_dict()` 直接产出**底稿形态**（draft），供报告渲染/证据挂载/底稿导出复用，
避免"结论结构"与"底稿结构"两套口径漂移。表现层零判定逻辑。

底稿自足性（M3）：底稿保存 `input_card` + `manual_results` + `ruleset_id`，
故可离线**重算复核**（`evidence.verify_draft_consistency`）——"导入底稿重算结论 == 导出前结论"。
"""

from .. import DISCLAIMER
from ..evidence import DRAFT_SCHEMA_VERSION
from ..rules.model import STATE_NONCOMPLIANT, STATE_PARTIAL
from .checklist import ItemResult, counts, evaluate_item, summarize
from .thresholds import evaluate_thresholds

# 严重度分级（分级标准挂条款依据；数值为工具内部严重度序，非政策数值）
RISK_HIGH = "high"
RISK_MEDIUM = "medium"
RISK_LOW = "low"
RISK_ADVISORY = "advisory"

_STATE_TO_RISK = {
    STATE_NONCOMPLIANT: RISK_HIGH,
    STATE_PARTIAL: RISK_MEDIUM,
}


class AuditRequest:
    def __init__(self, input_card, manual_results=None, audit_scope=None):
        self.input_card = input_card or {}
        self.manual_results = manual_results or {}
        self.audit_scope = audit_scope or {}


class AuditResult:
    def __init__(self, ruleset, threshold_result, item_results, summary, finding_list,
                 input_card=None, audit_scope=None, manual_results=None):
        self.ruleset = ruleset
        self.threshold_result = threshold_result
        self.item_results = item_results
        self.summary = summary
        self.findings = finding_list
        self.counts = counts(item_results)
        self.input_card = input_card or {}
        self.audit_scope = audit_scope or {}
        self.manual_results = manual_results or {}

    def to_dict(self):
        """产出底稿形态（单一结构源）。"""
        return {
            "schema_version": DRAFT_SCHEMA_VERSION,
            "ruleset_id": self.ruleset.ruleset_id,
            "ruleset_version": self.ruleset.version,
            "generated_at": self.ruleset.generated_at,
            "audit_scope": dict(self.audit_scope),
            "input_card": dict(self.input_card),
            "manual_results": dict(self.manual_results),
            "threshold_result": self.threshold_result.to_dict(),
            "summary": self.summary,
            "counts": self.counts,
            "item_results": [r.to_dict() for r in self.item_results],
            "findings": self.findings,
            "disclaimer": DISCLAIMER,
        }


def compute_audit(request, ruleset):
    """唯一编排：门槛判定 → 检查单评估 → 分级汇总。"""
    thr = evaluate_thresholds(ruleset, request.input_card)
    items = [
        evaluate_item(item, request.input_card, request.manual_results)
        for item in ruleset.checklist
    ]
    summary = summarize(items)
    findings = _build_findings(items)
    return AuditResult(ruleset, thr, items, summary, findings,
                       input_card=request.input_card, audit_scope=request.audit_scope,
                       manual_results=request.manual_results)


def _build_findings(items):
    out = []
    n = 0
    for r in items:
        risk = _STATE_TO_RISK.get(r.state)
        if not risk:
            continue
        n += 1
        out.append({
            "finding_id": "F-%03d" % n,
            "item_id": r.item.id,
            "title": r.item.title,
            "risk": risk,
            "clause": {
                "basis": r.item.clause.basis,
                "article": r.item.clause.article,
                "point": r.item.clause.point,
            },
            "recommendation": r.item.criteria,
            "owner": "",
            "due": "",
            "status": "open",
        })
    return out
