"""GUI 会话模型（纯 Python，零 Qt 依赖，可无头测试）。

分层纪律：本模块是界面的**数据面**，只调用引擎 API（`compute_audit` /
`attach_evidence` / `apply_ledger` / `export_draft` / `render_to_file`），
**零判定逻辑**——门槛结论、四态、问题分级一律由引擎产出后原样持有。
Qt 层只做"读 session → 填控件"与"读控件 → 调 session"。

与 Qt 解耦的好处：会话逻辑可用普通 pytest 覆盖（不必起 QApplication），
GUI 冒烟只验"能构建、能渲染"，业务正确性由本模块的测试守住。
"""

import json
from pathlib import Path

from ..errors import InputError
from ..rules.loader import load_ruleset


class SessionError(InputError):
    """界面会话输入不可用（复用 CLI 退出码 2 的语义）。"""


class Session(object):
    """一次审计会话：规则包 + 参数卡 → 底稿 → 证据/台账 → 报告。"""

    def __init__(self):
        self.ruleset = None
        self.ruleset_path = ""
        self.card_path = ""
        self.card = {}
        self.manual_results = {}
        self.audit_scope = {}
        self.draft = None

    # -- 载入 -------------------------------------------------------------
    def load_ruleset(self, path=None):
        """载入生效规则包（status/出处门控由 loader 负责，本层不绕过）。"""
        self.ruleset = load_ruleset(path or self.ruleset_path or None)
        self.ruleset_path = path or self.ruleset_path
        return self.ruleset

    def load_card(self, path):
        """载入参数卡 JSON（含 input_card / manual_results / audit_scope）。"""
        p = Path(path)
        if not p.is_file():
            raise SessionError("参数卡文件不存在: %s" % p)
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise SessionError("参数卡 JSON 解析失败: %s (%s)" % (p, exc))
        self.card_path = str(p)
        self.card = data.get("input_card", data) or {}
        self.manual_results = data.get("manual_results", {}) or {}
        self.audit_scope = data.get("audit_scope", {}) or {}
        return data

    # -- 判定（只编排，不判定） -------------------------------------------
    def run(self):
        """调唯一编排源产出底稿形态结论。"""
        from ..engine.pipeline import AuditRequest, compute_audit

        if self.ruleset is None:
            self.load_ruleset()
        self.draft = compute_audit(
            AuditRequest(self.card, self.manual_results, self.audit_scope),
            self.ruleset).to_dict()
        return self.draft

    def _require_draft(self):
        if self.draft is None:
            raise SessionError("尚未运行判定（请先选择参数卡并运行）")
        return self.draft

    # -- 呈现数据（全部取自引擎产出，界面零加工） -------------------------
    def threshold_view(self):
        """触发判定视图数据：结论 + 义务分栏 + 频次。"""
        thr = self._require_draft().get("threshold_result", {}) or {}
        return {
            "triggered": bool(thr.get("triggered")),
            "conclusions": list(thr.get("conclusions", [])),
            "frequency": thr.get("frequency", ""),
            "obligations": list(thr.get("obligations", [])),
            "conditional_triggers": list(thr.get("conditional_triggers", [])),
            "clauses": list(thr.get("clauses", [])),
        }

    def checklist_rows(self):
        """检查单行（四态 + 依据），供表格展示。"""
        rows = []
        for it in self._require_draft().get("item_results", []):
            cl = it.get("clause", {}) or {}
            rows.append({
                "item_id": it.get("item_id", ""),
                "category": it.get("category", ""),
                "title": it.get("title", ""),
                "state": it.get("state", ""),
                "note": it.get("note", ""),
                "basis": cl.get("basis", ""),
                "article": cl.get("article", ""),
            })
        return rows

    def findings_rows(self):
        """问题清单 + 台账三字段（owner/due/status）。"""
        rows = []
        for f in self._require_draft().get("findings", []):
            cl = f.get("clause", {}) or {}
            rows.append({
                "finding_id": f.get("finding_id", ""),
                "title": f.get("title", ""),
                "risk": f.get("risk", ""),
                "basis": cl.get("basis", ""),
                "article": cl.get("article", ""),
                "recommendation": f.get("recommendation", ""),
                "owner": f.get("owner", ""),
                "due": f.get("due", ""),
                "status": f.get("status", ""),
            })
        return rows

    def evidence_rows(self):
        """已挂证据行（含 sha256 指纹）。"""
        rows = []
        for it in self._require_draft().get("item_results", []):
            for ev in it.get("evidence", []):
                rows.append({
                    "evidence_id": ev.get("evidence_id", ""),
                    "item_id": it.get("item_id", ""),
                    "source": ev.get("source", ""),
                    "collected_at": ev.get("collected_at", ""),
                    "owner": ev.get("owner", ""),
                    "size": ev.get("size", 0),
                    "sha256": ev.get("sha256", ""),
                })
        return rows

    def item_ids(self):
        """可选检查项 id（挂证下拉用）。"""
        return [it.get("item_id", "") for it in self._require_draft().get("item_results", [])]

    # -- 编辑（挂证 / 台账；不改判定结论） --------------------------------
    def attach_evidence(self, item_id, file_path, source="", collected_at="", owner=""):
        from ..evidence import attach_evidence, has_item

        draft = self._require_draft()
        if not has_item(draft, item_id):
            raise SessionError("底稿中不存在检查项 %s" % item_id)
        # 挂证改变了底稿正文 → 旧自指纹失效（与 CLI 同口径：清除，需固化时重导出）
        draft.pop("draft_sha256", None)
        return attach_evidence(draft, item_id, file_path, source=source,
                               collected_at=collected_at, owner=owner)

    def set_ledger(self, entries):
        from ..engine.remediation import apply_ledger

        draft = self._require_draft()
        draft.pop("draft_sha256", None)
        return apply_ledger(draft, entries)

    # -- 导出 -------------------------------------------------------------
    def export_draft(self, out_path):
        from ..evidence import export_draft

        return export_draft(self._require_draft(), out_path)

    def export_report(self, out_path, template="self"):
        from ..report import render_to_file

        return render_to_file(self._require_draft(), self.ruleset, out_path,
                              template=template)

    def ledger_csv(self, out_path):
        from ..engine.remediation import export_ledger

        return export_ledger(self._require_draft(), out_path)
