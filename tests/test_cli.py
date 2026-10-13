"""CLI 退出码语义（定稿后锁进测试，不得漂移）。

  0 = 完成/达标；1 = 检出非合规或未评估 / 基准未达标；2 = 输入不可用/用法错误；3 = 缺可选依赖。
"""

import json

from conftest import AUTHORITATIVE_RULESET, DEMO_CARD, DEMO_RULESET
from paudit.cli import main


def test_check_demo_noncompliant_exit1(tmp_path, capsys):
    out = tmp_path / "draft.json"
    rc = main(["check", str(DEMO_CARD), "--ruleset", str(DEMO_RULESET), "--out", str(out)])
    assert rc == 1  # 检出非合规
    assert out.is_file()
    assert json.loads(out.read_text(encoding="utf-8"))["item_results"]


def test_check_authoritative_pending_exit2(capsys):
    """权威规则包含 pending → 门控拦截 → 输入不可用 exit 2。"""
    rc = main(["check", str(DEMO_CARD)])
    assert rc == 2


def test_check_missing_input_exit2():
    assert main(["check", "no/such/file.json"]) == 2


def test_no_command_exit2():
    assert main([]) == 2


def test_bench_authoritative_gate_exit1():
    """规则包未生效 → 基准未达标 exit 1。"""
    assert main(["bench"]) == 1


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
