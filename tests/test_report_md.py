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


def test_report_threshold_three_way_sections(demo_ruleset, demo_card):
    """M2：门槛结果分栏呈现（无条件义务 / 条件触发）。"""
    md = render_markdown(_draft(demo_ruleset, demo_card), demo_ruleset)
    assert "处理者义务（无条件）" in md
    assert "条件触发（保护部门可以要求）" in md


def test_report_conditional_only_case(demo_ruleset):
    """仅命中条件触发时：义务栏为空、条件栏有条目。"""
    res = compute_audit(
        AuditRequest({"scale": 0, "sensitive": False, "has_policy": True,
                      "has_consent_withdraw": True}, {}), demo_ruleset)
    md = render_markdown(res.to_dict(), demo_ruleset)
    assert "未命中无条件义务门槛" in md


# ---------------------------------------------------------------------------
# M3：证据清单 / 整改台账联动
# ---------------------------------------------------------------------------
def test_report_evidence_table_shows_attached_evidence(demo_ruleset, demo_card, tmp_path):
    from paudit.evidence import attach_evidence

    draft = _draft(demo_ruleset, demo_card)
    f = tmp_path / "ev.png"
    f.write_bytes(b"png")
    target = draft["item_results"][0]["item_id"]
    attach_evidence(draft, target, str(f), source="制度截图", collected_at="2026-10-01",
                    owner="审计员A")
    md = render_markdown(draft, demo_ruleset)
    assert "EV-0001" in md
    assert "制度截图" in md
    assert "审计员A" in md
    # 证据表的 sha256 列应出现 64 位十六进制指纹
    import re
    assert re.search(r"\| [0-9a-f]{64} \|", md)


def test_report_shows_empty_evidence_hint(demo_ruleset, demo_card):
    md = render_markdown(_draft(demo_ruleset, demo_card), demo_ruleset)
    assert "尚未挂载证据" in md


def test_report_ledger_status_localized_and_summarized(demo_ruleset, demo_card):
    from paudit.engine.remediation import apply_ledger

    draft = _draft(demo_ruleset, demo_card)
    apply_ledger(draft, [{"finding_id": "F-001", "owner": "张三",
                          "due": "2026-12-31", "status": "in_progress"}])
    md = render_markdown(draft, demo_ruleset)
    assert "张三" in md
    assert "2026-12-31" in md
    assert "整改中" in md          # 状态中文化
    assert "台账汇总" in md
