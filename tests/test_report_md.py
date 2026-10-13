"""报告渲染（FR-5）+ 免责声明（G8）。"""

from paudit import DISCLAIMER
from paudit.engine.pipeline import AuditRequest, compute_audit
from paudit.report.markdown import render_markdown


def _draft(demo_ruleset, demo_card):
    res = compute_audit(
        AuditRequest(demo_card["input_card"], demo_card["manual_results"],
                     demo_card["audit_scope"]), demo_ruleset)
    return res.to_dict()


def test_report_has_coord_and_disclaimer(demo_ruleset, demo_card):
    md = render_markdown(_draft(demo_ruleset, demo_card), demo_ruleset)
    assert "规则包坐标" in md
    assert demo_ruleset.ruleset_id in md and demo_ruleset.version in md
    assert DISCLAIMER in md


def test_report_renders_all_items(demo_ruleset, demo_card):
    """每个检查项都应出现在报告第四节（回归：曾因键名不一致为空表）。"""
    md = render_markdown(_draft(demo_ruleset, demo_card), demo_ruleset)
    for item in demo_ruleset.checklist:
        assert item.id in md


def test_report_renders_findings_and_clauses(demo_ruleset, demo_card):
    md = render_markdown(_draft(demo_ruleset, demo_card), demo_ruleset)
    assert "F-001" in md
    assert "示例依据B" in md  # 条款依据联动


def test_report_template_variants(demo_ruleset, demo_card):
    md_self = render_markdown(_draft(demo_ruleset, demo_card), demo_ruleset, template="self")
    md_third = render_markdown(_draft(demo_ruleset, demo_card), demo_ruleset,
                               template="third_party")
    assert "企业自审版" in md_self
    assert "第三方机构版" in md_third
    assert "审计机构" in md_third


def test_report_is_byte_stable(demo_ruleset, demo_card):
    d = _draft(demo_ruleset, demo_card)
    assert render_markdown(d, demo_ruleset) == render_markdown(d, demo_ruleset)
