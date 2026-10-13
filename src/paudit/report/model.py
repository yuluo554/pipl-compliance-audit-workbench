"""报告内容模型（核心层，仅标准库）——MD/DOCX/XLSX 的**单一内容源**。

三种格式共用本模块产出的结构化文档（标题/节/块），避免"各渲染器各写一套口径"
导致同一底稿在三种产物里结论不一致。渲染器只负责把块映射为各自的载体语法。

内容全部取自底稿与规则包（表现层零判定逻辑）：门槛分栏、四态、台账、证据
均由引擎产出后原样呈现。模板（自审版/第三方版）只影响抬头、附加列与签署栏。
"""

from .. import DISCLAIMER
from ..engine.remediation import LEDGER_STATUSES, ledger_summary
from ..rules.model import STATUS_VERIFIED

TEMPLATES = {
    "self": "企业自审版",
    "third_party": "第三方机构版",
}

LEDGER_LABELS = {
    "open": "待整改",
    "in_progress": "整改中",
    "resolved": "已整改",
    "waived": "已豁免",
}


class Block(object):
    """报告块基类。"""


class Heading(Block):
    def __init__(self, level, text):
        self.level = level
        self.text = text


class Para(Block):
    def __init__(self, text):
        self.text = text


class Bullets(Block):
    def __init__(self, items):
        self.items = list(items)


class Table(Block):
    def __init__(self, headers, rows):
        self.headers = list(headers)
        self.rows = [list(r) for r in rows]


class Note(Block):
    def __init__(self, text):
        self.text = text


class Section(object):
    def __init__(self, title, blocks=None):
        self.title = title
        self.blocks = list(blocks or [])


class Report(object):
    def __init__(self, title, coord, sections, signature_lines=None, disclaimer=None):
        self.title = title
        self.coord = coord
        self.sections = sections
        self.signature_lines = list(signature_lines or [])
        self.disclaimer = disclaimer if disclaimer is not None else DISCLAIMER


def _clause(cl):
    return "%s %s" % (cl.get("basis", ""), cl.get("article", ""))


def build(draft, ruleset, template="self"):
    """把底稿 + 规则包组装为结构化报告（模板只影响抬头/附加列/签署栏）。"""
    label = TEMPLATES.get(template, template)
    title = "个人信息保护合规审计报告（%s）" % label
    coord = "%s@%s（生成时间 %s）" % (
        ruleset.ruleset_id, ruleset.version, ruleset.generated_at)

    sections = [
        _scope_section(draft),
        _basis_section(ruleset),
        _threshold_section(draft),
        _checklist_section(draft, ruleset, template),
        _findings_section(draft),
        _evidence_section(draft),
        Section("七、声明", [Note(DISCLAIMER)]),
    ]
    signature = (["审计机构：________________", "复核人：________________"]
                 if template == "third_party" else [])
    return Report(title, coord, sections, signature_lines=signature)


def _scope_section(draft):
    scope = draft.get("audit_scope", {}) or {}
    return Section("一、审计范围", [
        Bullets([
            "主体：%s" % scope.get("subject", "（未填）"),
            "期间：%s" % scope.get("period", "（未填）"),
        ]),
    ])


def _basis_section(ruleset):
    rows = [[b.code, b.title, b.effective_date or "待核对",
             "已核对" if b.status == STATUS_VERIFIED else "待核对"]
            for b in ruleset.basis]
    return Section("二、审计依据清单", [
        Table(["依据编号", "名称", "施行/实施日期", "核对状态"], rows),
    ])


def _threshold_section(draft):
    thr = draft.get("threshold_result", {}) or {}
    obligations = thr.get("obligations", [])
    conditional = thr.get("conditional_triggers", [])

    blocks = [
        Bullets(["是否命中审计门槛：%s" % ("是" if thr.get("triggered") else "否")]),
        Heading(3, "3.1 处理者义务（无条件）"),
    ]
    if obligations:
        blocks.append(Table(
            ["结论码", "义务内容", "频次", "条款依据"],
            [[o.get("conclusion", ""), (o.get("clause") or {}).get("point", ""),
              o.get("frequency", "") or "—", _clause(o.get("clause") or {})]
             for o in obligations]))
    else:
        blocks.append(Bullets(["未命中无条件义务门槛。"]))

    blocks.append(Heading(3, "3.2 条件触发（保护部门可以要求）"))
    if conditional:
        blocks.append(Note("下列情形为保护部门可以要求委托专业机构开展审计，"
                           "非处理者无条件义务。"))
        blocks.append(Table(
            ["结论码", "情形", "条款依据"],
            [[c.get("conclusion", ""), (c.get("clause") or {}).get("point", ""),
              _clause(c.get("clause") or {})]
             for c in conditional]))
    else:
        blocks.append(Bullets(["未命中条件触发门槛。"]))
    return Section("三、审计触发与频次判定", blocks)


def _checklist_section(draft, ruleset, template):
    headers = ["检查项", "类别"]
    if template == "third_party":
        headers.append("核查方式")
    headers += ["判定", "说明", "条款依据"]

    # 核查方式来自规则包（底稿逐项结果不含 method，避免改动底稿 schema）
    methods = {c.id: c.method for c in ruleset.checklist}

    rows = []
    for it in draft.get("item_results", []):
        row = ["%s %s" % (it.get("item_id", ""), it.get("title", "")),
               it.get("category", "")]
        if template == "third_party":
            row.append(methods.get(it.get("item_id"), "") or "—")
        row += [it.get("state", ""), it.get("note", ""), _clause(it.get("clause") or {})]
        rows.append(row)
    return Section("四、检查单全项结果", [Table(headers, rows)])


def _findings_section(draft):
    blocks = [Table(
        ["编号", "检查项", "风险级", "依据条款", "整改建议", "责任人", "期限", "状态"],
        [[f.get("finding_id", ""), f.get("title", ""), f.get("risk", ""),
          _clause(f.get("clause") or {}), f.get("recommendation", ""),
          f.get("owner", "") or "（待指定）", f.get("due", "") or "（待定）",
          LEDGER_LABELS.get(f.get("status", ""), f.get("status", ""))]
         for f in draft.get("findings", [])])]

    summary = ledger_summary(draft)
    if summary["total"]:
        blocks.append(Note("台账汇总：共 %d 项，已指定责任人 %d 项；%s。" % (
            summary["total"], summary["assigned"],
            "、".join("%s %d 项" % (LEDGER_LABELS[s], summary[s])
                      for s in LEDGER_STATUSES if summary[s]))))
    return Section("五、问题清单与整改台账", blocks)


def _evidence_section(draft):
    rows = []
    for it in draft.get("item_results", []):
        for ev in it.get("evidence", []):
            rows.append([ev.get("evidence_id", ""), it.get("item_id", ""),
                         ev.get("source", ""), ev.get("collected_at", ""),
                         ev.get("owner", ""), ev.get("size", ""), ev.get("sha256", "")])
    blocks = [Table(["证据编号", "检查项", "来源", "采集时间", "责任人", "大小", "sha256"],
                    rows)]
    if not rows:
        blocks.append(Note("本底稿尚未挂载证据（paudit evidence <draft> --add 检查项=文件）。"))
    elif draft.get("draft_sha256"):
        blocks.append(Note("底稿自指纹（draft_sha256）：%s" % draft["draft_sha256"]))
    return Section("六、证据清单与指纹", blocks)
