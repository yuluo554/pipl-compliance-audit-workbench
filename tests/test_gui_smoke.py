"""GUI 骨架冒烟（offscreen，缺 PySide6 则整模块声明式跳过）。

纪律：QT_QPA_PLATFORM=offscreen 必须在**首次导入 PySide6 前**设置；
必须先有 QApplication 才能创建 QWidget/QMainWindow（否则 Qt 直接终止进程）；
本骨架不触发任何模态框。
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")


@pytest.fixture(scope="module")
def qt_app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def test_build_window_has_tabs(qt_app):
    from paudit.gui.main_window import build_window

    win = build_window()
    assert win.windowTitle() == "个人信息保护合规审计工作台"
    tabs = win.centralWidget()
    assert tabs.count() == 4
    win.close()


def test_gui_lazy_import_boundary():
    """gui 子包顶层不得 import PySide6（重件只在函数体内）。"""
    import ast

    from conftest import ROOT

    for name in ("__init__.py", "main_window.py"):
        tree = ast.parse((ROOT / "src" / "paudit" / "gui" / name).read_text(encoding="utf-8"))
        top = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                top.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                top.add(node.module.split(".")[0])
        assert "PySide6" not in top, "%s 顶层不得 import PySide6" % name
