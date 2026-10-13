"""GUI 会话数据面（零 Qt，无头可测）。

`gui/session.py` 是界面的数据面，只编排引擎 API；本模块验证它
"读得对、写不越界"：判定结论来自引擎、挂证/台账不改结论、导出三格式可读回。
"""

import json

import pytest

from paudit.gui.session import Session, SessionError


def _build(demo_card, tmp_path, ruleset_path):
    card_path = tmp_path / "card.json"
    card_path.write_text(json.dumps(demo_card, ensure_ascii=False), encoding="utf-8")
    s = Session()
    s.load_ruleset(str(ruleset_path))
    s.load_card(str(card_path))
    s.run()
    return s


def test_session_run_produces_engine_draft(demo_ruleset, demo_card, tmp_path):
    from conftest import DEMO_RULESET

    s = _build(demo_card, tmp_path, DEMO_RULESET)
    assert s.draft["item_results"], "会话未产出检查项结果"
    assert s.draft["ruleset_id"] == demo_ruleset.ruleset_id


def test_threshold_view_splits_obligations(demo_ruleset, demo_card, tmp_path):
    from conftest import DEMO_RULESET

    s = _build(demo_card, tmp_path, DEMO_RULESET)
    v = s.threshold_view()
    assert set(v) >= {"triggered", "obligations", "conditional_triggers", "frequency"}
    # 分栏不得混同：无条件义务与条件触发是两组独立条目
    assert isinstance(v["obligations"], list) and isinstance(v["conditional_triggers"], list)


def test_checklist_and_findings_rows_match_draft(demo_ruleset, demo_card, tmp_path):
    from conftest import DEMO_RULESET

    s = _build(demo_card, tmp_path, DEMO_RULESET)
    assert len(s.checklist_rows()) == len(s.draft["item_results"])
    assert len(s.findings_rows()) == len(s.draft["findings"])
    assert s.item_ids() == [it["item_id"] for it in s.draft["item_results"]]


def test_attach_evidence_records_fingerprint_not_content(demo_ruleset, demo_card, tmp_path):
    from conftest import DEMO_RULESET

    s = _build(demo_card, tmp_path, DEMO_RULESET)
    ev_file = tmp_path / "ev.png"
    ev_file.write_bytes(b"fake-image-bytes")
    target = s.item_ids()[0]
    ev = s.attach_evidence(target, str(ev_file), owner="审计员A", collected_at="2026-10-01")
    assert ev.file_ref == "ev.png"          # 仅文件名，路径不入底稿
    assert len(ev.sha256) == 64
    assert s.evidence_rows()[0]["sha256"] == ev.sha256
    # 证据正文不得进底稿
    assert "fake-image-bytes" not in json.dumps(s.draft, ensure_ascii=False)


def test_attach_evidence_unknown_item_raises(demo_ruleset, demo_card, tmp_path):
    from conftest import DEMO_RULESET

    s = _build(demo_card, tmp_path, DEMO_RULESET)
    ev_file = tmp_path / "ev.txt"
    ev_file.write_text("x", encoding="utf-8")
    with pytest.raises(SessionError):
        s.attach_evidence("CHK-NOPE-999", str(ev_file))


def test_attach_evidence_does_not_change_conclusion(demo_ruleset, demo_card, tmp_path):
    """挂证不改变判定结论（M3 定稿口径，界面同样守）。"""
    from conftest import DEMO_RULESET
    from paudit.evidence import draft_conclusion

    s = _build(demo_card, tmp_path, DEMO_RULESET)
    before = draft_conclusion(s.draft)
    ev_file = tmp_path / "ev.txt"
    ev_file.write_text("x", encoding="utf-8")
    s.attach_evidence(s.item_ids()[0], str(ev_file))
    assert draft_conclusion(s.draft) == before


def test_set_ledger_only_writes_three_fields(demo_ruleset, demo_card, tmp_path):
    from conftest import DEMO_RULESET

    s = _build(demo_card, tmp_path, DEMO_RULESET)
    fid = s.findings_rows()[0]["finding_id"]
    risk_before = s.draft["findings"][0]["risk"]
    n = s.set_ledger([{"finding_id": fid, "owner": "张三", "due": "2026-12-31",
                       "status": "in_progress"}])
    assert n == 1
    row = s.findings_rows()[0]
    assert (row["owner"], row["due"], row["status"]) == ("张三", "2026-12-31", "in_progress")
    assert s.draft["findings"][0]["risk"] == risk_before  # 分级不得被台账覆写


def test_set_ledger_bad_status_raises(demo_ruleset, demo_card, tmp_path):
    from conftest import DEMO_RULESET

    s = _build(demo_card, tmp_path, DEMO_RULESET)
    fid = s.findings_rows()[0]["finding_id"]
    with pytest.raises(Exception):
        s.set_ledger([{"finding_id": fid, "status": "bogus"}])


def test_session_export_report_and_draft(demo_ruleset, demo_card, tmp_path):
    from conftest import DEMO_RULESET

    s = _build(demo_card, tmp_path, DEMO_RULESET)
    # 三格式导出依赖 report extra；缺则只验 Markdown（核心层零依赖）。
    # 本用例不整体 skip——底稿自指纹与台账 CSV 是**核心层**能力，
    # 与重件无关，装不装 extra 都必须验到。
    exts = ["md"]
    try:
        import docx  # noqa: F401
        import openpyxl  # noqa: F401
        exts += ["docx", "xlsx"]
    except ImportError:
        pass
    for ext in exts:
        out = tmp_path / ("r.%s" % ext)
        s.export_report(str(out), template="self")
        assert out.is_file() and out.stat().st_size > 0
    digest = s.export_draft(str(tmp_path / "d.json"))
    assert len(digest) == 64
    csv_path = tmp_path / "ledger.csv"
    s.ledger_csv(str(csv_path))
    assert csv_path.read_text(encoding="utf-8").splitlines()[0].startswith("finding_id,")


def test_session_before_run_raises(demo_card, tmp_path):
    from conftest import DEMO_RULESET

    card_path = tmp_path / "card.json"
    card_path.write_text(json.dumps(demo_card, ensure_ascii=False), encoding="utf-8")
    s = Session()
    s.load_ruleset(str(DEMO_RULESET))
    s.load_card(str(card_path))
    with pytest.raises(SessionError):
        s.checklist_rows()


def test_session_missing_card_raises():
    s = Session()
    with pytest.raises(SessionError):
        s.load_card("no/such/card.json")
