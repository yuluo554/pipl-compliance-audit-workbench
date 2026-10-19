"""CLI 退出码语义（定稿后锁进测试，不得漂移）。

  0 = 完成/达标；1 = 检出非合规或未评估 / 基准未达标；2 = 输入不可用/用法错误；3 = 缺可选依赖。
"""

import json

import pytest

from conftest import AUTHORITATIVE_RULESET, DEMO_CARD, DEMO_RULESET
from paudit.cli import main


def test_check_demo_noncompliant_exit1(tmp_path, capsys):
    out = tmp_path / "draft.json"
    rc = main(["check", str(DEMO_CARD), "--ruleset", str(DEMO_RULESET), "--out", str(out)])
    assert rc == 1  # 检出非合规
    assert out.is_file()
    assert json.loads(out.read_text(encoding="utf-8"))["item_results"]


def test_check_missing_input_exit2():
    assert main(["check", "no/such/file.json"]) == 2


def test_check_authoritative_not_assessed_exit1(tmp_path, capsys):
    """M1 后权威规则包已生效；示例卡对权威检查单多为未观测 → 未评估 → exit 1。"""
    out = tmp_path / "draft.json"
    rc = main(["check", str(DEMO_CARD), "--out", str(out)])
    assert rc == 1
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["summary"] == "not_assessed"


def test_check_preview_flag_still_works(tmp_path, capsys):
    """--preview 仅预览（不做 pending 拦截），判定照跑。"""
    out = tmp_path / "draft.json"
    rc = main(["check", str(DEMO_CARD), "--ruleset", str(AUTHORITATIVE_RULESET),
               "--preview", "--out", str(out)])
    assert rc in (0, 1)
    assert out.is_file()


def test_no_command_exit2():
    assert main([]) == 2


def test_bench_authoritative_passes_after_m1():
    """M1 后权威规则包生效 → 基准可跑且达标 → exit 0。"""
    assert main(["bench"]) == 0


def test_bench_json_exposes_gate_metrics(capsys):
    """M4：`bench --json` 须给出三项门指标 + 样本量 + 门值。"""
    assert main(["bench", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    m = data["metrics"]
    for key in ("trigger_accuracy", "state_accuracy", "false_positive_rate"):
        assert key in m, "缺门指标: %s" % key
    assert m["false_positive_rate"] == 0
    assert data["gates"]["false_positive_rate"] == 0


def test_bench_exit1_when_metrics_below_gate(monkeypatch):
    """门指标未过门 → exit 1（即便套件无失败）。"""
    from paudit.benchmark import runner

    real = runner.run_all

    def fake_run_all(ruleset=None):
        report = real(ruleset)
        # 人为把误报样本注入全局计数器（模拟指标未过门）
        report.suites[0].setdefault("metrics", {})["false_positive"] = 5
        report.suites[0].setdefault("metrics", {})["false_positive_samples"] = 10
        return report

    monkeypatch.setattr(runner, "run_all", fake_run_all)
    assert main(["bench"]) == 1


def test_bench_exit1_when_ruleset_not_effective(monkeypatch, capsys):
    """规则包未核对生效（pending）→ 门控拦截 → exit 1（不抛栈）。"""
    from paudit.benchmark import runner
    from paudit.errors import PendingEntryError

    def fake_run_all(ruleset=None):
        raise PendingEntryError(["threshold:TH-DEMO"])

    monkeypatch.setattr(runner, "run_all", fake_run_all)
    assert main(["bench"]) == 1
    assert "未达标" in capsys.readouterr().err


def test_report_roundtrip(tmp_path):
    draft = tmp_path / "draft.json"
    assert main(["check", str(DEMO_CARD), "--ruleset", str(DEMO_RULESET),
                 "--out", str(draft)]) == 1
    report = tmp_path / "r.md"
    rc = main(["report", str(draft), "--ruleset", str(DEMO_RULESET), "-o", str(report)])
    assert rc == 0
    assert report.is_file()
    assert report.read_text(encoding="utf-8").startswith("# 个人信息保护合规审计报告")


def test_gui_missing_extra_exit3(monkeypatch):
    """缺 PySide6 → exit 3（本机装了则打桩模拟缺依赖）。"""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("PySide6"):
            raise ImportError("simulated missing PySide6")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert main(["gui"]) == 3


# ---------------------------------------------------------------------------
# M3：证据链 / 底稿导入导出 / 整改台账（退出码语义沿用 0/1/2）
# ---------------------------------------------------------------------------
def _check_draft(tmp_path, extra=()):
    out = tmp_path / "draft.json"
    rc = main(["check", str(DEMO_CARD), "--ruleset", str(DEMO_RULESET),
               "--out", str(out)] + list(extra))
    assert rc == 1
    return out


def test_check_draft_flag_writes_self_fingerprint(tmp_path):
    out = _check_draft(tmp_path, ["--draft"])
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["draft_sha256"]
    assert data["schema_version"] == "1.0"
    assert (tmp_path / "draft.evidence.json").is_file()


def test_check_evidence_attach(tmp_path):
    ev_file = tmp_path / "ev.txt"
    ev_file.write_text("evidence body", encoding="utf-8")
    draft = tmp_path / "draft.json"
    rc = main(["check", str(DEMO_CARD), "--ruleset", str(DEMO_RULESET), "--out", str(draft),
               "--evidence", "CHK-DEMO-001=%s" % ev_file, "--evidence-owner", "审计员A"])
    assert rc == 1
    data = json.loads(draft.read_text(encoding="utf-8"))
    ev = data["item_results"][0]["evidence"][0]
    assert ev["evidence_id"] == "EV-0001"
    assert ev["file_ref"] == "ev.txt"
    assert ev["owner"] == "审计员A"
    assert len(ev["sha256"]) == 64


def test_check_evidence_unknown_item_exit2(tmp_path):
    ev_file = tmp_path / "ev.txt"
    ev_file.write_text("x", encoding="utf-8")
    rc = main(["check", str(DEMO_CARD), "--ruleset", str(DEMO_RULESET),
               "--out", str(tmp_path / "d.json"), "--evidence", "CHK-NOPE-001=%s" % ev_file])
    assert rc == 2


def test_evidence_subcommand_add_and_check(tmp_path):
    ev_file = tmp_path / "ev.txt"
    ev_file.write_text("evidence body", encoding="utf-8")
    draft = _check_draft(tmp_path)
    assert main(["evidence", str(draft), "--add", "CHK-DEMO-001=%s" % ev_file,
                 "--owner", "甲", "--date", "2026-10-01"]) == 0
    assert main(["evidence", str(draft), "--check"]) == 0
    # 篡改证据文件 → 指纹不匹配 → exit 1
    ev_file.write_text("tampered", encoding="utf-8")
    assert main(["evidence", str(draft), "--check"]) == 1


def test_evidence_check_missing_file_exit1(tmp_path, capsys):
    """证据文件缺失 ≠ 通过：计入未核对并 exit 1（与篡改同级）。"""
    ev_file = tmp_path / "ev.txt"
    ev_file.write_text("evidence body", encoding="utf-8")
    draft = _check_draft(tmp_path)
    assert main(["evidence", str(draft), "--add", "CHK-DEMO-001=%s" % ev_file]) == 0
    ev_file.unlink()
    assert main(["evidence", str(draft), "--check"]) == 1
    err = capsys.readouterr().err
    assert "未找到证据文件 1 条" in err


def test_evidence_check_is_read_only(tmp_path):
    """`--check` 无 --out 时不得写回输入：非规范格式的文件 sha256 必须不变。"""
    import hashlib

    ev_file = tmp_path / "ev.txt"
    ev_file.write_text("evidence body", encoding="utf-8")
    draft = _check_draft(tmp_path)
    assert main(["evidence", str(draft), "--add", "CHK-DEMO-001=%s" % ev_file]) == 0

    # 构造成非规范格式（indent=4），以暴露任何隐藏的规范化重写
    data = json.loads(draft.read_text(encoding="utf-8"))
    draft.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
    before = hashlib.sha256(draft.read_bytes()).hexdigest()

    assert main(["evidence", str(draft), "--check"]) == 0
    after = hashlib.sha256(draft.read_bytes()).hexdigest()
    assert before == after


def test_evidence_subcommand_no_action_exit2(tmp_path):
    draft = _check_draft(tmp_path)
    assert main(["evidence", str(draft)]) == 2


def test_draft_export_import_roundtrip_via_cli(tmp_path):
    draft = tmp_path / "draft.json"
    assert main(["check", str(DEMO_CARD), "--ruleset", str(DEMO_RULESET),
                 "--out", str(draft)]) == 1
    out = tmp_path / "exported.json"
    assert main(["draft", "export", str(draft), "-o", str(out),
                 "--ruleset", str(DEMO_RULESET)]) == 0
    assert main(["draft", "import", str(out), "--ruleset", str(DEMO_RULESET)]) == 0


def test_draft_import_ruleset_mismatch_exit2(tmp_path):
    """底稿 ruleset_id 与当前规则包不匹配 → 输入不可用（exit 2）。"""
    draft = _check_draft(tmp_path)
    out = tmp_path / "exported.json"
    assert main(["draft", "export", str(draft), "-o", str(out),
                 "--ruleset", str(DEMO_RULESET)]) == 0
    assert main(["draft", "import", str(out),
                 "--ruleset", str(AUTHORITATIVE_RULESET)]) == 2


def test_draft_import_tampered_exit2(tmp_path):
    draft = _check_draft(tmp_path)
    out = tmp_path / "exported.json"
    assert main(["draft", "export", str(draft), "-o", str(out),
                 "--ruleset", str(DEMO_RULESET)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    data["summary"] = "compliant"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
                   encoding="utf-8")
    assert main(["draft", "import", str(out), "--ruleset", str(DEMO_RULESET)]) == 2


def test_draft_import_wrong_conclusion_exit1(tmp_path):
    """自指纹重算后仍与输入不符（结论漂移）→ 往返校验失败（exit 1）。"""
    from paudit.evidence import draft_body_digest

    draft = _check_draft(tmp_path)
    out = tmp_path / "exported.json"
    assert main(["draft", "export", str(draft), "-o", str(out),
                 "--ruleset", str(DEMO_RULESET)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    data["summary"] = "compliant"  # 改结论
    data["draft_sha256"] = draft_body_digest(data)  # 同时重算自指纹以绕过篡改校验
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
                   encoding="utf-8")
    assert main(["draft", "import", str(out), "--ruleset", str(DEMO_RULESET)]) == 1


def test_draft_no_subcommand_exit2(tmp_path):
    draft = _check_draft(tmp_path)
    assert main(["draft", str(draft)]) == 2


def test_ledger_export_and_apply(tmp_path):
    draft = _check_draft(tmp_path)
    led = tmp_path / "ledger.csv"
    assert main(["ledger", str(draft), "-o", str(led)]) == 0
    text = led.read_text(encoding="utf-8")
    assert text.splitlines()[0].startswith("finding_id,")
    assert "F-001" in text

    entries = tmp_path / "apply.json"
    entries.write_text(json.dumps([
        {"finding_id": "F-001", "owner": "张三", "due": "2026-12-31",
         "status": "in_progress"}]), encoding="utf-8")
    written = tmp_path / "d2.json"
    assert main(["ledger", str(draft), "--apply", str(entries),
                 "--write-draft", str(written)]) == 0
    row = [l for l in ledger_csv_lines(written) if l.startswith("F-001,")][0]
    assert "张三" in row and "in_progress" in row


def test_ledger_bad_status_exit2(tmp_path):
    draft = _check_draft(tmp_path)
    entries = tmp_path / "bad.json"
    entries.write_text('[{"finding_id": "F-001", "status": "bogus"}]', encoding="utf-8")
    assert main(["ledger", str(draft), "--apply", str(entries)]) == 2


def test_ledger_unknown_finding_exit2(tmp_path):
    draft = _check_draft(tmp_path)
    entries = tmp_path / "bad.json"
    entries.write_text('[{"finding_id": "F-999", "owner": "x"}]', encoding="utf-8")
    assert main(["ledger", str(draft), "--apply", str(entries)]) == 2


def ledger_csv_lines(draft_path):
    """读取底稿并渲染台账 CSV 行（测试辅助）。"""
    from paudit.engine.remediation import render_ledger_csv

    data = json.loads(draft_path.read_text(encoding="utf-8"))
    return render_ledger_csv(data).splitlines()


# ---------------------------------------------------------------------------
# M5：报告导出三格式（MD/DOCX/XLSX）+ 模板两版 + 退出码语义
# ---------------------------------------------------------------------------
def test_report_exports_md_docx_xlsx(tmp_path):
    """report 子命令按扩展名分派三格式，均 exit 0 且产物非空。"""
    pytest.importorskip("docx")
    pytest.importorskip("openpyxl")
    draft = tmp_path / "draft.json"
    assert main(["check", str(DEMO_CARD), "--ruleset", str(DEMO_RULESET),
                 "--out", str(draft)]) == 1
    for ext in ("md", "docx", "xlsx"):
        out = tmp_path / ("r.%s" % ext)
        rc = main(["report", str(draft), "--ruleset", str(DEMO_RULESET),
                   "-o", str(out), "--template", "third_party"])
        assert rc == 0, "导出 .%s 失败" % ext
        assert out.is_file() and out.stat().st_size > 0


def test_report_template_variants_via_cli(tmp_path):
    draft = tmp_path / "draft.json"
    assert main(["check", str(DEMO_CARD), "--ruleset", str(DEMO_RULESET),
                 "--out", str(draft)]) == 1
    self_md = tmp_path / "self.md"
    third_md = tmp_path / "third.md"
    assert main(["report", str(draft), "--ruleset", str(DEMO_RULESET),
                 "-o", str(self_md), "--template", "self"]) == 0
    assert main(["report", str(draft), "--ruleset", str(DEMO_RULESET),
                 "-o", str(third_md), "--template", "third_party"]) == 0
    assert "企业自审版" in self_md.read_text(encoding="utf-8")
    assert "第三方机构版" in third_md.read_text(encoding="utf-8")


def test_report_unsupported_format_exit2(tmp_path):
    draft = tmp_path / "draft.json"
    assert main(["check", str(DEMO_CARD), "--ruleset", str(DEMO_RULESET),
                 "--out", str(draft)]) == 1
    assert main(["report", str(draft), "--ruleset", str(DEMO_RULESET),
                 "-o", str(tmp_path / "r.pdf")]) == 2


def test_report_missing_extra_exit3(tmp_path, monkeypatch):
    """缺 python-docx/openpyxl → exit 3（打桩模拟缺 optional extra）。"""
    import builtins

    draft = tmp_path / "draft.json"
    assert main(["check", str(DEMO_CARD), "--ruleset", str(DEMO_RULESET),
                 "--out", str(draft)]) == 1
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.split(".")[0] in ("docx", "openpyxl"):
            raise ImportError("simulated missing %s" % name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert main(["report", str(draft), "--ruleset", str(DEMO_RULESET),
                 "-o", str(tmp_path / "r.docx")]) == 3


def test_report_docx_byte_reproducible_via_cli(tmp_path):
    """同一底稿两次导出 DOCX 逐字节一致（M5 门：报告产物可复现）。"""
    pytest.importorskip("docx")
    draft = tmp_path / "draft.json"
    assert main(["check", str(DEMO_CARD), "--ruleset", str(DEMO_RULESET),
                 "--out", str(draft)]) == 1
    a = tmp_path / "a.docx"
    b = tmp_path / "b.docx"
    assert main(["report", str(draft), "--ruleset", str(DEMO_RULESET), "-o", str(a)]) == 0
    assert main(["report", str(draft), "--ruleset", str(DEMO_RULESET), "-o", str(b)]) == 0
    assert a.read_bytes() == b.read_bytes()
