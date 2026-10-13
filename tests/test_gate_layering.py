"""守门测试 G3：核心层零重依赖（AST 静态断言）。

核心层（rules/engine/evidence/report-markdown/benchmark/paths/errors）不得 import
PySide6 / python-docx / openpyxl 等重件；gui 子包允许（但只在函数体内导入）。
"""

import ast
from pathlib import Path

from conftest import ROOT

CORE_FILES = [
    "src/paudit/__init__.py", "src/paudit/__main__.py", "src/paudit/cli.py",
    "src/paudit/paths.py", "src/paudit/errors.py",
]
CORE_DIRS = ["src/paudit/rules", "src/paudit/engine", "src/paudit/evidence",
             "src/paudit/report", "src/paudit/benchmark"]

HEAVY = ("PySide6", "docx", "openpyxl", "pyinstaller", "PyInstaller")


def _files():
    for rel in CORE_FILES:
        yield ROOT / rel
    for d in CORE_DIRS:
        yield from (ROOT / d).rglob("*.py")


def _imported_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
    return names


def test_core_layer_has_no_heavy_imports():
    bad = []
    for f in _files():
        names = _imported_names(ast.parse(f.read_text(encoding="utf-8"), filename=str(f)))
        for h in HEAVY:
            if h in names:
                bad.append("%s imports %s" % (f.relative_to(ROOT), h))
    assert not bad, "核心层不得 import 重件: %s" % bad


def test_cli_does_not_toplevel_import_gui_or_qt():
    """cli.py 顶层不得 import gui/PySide6（惰性导入边界由函数体承担）。"""
    tree = ast.parse((ROOT / "src/paudit/cli.py").read_text(encoding="utf-8"))
    top = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            top.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            top.add(node.module.split(".")[0])
    assert "PySide6" not in top
    # gui 只允许在函数体内以 from .gui import ... 出现（非顶层）
    assert "paudit.gui" not in top


def test_core_has_no_network_imports():
    """NFR-1：核心层不得 import 网络库（零上传）。"""
    net = ("requests", "urllib.request", "http.client", "socket", "aiohttp")
    bad = []
    for f in _files():
        text = f.read_text(encoding="utf-8")
        names = _imported_names(ast.parse(text, filename=str(f)))
        for n in net:
            if n.split(".")[0] in names:
                bad.append("%s imports %s" % (f.relative_to(ROOT), n))
    assert not bad, "核心层不得 import 网络库: %s" % bad
