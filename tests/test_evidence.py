"""证据链：sha256 指纹 + 底稿导出/导入（FR-3）。"""

import json

import pytest

from paudit.evidence import (
    Evidence,
    attach_evidence,
    export_draft,
    import_draft,
    sha256_bytes,
    sha256_file,
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


def test_attach_evidence_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        attach_evidence({"item_results": []}, "C1", str(tmp_path / "nope.png"))


def test_export_import_draft_roundtrip(tmp_path):
    draft = {"audit_scope": {"subject": "示例"}, "item_results": [], "findings": []}
    out = tmp_path / "draft.json"
    digest = export_draft(draft, out)
    assert len(digest) == 64
    assert (tmp_path / "draft.evidence.json").is_file()
    loaded = import_draft(out)
    assert loaded["audit_scope"]["subject"] == "示例"


def test_import_detects_tampering(tmp_path):
    out = tmp_path / "draft.json"
    export_draft({"audit_scope": {"subject": "A"}, "item_results": []}, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    data["audit_scope"]["subject"] = "B"  # 篡改
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
    with pytest.raises(ValueError):
        import_draft(out)


def test_export_is_byte_stable(tmp_path):
    """相同输入两次导出逐字节一致（确定性纪律）。"""
    draft = {"audit_scope": {"subject": "X"}, "item_results": []}
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    export_draft(draft, a)
    export_draft(draft, b)
    assert a.read_bytes() == b.read_bytes()
