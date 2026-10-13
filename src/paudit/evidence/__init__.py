"""证据链：sha256 指纹 + 底稿导出/导入（核心层，仅标准库）。

纪律：
- 证据只登记**结构说明 + 指纹**（`file_ref` 仅文件名，路径不入底稿正文）；
- 底稿导出产物自指纹（`draft_sha256`）固化在同名 `.evidence.json` 随附文件；
- 导入时校验自指纹 + `schema_version` + `ruleset_id`，不匹配即**显式报错**（不静默降级）。
"""

import hashlib
import json
from pathlib import Path

from ..errors import InputError

DRAFT_SCHEMA_VERSION = "1.0"


class DraftError(InputError, ValueError):
    """底稿校验失败（同时是 ValueError，兼容既有调用方的捕获口径）。"""


def sha256_file(path):
    """计算文件 sha256（分块读，避免大文件整体入内存）。"""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def draft_body_digest(data):
    """底稿正文指纹：键排序 + 缩进 2 + 不含 `draft_sha256` 自身。

    导出与导入共用本函数（单一实现源），避免两侧序列化口径漂移。
    """
    payload = {k: v for k, v in data.items() if k != "draft_sha256"}
    body = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    return sha256_bytes(body.encode("utf-8"))


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


def verify_evidence_record(record, file_path):
    """核对某条证据记录的指纹与给定文件是否一致。"""
    return record.get("sha256") == sha256_file(file_path)


def has_item(draft, item_id):
    """底稿中是否存在该检查项（供 CLI 挂证前校验，防挂到未知项）。"""
    return any(it.get("item_id") == item_id for it in draft.get("item_results", []))


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
    """导出底稿：无时间戳、LF 行尾、键排序，附底稿自指纹。"""
    payload = dict(draft)
    payload["schema_version"] = DRAFT_SCHEMA_VERSION
    digest = draft_body_digest(payload)
    payload["draft_sha256"] = digest
    body = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    write_lf_text(out_path, body)
    # 随附 evidence.json：底稿产物自指纹（"底稿被改动即可检出"）
    ev_path = Path(out_path).with_suffix(".evidence.json")
    write_lf_text(ev_path, json.dumps(
        {"draft": Path(out_path).name, "sha256": digest},
        ensure_ascii=False, indent=2))
    return digest


def import_draft(path, expect_ruleset_id=None, expect_schema_version=None):
    """导入底稿并校验自指纹 + schema_version + ruleset_id（不匹配即显式报错）。"""
    p = Path(path)
    if not p.is_file():
        raise DraftError("底稿文件不存在: %s" % p)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise DraftError("底稿 JSON 解析失败: %s (%s)" % (p, exc))

    recorded = data.get("draft_sha256")
    actual = draft_body_digest(data)
    if recorded is not None and recorded != actual:
        raise DraftError("底稿指纹不匹配（文件可能被改动）")

    schema = data.get("schema_version")
    if expect_schema_version is not None and schema != expect_schema_version:
        raise DraftError("底稿 schema_version 不匹配: 期望 %s，实际 %s"
                         % (expect_schema_version, schema))

    rid = draft_ruleset_id(data)
    if expect_ruleset_id is not None and rid != expect_ruleset_id:
        raise DraftError("底稿 ruleset_id 不匹配: 期望 %s，实际 %s"
                         % (expect_ruleset_id, rid))

    data.pop("draft_sha256", None)
    return data


def draft_ruleset_id(data):
    """读底稿的规则包身份键（兼容顶层扁平与旧版嵌套 `ruleset` 形态）。"""
    if data.get("ruleset_id"):
        return data["ruleset_id"]
    nested = data.get("ruleset") or {}
    return nested.get("ruleset_id", "")


def draft_conclusion(draft):
    """底稿中可离线复核的结论指纹：汇总 + 四态计数（不含证据/台账字段）。

    只取判定结论相关字段——证据挂载与台账填写**不改变**结论，
    故"重算结论一致"断言据此比对，不受这两类编辑干扰。
    """
    return {
        "summary": draft.get("summary"),
        "counts": draft.get("counts", {}),
        "states": {it.get("item_id"): it.get("state")
                   for it in draft.get("item_results", [])},
        "threshold_triggered": (draft.get("threshold_result") or {}).get("triggered"),
    }


def verify_draft_consistency(draft, ruleset):
    """往返一致性：用底稿保存的输入重算结论，与底稿记录结论比对。

    底稿自足（保存 `input_card`/`manual_results`/`ruleset_id`）故可离线重算。
    返回 `(ok, detail)`；不一致时 detail 说明差异字段。
    """
    from ..engine.pipeline import AuditRequest, compute_audit

    recomputed = compute_audit(
        AuditRequest(draft.get("input_card", {}), draft.get("manual_results", {}),
                     draft.get("audit_scope", {})),
        ruleset).to_dict()
    expected = draft_conclusion(draft)
    actual = draft_conclusion(recomputed)
    if expected == actual:
        return True, ""
    diffs = [k for k in expected if expected[k] != actual.get(k)]
    return False, "重算结论与底稿不一致: %s" % ", ".join(diffs)
