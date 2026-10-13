"""仓库守门：脱敏审计器 selftest + tracked 扫描常驻（随全量测试运行）。"""

import subprocess
import sys
from pathlib import Path

from conftest import ROOT

AUDIT = ROOT / "tools" / "audit_desensitize.py"


def _run(mode):
    return subprocess.run([sys.executable, str(AUDIT), mode],
                          capture_output=True, text=True, cwd=str(ROOT))


def test_desensitize_selftest_positive_and_negative():
    """阳性对照：合成假样本必须被检出；阴性对照：hex/noreply 不得误报。"""
    r = _run("selftest")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SELFTEST OK" in r.stdout


def test_desensitize_tracked_clean():
    """已跟踪文件 HARD 0 命中。"""
    r = _run("tracked")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "DESSENSITIZE_AUDIT_OK" in r.stdout


def test_frozen_ruleset_has_basis_entries(demo_ruleset):
    assert demo_ruleset.basis, "规则包必须含依据清单（报告头坐标）"


def test_data_ledger_exists(root):
    assert (root / "data" / "README.md").is_file()
