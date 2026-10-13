"""守门测试 G4（EOL 冻结）+ G5（再生成位级一致）+ G6（workflow 可解析）+ G7（extras 覆盖测试期 import）。"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import ROOT

# ---------------------------------------------------------------------------
# G4：冻结产物不得出现 CR 字节（跨平台基准可复现前置）
# ---------------------------------------------------------------------------
FROZEN_GLOBS = ["data/rules/*.json", "data/samples/*.json", "data/truth/*.json"]


def _frozen_files():
    for g in FROZEN_GLOBS:
        yield from ROOT.glob(g)


def test_frozen_products_have_no_cr():
    bad = []
    for f in _frozen_files():
        if b"\r" in f.read_bytes():
            bad.append(str(f.relative_to(ROOT)))
    assert not bad, "冻结产物出现 CR 字节（EOL 门）: %s" % bad


def test_gitattributes_sets_lf(root):
    text = (root / ".gitattributes").read_text(encoding="utf-8")
    assert "eol=lf" in text


# ---------------------------------------------------------------------------
# G5：生成器重跑 → 产物逐字节一致
# ---------------------------------------------------------------------------
def test_generator_regenerates_byte_identical(tmp_path):
    """把生成器产物写到临时目录，与仓库内冻结产物逐字节比对。"""
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "gen_rulesets.py"), str(tmp_path)],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr

    pairs = [
        (tmp_path / "data" / "rules" / "ruleset-pipl-audit-2025.json",
         ROOT / "data" / "rules" / "ruleset-pipl-audit-2025.json"),
        (tmp_path / "data" / "samples" / "ruleset-pipl-audit-demo.json",
         ROOT / "data" / "samples" / "ruleset-pipl-audit-demo.json"),
        (tmp_path / "data" / "samples" / "card-demo.json",
         ROOT / "data" / "samples" / "card-demo.json"),
    ]
    for fresh, frozen in pairs:
        assert fresh.read_bytes() == frozen.read_bytes(), \
            "生成器产物与冻结产物不一致，需重新生成整目录: %s" % frozen.name


def test_generator_output_is_lf(tmp_path):
    subprocess.run([sys.executable, str(ROOT / "tools" / "gen_rulesets.py"), str(tmp_path)],
                   check=True, capture_output=True)
    for f in tmp_path.rglob("*.json"):
        assert b"\r" not in f.read_bytes()


# ---------------------------------------------------------------------------
# G5b：合成场景生成器重跑 → 真值库逐字节一致
# ---------------------------------------------------------------------------
def test_scenario_generator_regenerates_byte_identical(tmp_path):
    """把真值库写到临时目录，与仓库内 data/truth/ 逐字节比对。"""
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "gen_scenarios.py"), str(tmp_path)],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr

    fresh_dir = tmp_path / "data" / "truth"
    frozen_dir = ROOT / "data" / "truth"
    fresh = {p.name: p.read_bytes() for p in sorted(fresh_dir.glob("*.json"))}
    frozen = {p.name: p.read_bytes() for p in sorted(frozen_dir.glob("*.json"))}
    assert fresh, "真值库为空：生成器未产出用例"
    assert set(fresh) == set(frozen), \
        "真值库文件集不一致，需重新生成: %s" % sorted(set(fresh) ^ set(frozen))
    for name in fresh:
        assert fresh[name] == frozen[name], "真值产物与冻结产物不一致: %s" % name


def test_scenario_generator_output_is_lf(tmp_path):
    subprocess.run([sys.executable, str(ROOT / "tools" / "gen_scenarios.py"), str(tmp_path)],
                   check=True, capture_output=True)
    for f in (tmp_path / "data" / "truth").glob("*.json"):
        assert b"\r" not in f.read_bytes()


# ---------------------------------------------------------------------------
# G6：CI workflow 可解析 + 每 job 有 runs-on/steps
# ---------------------------------------------------------------------------
def _workflows():
    return sorted((ROOT / ".github" / "workflows").glob("*.yml"))


def test_workflows_exist_and_parse():
    yaml = pytest.importorskip("yaml")
    files = _workflows()
    assert files, "缺少 CI workflow"
    for f in files:
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        assert isinstance(data, dict) and "jobs" in data, "workflow 非法: %s" % f.name
        for job_name, job in data["jobs"].items():
            assert "runs-on" in job, "%s 的 job %s 缺 runs-on" % (f.name, job_name)
            assert job.get("steps"), "%s 的 job %s 缺 steps" % (f.name, job_name)


def test_workflow_checkout_full_history():
    """脱敏/历史扫描类守门需要全量历史 → checkout 必须 fetch-depth: 0。"""
    yaml = pytest.importorskip("yaml")
    for f in _workflows():
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        for job in data["jobs"].values():
            for step in job.get("steps", []):
                if str(step.get("uses", "")).startswith("actions/checkout"):
                    with_ = step.get("with", {}) or {}
                    assert with_.get("fetch-depth") == 0, \
                        "%s 的 checkout 未取全量历史（fetch-depth: 0）" % f.name


# ---------------------------------------------------------------------------
# G7：extras 覆盖测试期 import（静态解析 pyproject）
# ---------------------------------------------------------------------------
def _toml_load(path):
    """py3.11+ 用 tomllib，py3.8 用 dev extra 的 tomli。"""
    try:
        import tomllib as mod
    except ImportError:
        import tomli as mod  # dev extra 提供
    with open(path, "rb") as fh:
        return mod.load(fh)


def test_dev_extra_declares_test_deps():
    data = _toml_load(ROOT / "pyproject.toml")
    dev = data["project"]["optional-dependencies"]["dev"]
    joined = " ".join(dev).lower()
    assert "pytest" in joined
    assert "pyyaml" in joined  # 守门测试 G6 依赖
    assert "tomli" in joined   # 守门测试 G7 在 py<3.11 依赖
