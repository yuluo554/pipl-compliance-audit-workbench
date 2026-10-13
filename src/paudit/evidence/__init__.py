"""证据链：sha256 指纹 + 底稿导出/导入（核心层，仅标准库）。"""

import hashlib
import json
from pathlib import Path

DRAFT_SCHEMA_VERSION = "1.0"


def sha256_file(path):
    """计算文件 sha256（分块读，避免大文件整体入内存）。"""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


class Evidence:
    """单条证据（仅存结构说明与指纹，不落真实内容副本）。"""

    def __init__(self, evidence_id, source, collected_at, owner,
                 file_ref="", size=0, sha256=""):
        self.evidence_id = evidence_id
        self.source = source
        self.collected_at = collected_at
        self.owner = owner
        self.file_ref = file_ref
        self.size = size
        self.sha256 = sha256

    def to_dict(self):
        return {
            "evidence_id": self.evidence_id,
            "source": self.source,
            "collected_at": self.collected_at,
            "owner": self.owner,
            "file_ref": self.file_ref,
            "size": self.size,
            "sha256": self.sha256,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            evidence_id=d["evidence_id"],
            source=d.get("source", ""),
            collected_at=d.get("collected_at", ""),
            owner=d.get("owner", ""),
            file_ref=d.get("file_ref", ""),
            size=d.get("size", 0),
            sha256=d.get("sha256", ""),
        )


def attach_evidence(draft, item_id, file_path, source="", collected_at="", owner=""):
    """把本地文件作为证据挂到某检查项，计算 sha256 指纹。"""
    p = Path(file_path)
    if not p.is_file():
        raise FileNotFoundError("证据文件不存在: %s" % p)
    ev = Evidence(
        evidence_id=_next_evidence_id(draft),
        source=source or p.name,
        collected_at=collected_at,
        owner=owner,
        file_ref=p.name,  # 仅登记文件名，路径不入底稿正文（脱敏纪律）
        size=p.stat().st_size,
        sha256=sha256_file(p),
    )
    items = draft.setdefault("item_results", [])
    for it in items:
        if it.get("item_id") == item_id:
            it.setdefault("evidence", []).append(ev.to_dict())
            break
    else:
        items.append({"item_id": item_id, "state": "unknown", "evidence": [ev.to_dict()]})
    return ev


def _next_evidence_id(draft):
    n = 0
    for it in draft.get("item_results", []):
        n += len(it.get("evidence", []))
    return "EV-%04d" % (n + 1)


def write_lf_text(path, text):
    """写文本：LF 行尾、UTF-8（py3.8 的 Path.write_text 不支持 newline 参数）。"""
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def export_draft(draft, out_path):
    """导出底稿：无时间戳、LF 行尾，附底稿自指纹。"""
    payload = dict(draft)
    payload["schema_version"] = DRAFT_SCHEMA_VERSION
    body = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    digest = sha256_bytes(body.encode("utf-8"))
    payload["draft_sha256"] = digest
    body = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    write_lf_text(out_path, body)
    # 随附 evidence.json：底稿产物自指纹（"底稿被改动即可检出"）
    ev_path = Path(out_path).with_suffix(".evidence.json")
    write_lf_text(ev_path, json.dumps(
        {"draft": Path(out_path).name, "sha256": digest},
        ensure_ascii=False, indent=2))
    return digest


def import_draft(path):
    """导入底稿并校验自指纹。"""
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    recorded = data.pop("draft_sha256", None)
    body = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
    actual = sha256_bytes(body.encode("utf-8"))
    if recorded is not None and recorded != actual:
        raise ValueError("底稿指纹不匹配（文件可能被改动）")
    return data
