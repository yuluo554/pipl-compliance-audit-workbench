"""守门测试 G10：M3 证据链与整改接入面（防"模块有实现但未接入"回归）。

断言：
- CLI 暴露 evidence / draft / ledger 子命令与 check 的挂证/底稿开关；
- `attach_evidence`/`export_draft`/`import_draft` 均有**非测试**调用点（接入编排）；
- 导入校验含 schema_version / ruleset_id 显式报错分支；
- 整改台账字段可填可导出（LEDGER_FIELDS 含 owner/due/status）。

本门为**接入面门**：M2 收尾时 evidence 模块仅有测试调用（模块有实现但 CLI 未接），
本条守住"接入唯一编排源"这一 M3 交付，不再退化。
"""

import ast
from pathlib import Path

from conftest import ROOT

SRC = ROOT / "src" / "paudit"


def _cli_text():
    return (SRC / "cli.py").read_text(encoding="utf-8")


def test_cli_exposes_m3_subcommands():
    text = _cli_text()
    for cmd in ('sub.add_parser("evidence"', 'sub.add_parser("draft"',
                'sub.add_parser("ledger"'):
        assert cmd in text, "CLI 缺子命令: %s" % cmd
    # check 挂证 / 底稿开关
    assert '"--evidence"' in text
    assert '"--draft"' in text


def test_cli_dispatch_registers_m3():
    text = _cli_text()
    for key in ('"evidence": cmd_evidence', '"draft": cmd_draft', '"ledger": cmd_ledger'):
        assert key in text, "CLI 未注册分发: %s" % key


def _core_callers(symbol, exclude_dirs=("tests",)):
    """在 src/ 与 tools/ 下找 symbol 的调用点（排除测试）。"""
    hits = []
    for base in (ROOT / "src", ROOT / "tools"):
        for f in base.rglob("*.py"):
            text = f.read_text(encoding="utf-8")
            if symbol + "(" in text:
                hits.append(f.relative_to(ROOT))
    return hits


def test_evidence_module_is_wired_into_cli_not_only_tests():
    """attach_evidence / export_draft / import_draft 必须有非测试调用点。"""
    for symbol in ("attach_evidence", "export_draft", "import_draft"):
        hits = _core_callers(symbol)
        assert hits, "%s 无接入调用点（仍只被测试调用？）" % symbol
        assert any("cli.py" in str(h) for h in hits), \
            "%s 未接入唯一编排源（cli.py）: %s" % (symbol, hits)


def test_import_draft_validates_schema_and_ruleset():
    """导入校验须有 schema_version / ruleset_id 的不匹配分支（显式报错）。"""
    tree = ast.parse((SRC / "evidence" / "__init__.py").read_text(encoding="utf-8"))
    fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "import_draft":
            fn = node
            break
    assert fn is not None, "缺 import_draft"
    src = ast.get_source_segment(
        (SRC / "evidence" / "__init__.py").read_text(encoding="utf-8"), fn)
    assert "expect_schema_version" in src and "schema_version" in src
    assert "expect_ruleset_id" in src and "ruleset_id" in src
    assert "raise DraftError" in src, "不匹配须显式报错（不静默降级）"


def test_ledger_exposes_owner_due_status():
    from paudit.engine.remediation import LEDGER_FIELDS, LEDGER_STATUSES

    for field in ("owner", "due", "status"):
        assert field in LEDGER_FIELDS, "台账缺字段: %s" % field
    assert "open" in LEDGER_STATUSES


def test_report_reads_evidence_and_ledger():
    """报告第五节/第六节须消费台账与证据字段（联动，不留占位表）。

    M5 起报告拆为"内容源 model.py + 三个渲染器"，故断言落在**单一内容源**上
    （markdown.py 只做块→语法映射，不再直接读台账字段）。
    """
    text = (SRC / "report" / "model.py").read_text(encoding="utf-8")
    assert "ledger_summary" in text, "报告内容源未联动台账汇总"
    assert "evidence" in text and "sha256" in text, "报告内容源未消费证据指纹"
