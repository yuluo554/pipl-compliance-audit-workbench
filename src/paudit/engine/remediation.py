"""整改台账：问题分级的责任落实（责任人 / 期限 / 状态）——可填、可导出。

分级语义：风险级由**单项四态**决定（不符合→`high`、部分符合→`medium`），
分级恒挂条款依据（`findings[].clause`），台账只补"谁改、何时改、改到哪一步"，
不改判定结论（分级与依据由引擎产出，台账不得覆写）。

台账三字段（工具内部约定，非法规原文）：
- `owner`：责任人；- `due`：整改期限（`YYYY-MM-DD` 字符串）；- `status`：状态枚举。

确定性纪律：导出按 `finding_id` 升序、LF 行尾、无时间戳。
"""

import csv
import io
import json
from pathlib import Path

from ..errors import InputError

# 状态枚举（工具内部约定；`open` 为初值）
STATUS_OPEN = "open"
STATUS_IN_PROGRESS = "in_progress"
STATUS_RESOLVED = "resolved"
STATUS_WAIVED = "waived"
LEDGER_STATUSES = (STATUS_OPEN, STATUS_IN_PROGRESS, STATUS_RESOLVED, STATUS_WAIVED)

LEDGER_FIELDS = ("finding_id", "item_id", "title", "risk", "basis", "article",
                 "recommendation", "owner", "due", "status")


class LedgerError(InputError):
    """台账输入不合法。"""


def normalize_status(status):
    """归一化状态；未知状态即报错（不静默降级）。"""
    s = (status or STATUS_OPEN).strip().lower()
    if s not in LEDGER_STATUSES:
        raise LedgerError("台账状态非法: %r（可用: %s）"
                          % (status, "/".join(LEDGER_STATUSES)))
    return s


def apply_ledger(draft, entries):
    """把台账条目填进底稿 `findings`（按 `finding_id` 定位）。

    只补 `owner`/`due`/`status`；不改风险级与条款依据。
    返回更新条数；`finding_id` 未知即报错（防静默丢弃）。
    """
    findings = draft.get("findings", [])
    by_id = {f.get("finding_id"): f for f in findings}
    updated = 0
    for e in entries:
        fid = e.get("finding_id")
        if not fid:
            raise LedgerError("台账条目缺 finding_id: %r" % (e,))
        target = by_id.get(fid)
        if target is None:
            raise LedgerError("台账指向未知 finding_id: %s（底稿现有: %s）"
                              % (fid, ", ".join(sorted(by_id)) or "（无）"))
        if "owner" in e and e["owner"] is not None:
            target["owner"] = str(e["owner"])
        if "due" in e and e["due"] is not None:
            target["due"] = str(e["due"])
        if "status" in e and e["status"] is not None:
            target["status"] = normalize_status(e["status"])
        updated += 1
    return updated


def ledger_rows(draft):
    """底稿 → 台账行（按 finding_id 升序，确定性）。"""
    rows = []
    for f in sorted(draft.get("findings", []), key=lambda x: x.get("finding_id", "")):
        cl = f.get("clause", {})
        rows.append({
            "finding_id": f.get("finding_id", ""),
            "item_id": f.get("item_id", ""),
            "title": f.get("title", ""),
            "risk": f.get("risk", ""),
            "basis": cl.get("basis", ""),
            "article": cl.get("article", ""),
            "recommendation": f.get("recommendation", ""),
            "owner": f.get("owner", ""),
            "due": f.get("due", ""),
            "status": f.get("status", STATUS_OPEN),
        })
    return rows


def render_ledger_csv(draft):
    """台账渲染为 CSV 文本（LF 行尾、固定列序、按 finding_id 升序）。"""
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=LEDGER_FIELDS, lineterminator="\n")
    w.writeheader()
    for row in ledger_rows(draft):
        w.writerow(row)
    return buf.getvalue()


def export_ledger(draft, out_path):
    """导出台账 CSV（无时间戳、LF）。"""
    text = render_ledger_csv(draft)
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return out_path


def load_ledger(path):
    """读台账文件：JSON（list 或 {"entries": [...]}）或 CSV（含表头）。"""
    p = Path(path)
    if not p.is_file():
        raise LedgerError("台账文件不存在: %s" % p)
    text = p.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if stripped.startswith("[") or stripped.startswith("{"):
        try:
            data = json.loads(text)
        except ValueError as exc:
            raise LedgerError("台账 JSON 解析失败: %s (%s)" % (p, exc))
        if isinstance(data, dict):
            data = data.get("entries", [])
        if not isinstance(data, list):
            raise LedgerError("台账 JSON 须为条目数组或含 entries 数组: %s" % p)
        entries = []
        for e in data:
            if not isinstance(e, dict):
                raise LedgerError("台账条目须为对象: %r" % (e,))
            entries.append(e)
        return entries
    return _load_ledger_csv(text, p)


def _load_ledger_csv(text, p):
    rows = list(csv.DictReader(io.StringIO(text, newline="")))
    entries = []
    for r in rows:
        if not r.get("finding_id"):
            continue
        entries.append({
            "finding_id": r["finding_id"].strip(),
            "owner": (r.get("owner") or "").strip(),
            "due": (r.get("due") or "").strip(),
            "status": (r.get("status") or "").strip(),
        })
    if not entries:
        raise LedgerError("台账 CSV 无有效条目（须含 finding_id 列）: %s" % p)
    return entries


def ledger_summary(draft):
    """台账状态计数（供报告/CLI 展示，确定性）。"""
    c = {s: 0 for s in LEDGER_STATUSES}
    for f in draft.get("findings", []):
        s = f.get("status") or STATUS_OPEN
        c[s] = c.get(s, 0) + 1
    c["total"] = len(draft.get("findings", []))
    c["assigned"] = sum(1 for f in draft.get("findings", []) if f.get("owner"))
    return c
