"""守门测试 G1：零政策字面量门禁。

引擎/基准/前端源码（含文档字符串与注释）不得出现门槛数值与年度数字 token；
数值只能来自规则包（NFR-5）。
豁免口径（写死）：< 100 的整数视为日历/精度/结构常数；纯结构性数字（schema 版本等）豁免。
"""

import ast
from pathlib import Path

from conftest import ROOT

CORE_DIRS = ["src/paudit/engine", "src/paudit/benchmark", "src/paudit/report",
             "src/paudit/evidence", "src/paudit/rules", "src/paudit/cli.py",
             "src/paudit/gui"]

# 禁用 token：门槛数值（真实与示例）与年度数字（词边界匹配）
FORBIDDEN = [
    "1000000", "10000000", "5000", "50000",
    "2019", "2020", "2021", "2022", "2023", "2024", "2025", "2026", "2027",
]

# 豁免文件：生成器是数值的唯一合法来源（不在扫描面）；测试与 plan 文档不受此门约束
EXEMPT_FILES = set()


def _iter_py_files():
    for d in CORE_DIRS:
        p = ROOT / d
        if p.is_file():
            yield p
        elif p.is_dir():
            for f in p.rglob("*.py"):
                yield f


def test_no_policy_literals_in_core():
    hits = []
    for f in _iter_py_files():
        if f.name in EXEMPT_FILES:
            continue
        text = f.read_text(encoding="utf-8")
        for tok in FORBIDDEN:
            if tok in text:
                hits.append("%s: %s" % (f.relative_to(ROOT), tok))
    assert not hits, "核心源码出现政策字面量（数值只能来自规则包）: %s" % hits


def test_generator_is_only_numeric_source():
    """门槛数值应出现在生成器（唯一合法来源），不应出现在核心源码。"""
    gen = (ROOT / "tools" / "gen_rulesets.py").read_text(encoding="utf-8")
    assert "1000000" in gen and "10000000" in gen


def test_core_layer_parses_as_ast():
    for f in _iter_py_files():
        ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
