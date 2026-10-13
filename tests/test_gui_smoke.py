"""GUI 冒烟（offscreen，缺 PySide6 则整模块声明式跳过）。

纪律：QT_QPA_PLATFORM=offscreen 必须在**首次导入 PySide6 前**设置；
必须先有 QApplication 才能创建 QWidget/QMainWindow（否则 Qt 直接终止进程）；
冒烟只验"能构建、能渲染"，业务正确性由 `test_gui_session.py`（零 Qt）守住。

注意（环境坑）：Qt 在 pytest 收集期偶发访问违例；本模块为唯一导入 Qt 的测试，
全量 `pytest -q` 稳定通过。
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


@pytest.fixture
def demo_card_path(tmp_path, demo_card):
    import json

    p = tmp_path / "card.json"
    p.write_text(json.dumps(demo_card, ensure_ascii=False), encoding="utf-8")
    return p


def test_build_window_has_four_tabs(qt_app):
    from paudit.gui.main_window import build_window

    win = build_window()
    assert win.windowTitle() == "个人信息保护合规审计工作台"
    tabs = win.centralWidget()
    assert tabs.count() == 4
    assert [tabs.tabText(i) for i in range(tabs.count())] == [
        "触发判定", "检查单", "证据链", "报告导出"]
    win.close()


def test_main_window_renders_after_run(qt_app, demo_card_path):
    """端到端：载入示例规则包 + 参数卡 → 运行 → 四页签表格被填充。"""
    from conftest import DEMO_RULESET

    from paudit.gui.main_window import MainWindow

    mw = MainWindow()
    mw.session.load_ruleset(str(DEMO_RULESET))
    mw.session.load_card(str(demo_card_path))
    mw.session.run()
    mw._refresh_all()

    assert "是否命中门槛" in mw.lbl_summary.text()
    assert mw.tbl_threshold.rowCount() >= 1
    assert mw.tbl_checklist.rowCount() == len(mw.session.draft["item_results"])
    assert mw.tbl_findings.rowCount() == len(mw.session.draft["findings"])
    assert mw.cmb_item.count() == len(mw.session.item_ids())
    mw.win.close()


def test_gui_lazy_import_boundary():
    """gui 子包顶层不得 import PySide6（重件只在函数体内）。"""
    import ast

    from conftest import ROOT

    for name in ("__init__.py", "main_window.py", "session.py"):
        tree = ast.parse((ROOT / "src" / "paudit" / "gui" / name).read_text(encoding="utf-8"))
        top = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                top.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                top.add(node.module.split(".")[0])
        assert "PySide6" not in top, "%s 顶层不得 import PySide6" % name
