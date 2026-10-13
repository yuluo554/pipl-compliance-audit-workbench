"""桌面应用（PySide6，optional extra）。

分层纪律：本层只消费引擎 API，零判定逻辑；PySide6 只在函数体内导入
（AST 守门断言核心层与 cli 顶层不得 import PySide6）。
"""


def _qt():
    from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QTabWidget, QWidget

    return QApplication, QMainWindow, QTabWidget, QWidget, QLabel


def build_window():
    """构建主窗口（多页签：触发判定 / 检查单 / 证据 / 报告）。"""
    QApplication, QMainWindow, QTabWidget, QWidget, QLabel = _qt()

    win = QMainWindow()
    win.setWindowTitle("个人信息保护合规审计工作台")
    tabs = QTabWidget()
    for name in ("触发判定", "检查单", "证据链", "报告导出"):
        page = QWidget()
        layout_holder = page
        layout_holder.setLayout(_vbox(QLabel("%s（骨架页，待 M5 实现）" % name)))
        tabs.addTab(page, name)
    win.setCentralWidget(tabs)
    return win


def _vbox(widget):
    from PySide6.QtWidgets import QVBoxLayout

    box = QVBoxLayout()
    box.addWidget(widget)
    return box


def main(argv=None):
    """GUI 入口：返回退出码。"""
    QApplication, _MW, _TW, _W, _L = _qt()
    app = QApplication.instance() or QApplication(argv or [])
    win = build_window()
    win.resize(1000, 680)
    win.show()
    return app.exec()
