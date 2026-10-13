"""报告渲染（核心层：Markdown，零第三方依赖）。

报告头固定输出规则包坐标（依据版本 + 版本号 + 生成时间）；强制免责声明。
无系统时间戳：报告时间取底稿显式字段。
"""

from .. import DISCLAIMER
from ..rules.model import STATUS_VERIFIED

TEMPLATES = {
    "self": "企业自审版",
    "third_party": "第三方机构版",
}


def _coord(ruleset):
    return "%s@%s（生成时间 %s）" % (
        ruleset.ruleset_id, ruleset.version, ruleset.generated_at)


def render_markdown(draft, ruleset, template="self"):
    """把底稿渲染为 Markdown 报告。"""
    L = []
    title = TEMPLATES.get(template, template)
    L.append("# 个人信息保护合规审计报告（%s）" % title)
    L.append("")
    L.append("> 规则包坐标：**%s**" % _coord(ruleset))
    L.append("")

    scope = draft.get("audit_scope", {})
    L.append("## 一、审计范围")
    L.append("")
    L.append("- 主体：%s" % scope.get("subject", "（未填）"))
    L.append("- 期间：%s" % scope.get("period", "（未填）"))
    L.append("")

    L.append("## 二、审计依据清单")
    L.append("")
    L.append("| 依据编号 | 名称 | 施行/实施日期 | 核对状态 |")
    L.append("|---|---|---|---|")
    for b in ruleset.basis:
        L.append("| %s | %s | %s | %s |" % (
            b.code, b.title, b.effective_date or "待核对",
            "已核对" if b.status == STATUS_VERIFIED else "待核对"))
    L.append("")

    thr = draft.get("threshold_result", {})
    L.append("## 三、审计触发与频次判定")
    L.append("")
    L.append("- 是否触发审计义务：**%s**" % ("是" if thr.get("triggered") else "否"))
    if thr.get("frequency"):
        L.append("- 适用频次：%s" % thr["frequency"])
    for c in thr.get("clauses", []):
        L.append("- 条款依据：%s %s（%s）" % (c.get("basis"), c.get("article"), c.get("point", "")))
    L.append("")

    L.append("## 四、检查单全项结果")
    L.append("")
    L.append("| 检查项 | 类别 | 判定 | 说明 | 条款依据 |")
    L.append("|---|---|---|---|---|")
    for it in draft.get("item_results", []):
        cl = it.get("clause", {})
        L.append("| %s %s | %s | %s | %s | %s %s |" % (
            it.get("item_id", ""), it.get("title", ""), it.get("category", ""),
            it.get("state", ""), it.get("note", ""),
            cl.get("basis", ""), cl.get("article", "")))
    L.append("")

    L.append("## 五、问题清单与整改台账")
    L.append("")
    L.append("| 编号 | 检查项 | 风险级 | 依据条款 | 整改建议 | 责任人 | 期限 | 状态 |")
    L.append("|---|---|---|---|---|---|---|---|")
    for f in draft.get("findings", []):
        cl = f.get("clause", {})
        L.append("| %s | %s | %s | %s %s | %s | %s | %s | %s |" % (
            f.get("finding_id", ""), f.get("title", ""), f.get("risk", ""),
            cl.get("basis", ""), cl.get("article", ""),
            f.get("recommendation", ""), f.get("owner", ""), f.get("due", ""),
            f.get("status", "")))
    L.append("")

    L.append("## 六、证据清单与指纹")
    L.append("")
    L.append("| 证据编号 | 检查项 | 来源 | 采集时间 | 责任人 | 大小 | sha256 |")
    L.append("|---|---|---|---|---|---|---|")
    for it in draft.get("item_results", []):
        for ev in it.get("evidence", []):
            L.append("| %s | %s | %s | %s | %s | %s | %s |" % (
                ev.get("evidence_id", ""), it.get("item_id", ""),
                ev.get("source", ""), ev.get("collected_at", ""),
                ev.get("owner", ""), ev.get("size", ""), ev.get("sha256", "")))
    L.append("")

    L.append("## 七、声明")
    L.append("")
    L.append("> %s" % DISCLAIMER)
    if template == "third_party":
        L.append("")
        L.append("- 审计机构：________________")
        L.append("- 复核人：________________")
    L.append("")
    return "\n".join(L)
