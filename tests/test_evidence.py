"""证据链：sha256 指纹 + 底稿导出/导入（FR-3）。

M3 补齐：导入校验 schema_version / ruleset_id 不匹配的**显式报错**，
以及"导入底稿重算结论 == 导出前结论"的往返一致性断言。
"""

import json

import pytest

from paudit.engine.pipeline import AuditRequest, compute_audit
from paudit.evidence import (
    DRAFT_SCHEMA_VERSION,
    Evidence,
    DraftError,
    attach_evidence,
    draft_body_digest,
    draft_conclusion,
    draft_ruleset_id,
    export_draft,
    has_item,
    import_draft,
    sha256_bytes,
    sha256_file,
    verify_draft_consistency,
    verify_evidence_record,
)


def test_sha256_file_and_bytes(tmp_path):
    p = tmp_path / "e.txt"
    p.write_bytes(b"hello")
    assert sha256_file(p) == sha256_bytes(b"hello")
    assert len(sha256_file(p)) == 64


def test_evidence_dict_roundtrip():
    ev = Evidence("EV-0001", "s", "2026-10-01", "owner", "f.png", 10, "a" * 64)
    assert Evidence.from_dict(ev.to_dict()).to_dict() == ev.to_dict()


def test_attach_evidence_fingerprint(tmp_path):
    f = tmp_path / "shot.png"
    f.write_bytes(b"\x89PNG fake")
    draft = {"item_results": [{"item_id": "C1", "state": "noncompliant"}]}
    ev = attach_evidence(draft, "C1", str(f), source="截图", collected_at="2026-10-01",
                         owner="审计员A")
    assert ev.sha256 == sha256_file(f)
    assert draft["item_results"][0]["evidence"][0]["evidence_id"] == "EV-0001"
    # 路径不入底稿正文（脱敏纪律：仅登记文件名）
    assert draft["item_results"][0]["evidence"][0]["file_ref"] == "shot.png"
    assert verify_evidence_record(draft["item_results"][0]["evidence"][0], str(f))


def test_attach_evidence_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        attach_evidence({"item_results": []}, "C1", str(tmp_path / "nope.png"))


def test_attach_evidence_numbers_sequentially(tmp_path):
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_bytes(b"a")
    b.write_bytes(b"b")
    draft = {"item_results": [{"item_id": "C1", "state": "partial"}]}
    assert attach_evidence(draft, "C1", str(a)).evidence_id == "EV-0001"
    assert attach_evidence(draft, "C1", str(b)).evidence_id == "EV-0002"


def test_has_item(tmp_path):
    draft = {"item_results": [{"item_id": "C1"}]}
    assert has_item(draft, "C1") is True
    assert has_item(draft, "CX") is False


def test_export_import_draft_roundtrip(tmp_path):
    draft = {"audit_scope": {"subject": "示例"}, "item_results": [], "findings": []}
    out = tmp_path / "draft.json"
    digest = export_draft(draft, out)
    assert len(digest) == 64
    assert (tmp_path / "draft.evidence.json").is_file()
    loaded = import_draft(out)
    assert loaded["audit_scope"]["subject"] == "示例"
    assert "draft_sha256" not in loaded


def test_export_writes_schema_version(tmp_path):
    out = tmp_path / "draft.json"
    export_draft({"item_results": []}, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["schema_version"] == DRAFT_SCHEMA_VERSION


def test_import_detects_tampering(tmp_path):
    out = tmp_path / "draft.json"
    export_draft({"audit_scope": {"subject": "A"}, "item_results": []}, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    data["audit_scope"]["subject"] = "B"  # 篡改
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
    with pytest.raises(ValueError):
        import_draft(out)


def test_import_rejects_schema_version_mismatch(tmp_path):
    """schema_version 不匹配 → 显式报错（不静默降级）。"""
    out = tmp_path / "draft.json"
    export_draft({"item_results": []}, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    data["schema_version"] = "0.9"
    data["draft_sha256"] = draft_body_digest(data)  # 重算自指纹，隔离 schema 校验
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
    with pytest.raises(ValueError) as exc:
        import_draft(out, expect_schema_version=DRAFT_SCHEMA_VERSION)
    assert "schema_version" in str(exc.value)


def test_import_rejects_ruleset_mismatch(tmp_path):
    out = tmp_path / "draft.json"
    export_draft({"ruleset_id": "pipl-audit-2025", "item_results": []}, out)
    with pytest.raises(ValueError) as exc:
        import_draft(out, expect_ruleset_id="pipl-audit-demo")
    assert "ruleset_id" in str(exc.value)


def test_import_missing_file_is_draft_error(tmp_path):
    with pytest.raises(DraftError):
        import_draft(tmp_path / "nope.json")


def test_draft_ruleset_id_reads_flat_and_nested():
    assert draft_ruleset_id({"ruleset_id": "x"}) == "x"
    assert draft_ruleset_id({"ruleset": {"ruleset_id": "y"}}) == "y"
    assert draft_ruleset_id({}) == ""


def test_export_is_byte_stable(tmp_path):
    """相同输入两次导出逐字节一致（确定性纪律）。"""
    draft = {"audit_scope": {"subject": "X"}, "item_results": []}
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    export_draft(draft, a)
    export_draft(draft, b)
    assert a.read_bytes() == b.read_bytes()


# ---------------------------------------------------------------------------
# 往返一致性：导入底稿重算结论 == 导出前结论（M3 门）
# ---------------------------------------------------------------------------
def _audit(demo_ruleset, demo_card):
    return compute_audit(
        AuditRequest(demo_card["input_card"], demo_card["manual_results"],
                     demo_card["audit_scope"]), demo_ruleset).to_dict()


def test_draft_roundtrip_recompute_matches(demo_ruleset, demo_card, tmp_path):
    """底稿自足（含 input_card/manual_results）→ 离线重算结论一致。"""
    draft = _audit(demo_ruleset, demo_card)
    out = tmp_path / "draft.json"
    export_draft(draft, out)
    loaded = import_draft(out, expect_ruleset_id=demo_ruleset.ruleset_id,
                          expect_schema_version=DRAFT_SCHEMA_VERSION)
    ok, detail = verify_draft_consistency(loaded, demo_ruleset)
    assert ok, detail
    assert draft_conclusion(loaded) == draft_conclusion(draft)


def test_roundtrip_consistency_survives_evidence_and_ledger(demo_ruleset, demo_card, tmp_path):
    """挂证与填台账不改变判定结论 → 往返一致仍成立。"""
    draft = _audit(demo_ruleset, demo_card)
    f = tmp_path / "e.txt"
    f.write_bytes(b"evidence")
    target = draft["item_results"][0]["item_id"]
    attach_evidence(draft, target, str(f), owner="审计员A")
    for fnd in draft["findings"]:
        fnd["owner"] = "责任人"
        fnd["due"] = "2026-12-31"
        fnd["status"] = "in_progress"
    out = tmp_path / "draft.json"
    export_draft(draft, out)
    loaded = import_draft(out)
    ok, detail = verify_draft_consistency(loaded, demo_ruleset)
    assert ok, detail


def test_roundtrip_consistency_detects_conclusion_drift(demo_ruleset, demo_card, tmp_path):
    """结论被篡改（且重算了自指纹）→ 往返一致性断言仍能检出。"""
    draft = _audit(demo_ruleset, demo_card)
    draft["summary"] = "compliant"  # 与输入重算结果不符
    out = tmp_path / "draft.json"
    export_draft(draft, out)
    loaded = import_draft(out, expect_ruleset_id=demo_ruleset.ruleset_id)
    ok, detail = verify_draft_consistency(loaded, demo_ruleset)
    assert not ok
    assert "summary" in detail
