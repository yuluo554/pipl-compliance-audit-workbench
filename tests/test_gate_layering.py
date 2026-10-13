"""守门测试 G3：核心层零重依赖（AST 静态断言）。

两层纪律（M5 起，report 包拆分后细化）：
- **严格核心层**（rules/engine/evidence/benchmark + report 的 markdown/model/docxutil）
  任何位置都不得 import PySide6 / python-docx / openpyxl / pyinstaller；
- **惰性边界层**（gui/* + report 的 __init__/docx/xlsx）允许依赖重件，但**只能在函数体内**
  导入（模块顶层不得 import），保证核心通路在未装 extra 时仍可跑。

`report/docxutil.py` 只做 zip 收口（纯标准库），故留在严格核心层。
"""

import ast
from pathlib import Path

from conftest import ROOT

# 严格核心：任何位置不得出现重件 import
STRICT_FILES = [
    "src/paudit/__init__.py", "src/paudit/__main__.py", "src/paudit/cli.py",
    "src/paudit/paths.py", "src/paudit/errors.py",
    "src/paudit/report/__init__.py", "src/paudit/report/markdown.py",
    "src/paudit/report/model.py", "src/paudit/report/docxutil.py",
]
STRICT_DIRS = ["src/paudit/rules", "src/paudit/engine", "src/paudit/evidence",
               "src/paudit/benchmark"]

# 惰性边界：重件 import 只允许出现在函数体内（顶层不得导入）
LAZY_FILES = ["src/paudit/report/docx.py", "src/paudit/report/xlsx.py"]

HEAVY = ("PySide6", "docx", "openpyxl", "pyinstaller", "PyInstaller")


def _strict_files():
    for rel in STRICT_FILES:
        yield ROOT / rel
    for d in STRICT_DIRS:
        yield from (ROOT / d).rglob("*.py")


def _imported_from(node):
    """从 ImportFrom 取顶层包名；相对导入（level>0，如 `from .docx import x`）不计。"""
    if getattr(node, "level", 0) or not node.module:
        return None
    return node.module.split(".")[0]


def _all_imported_names(tree):
    """整棵树（含函数体）里 import 的顶层包名（相对导入不计）。"""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            name = _imported_from(node)
            if name:
                names.add(name)
    return names


def _toplevel_imported_names(tree):
    """仅模块顶层（函数体之外）import 的顶层包名（相对导入不计）。"""
    names = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            name = _imported_from(node)
            if name:
                names.add(name)
    return names


def test_strict_core_has_no_heavy_imports():
    bad = []
    for f in _strict_files():
        names = _all_imported_names(ast.parse(f.read_text(encoding="utf-8"), filename=str(f)))
        for h in HEAVY:
            if h in names:
                bad.append("%s imports %s" % (f.relative_to(ROOT), h))
    assert not bad, "严格核心层不得 import 重件: %s" % bad


def test_lazy_boundary_imports_heavy_only_in_function_body():
    """惰性边界层（report/docx.py 等）：重件不得在模块顶层导入。"""
    bad = []
    for rel in LAZY_FILES:
        f = ROOT / rel
        top = _toplevel_imported_names(ast.parse(f.read_text(encoding="utf-8"),
                                                filename=str(f)))
        for h in HEAVY:
            if h in top:
                bad.append("%s 顶层 imports %s（应移入函数体）" % (rel, h))
    assert not bad, bad


def test_report_package_exports_all_three_formats():
    """report 包须暴露 md/docx/xlsx 三分派（接入面：三格式共用内容源）。"""
    text = (ROOT / "src" / "paudit" / "report" / "__init__.py").read_text(encoding="utf-8")
    assert "render_to_file" in text
    for ext in (".md", ".docx", ".xlsx"):
        assert ext in text, "report 分派缺格式: %s" % ext


def test_cli_does_not_toplevel_import_gui_or_qt():
    """cli.py 顶层不得 import gui/PySide6（惰性导入边界由函数体承担）。"""
    tree = ast.parse((ROOT / "src/paudit/cli.py").read_text(encoding="utf-8"))
    top = _toplevel_imported_names(tree)
    assert "PySide6" not in top
    assert "paudit.gui" not in top


def test_core_has_no_network_imports():
    """NFR-1：核心层不得 import 网络库（零上传）。"""
    net = ("requests", "urllib.request", "http.client", "socket", "aiohttp")
    bad = []
    for f in _strict_files():
        names = _all_imported_names(ast.parse(f.read_text(encoding="utf-8"), filename=str(f)))
        for n in net:
            if n.split(".")[0] in names:
                bad.append("%s imports %s" % (f.relative_to(ROOT), n))
    assert not bad, "核心层不得 import 网络库: %s" % bad
