"""XLSX 报告渲染（optional extra `[report]`；openpyxl 只在函数体内导入）。

内容来自 `report/model.py`（单一内容源），本模块把各节映射为工作表：
概览 / 依据 / 触发判定 / 检查单 / 问题台账 / 证据清单。落盘经 `docxutil.write_ooxml()`
收口为确定性字节（openpyxl 在 save 时才覆盖 core.xml 时间戳，故必须落盘后收口）。

工作表名固定（不随底稿变化），保证"同输入两次导出逐字节一致"。
"""

from .model import Bullets, Heading, Note, Para, Table, build

# 工作表名固定（Excel 限 31 字符；确定性的一部分）
_SHEETS = ["概览", "审计依据", "触发判定", "检查单", "问题台账", "证据清单"]


def render_xlsx(draft, ruleset, out_path, template="self"):
    """渲染 XLSX 报告并落盘（确定性字节）。返回输出路径。"""
    import io

    import openpyxl  # 函数体内导入：核心层 AST 守门（G3）要求 report 包不得顶层依赖重件

    from .docxutil import write_ooxml

    report = build(draft, ruleset, template=template)
    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # 去掉默认空表，只留本模块定义的固定工作表

    plan = _sheet_plan(report)
    for name in _SHEETS:
        ws = wb.create_sheet(title=name)
        _fill_sheet(ws, plan.get(name, []))
        ws.freeze_panes = "A2" if plan.get(name) else None

    _set_core_properties(wb, report)

    buf = io.BytesIO()
    wb.save(buf)
    return write_ooxml(buf.getvalue(), out_path)


def _set_core_properties(wb, report):
    """固定文档属性（时间戳由 docxutil 最终收口；此处只固定作者/标题）。"""
    props = wb.properties
    props.creator = "paudit"
    props.lastModifiedBy = "paudit"
    props.title = report.title
    props.description = "个人信息保护合规审计报告"


def _sheet_plan(report):
    """把结构化报告映射为 {工作表名: [行...]}（每行是字符串列表）。"""
    plan = {name: [] for name in _SHEETS}

    plan["概览"].append(["项目", "内容"])
    plan["概览"].append(["报告标题", report.title])
    plan["概览"].append(["规则包坐标", report.coord])
    plan["概览"].append(["声明", report.disclaimer])
    for line in report.signature_lines:
        plan["概览"].append(["签署", line.replace("- ", "")])

    for section in report.sections:
        target = _section_target(section.title)
        if target is None:
            continue
        for block in section.blocks:
            _emit(plan[target], block, section.title)
    return plan


_SECTION_TO_SHEET = {
    "一、审计范围": "概览",
    "二、审计依据清单": "审计依据",
    "三、审计触发与频次判定": "触发判定",
    "四、检查单全项结果": "检查单",
    "五、问题清单与整改台账": "问题台账",
    "六、证据清单与指纹": "证据清单",
}


def _section_target(title):
    return _SECTION_TO_SHEET.get(title)


def _emit(rows, block, section_title):
    """把块追加为行；标题行以【】标记，保证块边界在纯表格里仍可读。"""
    if isinstance(block, Heading):
        rows.append(["【%s】" % block.text])
    elif isinstance(block, Table):
        rows.append(list(block.headers))
        for r in block.rows:
            rows.append(["" if v is None else str(v) for v in r])
        if not block.rows:
            rows.append(["（无）"])
    elif isinstance(block, Bullets):
        for item in block.items:
            rows.append([_plain(item)])
    elif isinstance(block, Note):
        rows.append([_plain(block.text)])
    elif isinstance(block, Para):
        rows.append([_plain(block.text)])


def _plain(text):
    """去掉 Markdown 强调标记（XLSX 是纯文本载体）。"""
    return str(text).replace("**", "").replace("`", "")


def _fill_sheet(ws, rows):
    for row in rows:
        ws.append(row)
