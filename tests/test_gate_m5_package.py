"""守门测试 G12：M5 桌面交付与报告导出（防"实现了但没接上/打包漏红线"回归）。

断言：
- GUI 四页签齐备且**只消费引擎 API**（session 层零判定逻辑、无政策字面量）；
- `session.py` 纯 Python（不 import Qt），Qt 只在 `main_window` 函数体内导入；
- 打包白名单排除版权禁区 `data/knowledge/raw`（构建器抛错 + spec 无禁区字面量）；
- 两个 PyInstaller spec 存在且 onedir（COLLECT）；
- report 包按扩展名分派三格式；CLI `report` 子命令支持三格式。

本门与 G3（分层）、G10（M3 接入面）互补：G3 守"核心层不被重件污染"，
本门守"桌面交付面真的接上了引擎、且不夹带版权红线文件"。
"""

import ast
from pathlib import Path

from conftest import ROOT

SRC = ROOT / "src" / "paudit"
TOOLS = ROOT / "tools"


def _text(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# GUI 页签与分层
# ---------------------------------------------------------------------------
def test_gui_has_four_tabs():
    text = _text("src/paudit/gui/main_window.py")
    for name in ("触发判定", "检查单", "证据链", "报告导出"):
        assert name in text, "GUI 缺页签: %s" % name


def test_gui_session_has_no_qt_import():
    """session.py 是纯数据面：任何位置都不得 import Qt（无头可测）。"""
    tree = ast.parse(_text("src/paudit/gui/session.py"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                assert not a.name.startswith("PySide6"), "session 不得 import Qt"
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("PySide6"), "session 不得 import Qt"


def test_gui_main_window_imports_qt_only_in_function_body():
    """Qt 只能在函数体内导入（模块顶层不得导入）。"""
    tree = ast.parse(_text("src/paudit/gui/main_window.py"))
    top = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            top.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            top.add(node.module.split(".")[0])
    assert "PySide6" not in top


def test_gui_session_delegates_to_engine_not_reimplementing():
    """会话层须调用唯一编排源与引擎 API（防界面自己算判定）。"""
    text = _text("src/paudit/gui/session.py")
    for symbol in ("compute_audit", "attach_evidence", "apply_ledger",
                   "export_draft", "render_to_file"):
        assert symbol in text, "会话层未接入引擎 API: %s" % symbol
    # 不得直接读门槛数值/自行比较阈值（判定只能来自引擎）
    assert "ruleset.thresholds" not in text, "会话层不得自行遍历门槛求值"


def test_gui_entry_points_exist():
    assert (SRC / "gui_entry.py").is_file(), "缺 GUI 冻结入口"
    assert (SRC / "cli_entry.py").is_file(), "缺 CLI 冻结入口"


# ---------------------------------------------------------------------------
# 打包白名单与版权红线
# ---------------------------------------------------------------------------
def test_build_data_whitelist_excludes_copyright_redline():
    import sys

    sys.path.insert(0, str(TOOLS))
    try:
        import build_data
    finally:
        sys.path.pop(0)

    for rel in build_data.DATA_WHITELIST:
        assert not build_data.is_forbidden(rel), "白名单含禁区: %s" % rel
    assert build_data.is_forbidden("data/knowledge/raw")
    assert build_data.is_forbidden("data/knowledge/raw/x.txt")


def test_build_data_raises_on_forbidden_and_expands_clean_tree():
    import sys

    sys.path.insert(0, str(TOOLS))
    try:
        import build_data
    finally:
        sys.path.pop(0)

    datas = build_data.collect_data_sources(ROOT)
    assert datas, "白名单未展开出任何数据"
    for src, _dest in datas:
        rel = Path(src).relative_to(ROOT).as_posix()
        assert not build_data.is_forbidden(rel), "展开结果夹带禁区: %s" % rel

    import pytest
    with pytest.raises(build_data.BuildError):
        build_data.collect_data_sources(ROOT, whitelist=("data/knowledge/raw",))


def test_specs_exist_are_onedir_and_free_of_redline_literals():
    for name in ("paudit-gui.spec", "paudit-cli.spec"):
        f = TOOLS / name
        assert f.is_file(), "缺 spec: %s" % name
        text = f.read_text(encoding="utf-8")
        assert "COLLECT(" in text, "%s 非 onedir（缺 COLLECT）" % name
        assert "collect_data_sources" in text, "%s 未走白名单单一实现源" % name
        # 禁区路径不得作为字面量出现在 spec（spec 守门）
        assert "knowledge/raw" not in text, "%s 出现版权禁区字面量" % name


def test_specs_declare_dual_entries():
    gui = (TOOLS / "paudit-gui.spec").read_text(encoding="utf-8")
    cli = (TOOLS / "paudit-cli.spec").read_text(encoding="utf-8")
    assert "gui_entry.py" in gui
    assert "cli_entry.py" in cli
    assert "PySide6" in cli, "CLI spec 应显式排除 PySide6（精简产物）"


# ---------------------------------------------------------------------------
# 报告分派与 CLI
# ---------------------------------------------------------------------------
def test_report_package_dispatches_three_formats():
    text = _text("src/paudit/report/__init__.py")
    assert "render_to_file" in text
    for ext in (".md", ".docx", ".xlsx"):
        assert ext in text, "报告分派缺格式: %s" % ext


def test_cli_report_supports_docx_and_xlsx():
    text = _text("src/paudit/cli.py")
    assert "render_to_file" in text, "CLI 未接入三格式分派"
    assert ".docx" in text and ".xlsx" in text


def test_docxutil_is_pure_stdlib_and_single_source():
    """收口器须是纯标准库（核心层），且被 DOCX/XLSX 两条通路共用。"""
    tree = ast.parse(_text("src/paudit/report/docxutil.py"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    assert not (names & {"docx", "openpyxl", "PySide6"}), "docxutil 必须是纯标准库"

    for rel in ("src/paudit/report/docx.py", "src/paudit/report/xlsx.py"):
        assert "write_ooxml" in _text(rel), "%s 未走共用收口" % rel
