"""桌面应用（PySide6，optional extra）。

分层纪律：本层只消费 `gui.session.Session`（其内部只调引擎 API），**零判定逻辑**；
PySide6 只在函数体内导入（AST 守门断言核心层与 cli 顶层不得 import PySide6）。

四个页签对应审计工作流：
1. 触发判定——门槛结论 + 义务分栏（无条件 / 条件触发），条件触发不得冒充处理者义务；
2. 检查单——全项四态 + 依据；
3. 证据链——挂证（登记文件名 + sha256）与台账填写；
4. 报告导出——MD/DOCX/XLSX + 模板两版，并导出底稿。
"""

from .session import Session, SessionError


def _qt():
    from PySide6.QtWidgets import (
        QApplication, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QHeaderView,
        QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QTableWidget,
        QTableWidgetItem, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
    )

    return {
        "QApplication": QApplication, "QComboBox": QComboBox,
        "QFileDialog": QFileDialog, "QFormLayout": QFormLayout,
        "QHBoxLayout": QHBoxLayout, "QHeaderView": QHeaderView, "QLabel": QLabel,
        "QLineEdit": QLineEdit, "QMainWindow": QMainWindow,
        "QMessageBox": QMessageBox, "QPushButton": QPushButton,
        "QTableWidget": QTableWidget, "QTableWidgetItem": QTableWidgetItem,
        "QTabWidget": QTabWidget, "QTextEdit": QTextEdit, "QVBoxLayout": QVBoxLayout,
        "QWidget": QWidget,
    }


class MainWindow(object):
    """主窗口装配器（组合而非继承，便于无头测试装配逻辑）。"""

    def __init__(self):
        self.q = _qt()
        self.session = Session()
        self.win = self.q["QMainWindow"]()
        self.win.setWindowTitle("个人信息保护合规审计工作台")
        self._tabs = self.q["QTabWidget"]()
        self._tabs.addTab(self._build_trigger_tab(), "触发判定")
        self._tabs.addTab(self._build_checklist_tab(), "检查单")
        self._tabs.addTab(self._build_evidence_tab(), "证据链")
        self._tabs.addTab(self._build_report_tab(), "报告导出")
        self.win.setCentralWidget(self._tabs)

    # -- 顶部公共条：规则包 / 参数卡 / 运行 -------------------------------
    def _build_input_bar(self, parent_layout):
        q = self.q
        bar = q["QHBoxLayout"]()
        self.lbl_ruleset = q["QLabel"]("规则包：未选择")
        self.lbl_card = q["QLabel"]("参数卡：未选择")
        btn_ruleset = q["QPushButton"]("选择规则包…")
        btn_card = q["QPushButton"]("选择参数卡…")
        btn_run = q["QPushButton"]("运行判定")
        btn_ruleset.clicked.connect(self._choose_ruleset)
        btn_card.clicked.connect(self._choose_card)
        btn_run.clicked.connect(self._run)
        for w in (btn_ruleset, btn_card, btn_run, self.lbl_ruleset, self.lbl_card):
            bar.addWidget(w)
        parent_layout.addLayout(bar)

    # -- 页签 1：触发判定 -------------------------------------------------
    def _build_trigger_tab(self):
        q = self.q
        page = q["QWidget"]()
        layout = q["QVBoxLayout"]()
        self._build_input_bar(layout)
        self.lbl_summary = q["QLabel"]("尚未运行判定")
        layout.addWidget(self.lbl_summary)
        self.tbl_threshold = q["QTableWidget"](0, 4)
        self.tbl_threshold.setHorizontalHeaderLabels(
            ["栏位", "结论码", "义务内容", "条款依据"])
        layout.addWidget(self.tbl_threshold)
        page.setLayout(layout)
        return page

    # -- 页签 2：检查单 ---------------------------------------------------
    def _build_checklist_tab(self):
        q = self.q
        page = q["QWidget"]()
        layout = q["QVBoxLayout"]()
        self.tbl_checklist = q["QTableWidget"](0, 6)
        self.tbl_checklist.setHorizontalHeaderLabels(
            ["检查项", "类别", "判定", "说明", "依据", "条号"])
        layout.addWidget(self.tbl_checklist)
        page.setLayout(layout)
        return page

    # -- 页签 3：证据链 + 台账 -------------------------------------------
    def _build_evidence_tab(self):
        q = self.q
        page = q["QWidget"]()
        layout = q["QVBoxLayout"]()

        form = q["QFormLayout"]()
        self.cmb_item = q["QComboBox"]()
        self.ed_ev_file = q["QLineEdit"]()
        self.ed_ev_owner = q["QLineEdit"]()
        self.ed_ev_date = q["QLineEdit"]()
        btn_ev_file = q["QPushButton"]("选择证据文件…")
        btn_ev_add = q["QPushButton"]("挂证")
        btn_ev_file.clicked.connect(self._choose_evidence_file)
        btn_ev_add.clicked.connect(self._attach_evidence)
        row = q["QHBoxLayout"]()
        row.addWidget(self.ed_ev_file)
        row.addWidget(btn_ev_file)
        form.addRow("检查项", self.cmb_item)
        form.addRow("证据文件", row)
        form.addRow("责任人", self.ed_ev_owner)
        form.addRow("采集时间", self.ed_ev_date)
        form.addRow("", btn_ev_add)
        layout.addLayout(form)

        self.tbl_evidence = q["QTableWidget"](0, 6)
        self.tbl_evidence.setHorizontalHeaderLabels(
            ["证据编号", "检查项", "来源", "采集时间", "责任人", "sha256"])
        layout.addWidget(self.tbl_evidence)

        layout.addWidget(q["QLabel"]("整改台账（只补责任落实，不改判定结论）"))
        self.tbl_findings = q["QTableWidget"](0, 7)
        self.tbl_findings.setHorizontalHeaderLabels(
            ["编号", "检查项", "风险级", "责任人", "期限", "状态", "整改建议"])
        self.tbl_findings.itemChanged.connect(self._on_finding_edited)
        layout.addWidget(self.tbl_findings)
        self._editing = False
        page.setLayout(layout)
        return page

    # -- 页签 4：报告导出 -------------------------------------------------
    def _build_report_tab(self):
        q = self.q
        page = q["QWidget"]()
        layout = q["QVBoxLayout"]()

        form = q["QFormLayout"]()
        self.cmb_template = q["QComboBox"]()
        self.cmb_template.addItems(["self", "third_party"])
        self.ed_report_out = q["QLineEdit"]()
        btn_out = q["QPushButton"]("选择输出路径…")
        btn_out.clicked.connect(self._choose_report_out)
        row = q["QHBoxLayout"]()
        row.addWidget(self.ed_report_out)
        row.addWidget(btn_out)
        form.addRow("模板", self.cmb_template)
        form.addRow("输出路径", row)
        layout.addLayout(form)

        bar = q["QHBoxLayout"]()
        for label, slot in (("导出报告", self._export_report),
                            ("导出底稿", self._export_draft),
                            ("导出台账 CSV", self._export_ledger)):
            b = q["QPushButton"](label)
            b.clicked.connect(slot)
            bar.addWidget(b)
        layout.addLayout(bar)

        self.txt_log = q["QTextEdit"]()
        self.txt_log.setReadOnly(True)
        layout.addWidget(self.txt_log)
        page.setLayout(layout)
        return page

    # -- 交互 -------------------------------------------------------------
    def _choose_ruleset(self):
        q = self.q
        path, _ = q["QFileDialog"].getOpenFileName(self.win, "选择规则包", "", "JSON (*.json)")
        if not path:
            return
        try:
            rs = self.session.load_ruleset(path)
        except Exception as exc:
            self._error("规则包不可用", exc)
            return
        self.lbl_ruleset.setText("规则包：%s@%s" % (rs.ruleset_id, rs.version))

    def _choose_card(self):
        q = self.q
        path, _ = q["QFileDialog"].getOpenFileName(self.win, "选择参数卡", "", "JSON (*.json)")
        if not path:
            return
        try:
            self.session.load_card(path)
        except Exception as exc:
            self._error("参数卡不可用", exc)
            return
        self.lbl_card.setText("参数卡：%s" % path)

    def _run(self):
        try:
            self.session.run()
        except Exception as exc:
            self._error("判定失败", exc)
            return
        self._refresh_all()

    def _choose_evidence_file(self):
        q = self.q
        path, _ = q["QFileDialog"].getOpenFileName(self.win, "选择证据文件")
        if path:
            self.ed_ev_file.setText(path)

    def _attach_evidence(self):
        try:
            ev = self.session.attach_evidence(
                self.cmb_item.currentText(), self.ed_ev_file.text(),
                collected_at=self.ed_ev_date.text(), owner=self.ed_ev_owner.text())
        except Exception as exc:
            self._error("挂证失败", exc)
            return
        self._log("已挂证 %s → %s（sha256 %s…）"
                  % (ev.evidence_id, ev.file_ref, ev.sha256[:12]))
        self._refresh_all()

    def _on_finding_edited(self, item):
        """表格编辑 → 回写台账（只写 owner/due/status 三列）。"""
        if self._editing:
            return
        col = item.column()
        field = {3: "owner", 4: "due", 5: "status"}.get(col)
        if not field:
            return
        row = item.row()
        fid = self.tbl_findings.item(row, 0).text()
        try:
            self.session.set_ledger([{"finding_id": fid, field: item.text()}])
        except Exception as exc:
            self._error("台账填写失败", exc)
            return
        self._log("台账更新 %s.%s = %s" % (fid, field, item.text()))

    def _choose_report_out(self):
        q = self.q
        path, _ = q["QFileDialog"].getSaveFileName(
            self.win, "选择报告输出路径", "", "报告 (*.md *.docx *.xlsx)")
        if path:
            self.ed_report_out.setText(path)

    def _export_report(self):
        try:
            out = self.session.export_report(
                self.ed_report_out.text(), template=self.cmb_template.currentText())
        except Exception as exc:
            self._error("报告导出失败", exc)
            return
        self._log("报告已写出：%s" % out)

    def _export_draft(self):
        q = self.q
        path, _ = q["QFileDialog"].getSaveFileName(self.win, "导出底稿", "", "JSON (*.json)")
        if not path:
            return
        try:
            digest = self.session.export_draft(path)
        except Exception as exc:
            self._error("底稿导出失败", exc)
            return
        self._log("底稿已导出：%s（draft_sha256 %s）" % (path, digest))

    def _export_ledger(self):
        q = self.q
        path, _ = q["QFileDialog"].getSaveFileName(self.win, "导出台账 CSV", "", "CSV (*.csv)")
        if not path:
            return
        try:
            self.session.ledger_csv(path)
        except Exception as exc:
            self._error("台账导出失败", exc)
            return
        self._log("台账已导出：%s" % path)

    # -- 呈现 -------------------------------------------------------------
    def _refresh_all(self):
        self._fill_threshold()
        self._fill_checklist()
        self._fill_evidence()
        self._fill_findings()
        self._fill_items()

    def _fill_threshold(self):
        v = self.session.threshold_view()
        self.lbl_summary.setText(
            "是否命中门槛：%s    频次：%s    结论：%s"
            % ("是" if v["triggered"] else "否", v["frequency"] or "—",
               "、".join(v["conclusions"]) or "—"))
        rows = [["无条件义务", o.get("conclusion", ""), (o.get("clause") or {}).get("point", ""),
                 _clause(o.get("clause") or {})] for o in v["obligations"]]
        rows += [["条件触发（可要求）", c.get("conclusion", ""),
                  (c.get("clause") or {}).get("point", ""), _clause(c.get("clause") or {})]
                 for c in v["conditional_triggers"]]
        self._fill_table(self.tbl_threshold, rows)

    def _fill_checklist(self):
        rows = [[r["item_id"], r["category"], r["state"], r["note"], r["basis"], r["article"]]
                for r in self.session.checklist_rows()]
        self._fill_table(self.tbl_checklist, rows)

    def _fill_evidence(self):
        rows = [[r["evidence_id"], r["item_id"], r["source"], r["collected_at"],
                 r["owner"], r["sha256"]] for r in self.session.evidence_rows()]
        self._fill_table(self.tbl_evidence, rows)

    def _fill_findings(self):
        rows = [[r["finding_id"], r["title"], r["risk"], r["owner"], r["due"],
                 r["status"], r["recommendation"]] for r in self.session.findings_rows()]
        self._editing = True
        self._fill_table(self.tbl_findings, rows)
        self._editing = False

    def _fill_items(self):
        current = self.cmb_item.currentText()
        self.cmb_item.clear()
        self.cmb_item.addItems(self.session.item_ids())
        if current:
            self.cmb_item.setCurrentText(current)

    def _fill_table(self, table, rows):
        q = self.q
        table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, value in enumerate(row):
                table.setItem(i, j, q["QTableWidgetItem"](str(value)))

    def _log(self, text):
        self.txt_log.append(text)

    def _error(self, title, exc):
        q = self.q
        q["QMessageBox"].warning(self.win, title, str(exc))
        self._log("[%s] %s" % (title, exc))


def _clause(cl):
    return "%s %s" % (cl.get("basis", ""), cl.get("article", ""))


def build_window():
    """构建主窗口（四页签：触发判定 / 检查单 / 证据链 / 报告导出）。"""
    return MainWindow().win


def main(argv=None):
    """GUI 入口：返回退出码。"""
    QApplication = _qt()["QApplication"]
    app = QApplication.instance() or QApplication(argv or [])
    win = build_window()
    win.resize(1080, 720)
    win.show()
    return app.exec()
