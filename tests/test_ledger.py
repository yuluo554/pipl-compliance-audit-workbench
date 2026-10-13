"""整改台账：填写 / 导出 / 状态枚举校验（FR-4）。"""

import pytest

from paudit.engine.remediation import (
    LEDGER_FIELDS,
    LedgerError,
    apply_ledger,
    export_ledger,
    ledger_rows,
    ledger_summary,
    load_ledger,
    normalize_status,
    render_ledger_csv,
)


def _draft():
    return {
        "summary": "noncompliant",
        "findings": [
            {"finding_id": "F-002", "item_id": "C2", "title": "乙", "risk": "medium",
             "clause": {"basis": "B", "article": "条2"}, "recommendation": "r2",
             "owner": "", "due": "", "status": "open"},
            {"finding_id": "F-001", "item_id": "C1", "title": "甲", "risk": "high",
             "clause": {"basis": "B", "article": "条1"}, "recommendation": "r1",
             "owner": "", "due": "", "status": "open"},
        ],
    }


def test_apply_ledger_fills_owner_due_status():
    d = _draft()
    n = apply_ledger(d, [{"finding_id": "F-001", "owner": "张三", "due": "2026-12-31",
                          "status": "in_progress"}])
    assert n == 1
    f = {x["finding_id"]: x for x in d["findings"]}
    assert f["F-001"]["owner"] == "张三"
    assert f["F-001"]["due"] == "2026-12-31"
    assert f["F-001"]["status"] == "in_progress"
    # 未提及的条目不动
    assert f["F-002"]["owner"] == ""


def test_apply_ledger_does_not_touch_risk_or_clause():
    """台账只补责任落实，不得覆写分级与条款依据。"""
    d = _draft()
    apply_ledger(d, [{"finding_id": "F-001", "owner": "x", "risk": "low",
                      "clause": {"basis": "篡改"}}])
    f = {x["finding_id"]: x for x in d["findings"]}["F-001"]
    assert f["risk"] == "high"
    assert f["clause"]["basis"] == "B"


def test_apply_ledger_unknown_finding_raises():
    with pytest.raises(LedgerError):
        apply_ledger(_draft(), [{"finding_id": "F-999", "owner": "x"}])


def test_apply_ledger_missing_finding_id_raises():
    with pytest.raises(LedgerError):
        apply_ledger(_draft(), [{"owner": "x"}])


def test_normalize_status_rejects_unknown():
    assert normalize_status("") == "open"
    assert normalize_status("RESOLVED") == "resolved"
    with pytest.raises(LedgerError):
        normalize_status("bogus")


def test_ledger_rows_sorted_and_full():
    rows = ledger_rows(_draft())
    assert [r["finding_id"] for r in rows] == ["F-001", "F-002"]
    assert set(rows[0]) == set(LEDGER_FIELDS)
    assert rows[0]["basis"] == "B" and rows[0]["article"] == "条1"


def test_render_ledger_csv_lf_and_header():
    text = render_ledger_csv(_draft())
    assert "\r" not in text
    assert text.splitlines()[0] == ",".join(LEDGER_FIELDS)
    assert "F-001" in text and "F-002" in text


def test_export_ledger_byte_stable(tmp_path):
    d = _draft()
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    export_ledger(d, a)
    export_ledger(d, b)
    assert a.read_bytes() == b.read_bytes()


def test_load_ledger_json_list_and_wrapper(tmp_path):
    p = tmp_path / "l.json"
    p.write_text('[{"finding_id": "F-001", "owner": "a"}]', encoding="utf-8")
    assert load_ledger(p) == [{"finding_id": "F-001", "owner": "a"}]
    p2 = tmp_path / "l2.json"
    p2.write_text('{"entries": [{"finding_id": "F-002", "owner": "b"}]}', encoding="utf-8")
    assert load_ledger(p2)[0]["finding_id"] == "F-002"


def test_load_ledger_csv(tmp_path):
    p = tmp_path / "l.csv"
    p.write_text("finding_id,owner,due,status\nF-001,甲,2026-12-31,in_progress\n",
                 encoding="utf-8")
    rows = load_ledger(p)
    assert rows == [{"finding_id": "F-001", "owner": "甲", "due": "2026-12-31",
                     "status": "in_progress"}]


def test_load_ledger_csv_roundtrip_via_export(tmp_path):
    """导出的 CSV 可直接回读为台账条目（可填可导出的闭环）。"""
    d = _draft()
    apply_ledger(d, [{"finding_id": "F-001", "owner": "甲", "due": "2026-12-31",
                      "status": "resolved"}])
    out = tmp_path / "l.csv"
    export_ledger(d, out)
    entries = load_ledger(out)
    assert {e["finding_id"]: e for e in entries}["F-001"]["status"] == "resolved"


def test_load_ledger_bad_csv_raises(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("foo,bar\n1,2\n", encoding="utf-8")
    with pytest.raises(LedgerError):
        load_ledger(p)


def test_load_ledger_missing_file_raises(tmp_path):
    with pytest.raises(LedgerError):
        load_ledger(tmp_path / "nope.csv")


def test_ledger_summary_counts():
    d = _draft()
    apply_ledger(d, [{"finding_id": "F-001", "owner": "甲", "status": "resolved"}])
    s = ledger_summary(d)
    assert s["total"] == 2 and s["resolved"] == 1 and s["open"] == 1 and s["assigned"] == 1
