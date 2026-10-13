"""报告渲染：Markdown（核心层，零第三方依赖）。

内容来自 `report/model.py`（MD/DOCX/XLSX 的**单一内容源**），本模块只做
"块 → Markdown 语法"的映射。报告头固定输出规则包坐标（依据版本 + 版本号 + 生成时间）；
强制免责声明。无系统时间戳：报告时间取底稿显式字段。
"""

from .model import TEMPLATES, Bullets, Heading, Note, Para, Table, build

__all__ = ["TEMPLATES", "render_markdown"]


def render_markdown(draft, ruleset, template="self"):
    """把底稿渲染为 Markdown 报告。"""
    report = build(draft, ruleset, template=template)
    L = ["# %s" % report.title, "", "> 规则包坐标：**%s**" % report.coord, ""]
    for section in report.sections:
        L.append("## %s" % section.title)
        L.append("")
        for block in section.blocks:
            L.extend(_render_block(block))
        L.append("")
    for line in report.signature_lines:
        L.append("- %s" % line)
    if report.signature_lines:
        L.append("")
    return "\n".join(L)


def _render_block(block):
    if isinstance(block, Heading):
        return ["### %s" % block.text, ""]
    if isinstance(block, Para):
        return [block.text, ""]
    if isinstance(block, Bullets):
        return ["- %s" % item for item in block.items] + [""]
    if isinstance(block, Note):
        return ["> %s" % block.text, ""]
    if isinstance(block, Table):
        return _render_table(block)
    return [str(getattr(block, "text", block)), ""]


def _cell(value):
    """表格单元转义：竖线与换行会破坏 Markdown 表结构。"""
    return str("" if value is None else value).replace("|", "\\|").replace("\n", " ")


def _render_table(table):
    if not table.headers:
        return []
    L = ["| %s |" % " | ".join(_cell(h) for h in table.headers),
         "|%s|" % ("---|" * len(table.headers))]
    for row in table.rows:
        L.append("| %s |" % " | ".join(_cell(v) for v in row))
    L.append("")
    return L
