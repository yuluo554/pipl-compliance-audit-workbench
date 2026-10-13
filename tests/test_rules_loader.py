"""规则加载器 + status 门控（G2）+ 出处门控（G2b：verified 必须可追溯）。"""

import json

import pytest

from conftest import AUTHORITATIVE_RULESET, DEMO_RULESET
from paudit.errors import PendingEntryError, RulesetError, UnattributedEntryError
from paudit.rules.loader import effective_ruleset, load_ruleset
from paudit.rules.model import (
    STATUS_PENDING,
    STATUS_VERIFIED,
    CheckItem,
    Clause,
    Ruleset,
    Source,
    Threshold,
)


def _pending_ruleset():
    """合成含 pending 条目的规则包（不依赖权威包状态）。"""
    return Ruleset.from_dict({
        "ruleset_id": "x",
        "thresholds": [{"id": "T1", "param": "scale", "op": ">", "value": 1,
                        "conclusion": "c", "frequency": "", "clause": {"basis": "b", "article": "a"},
                        "status": STATUS_PENDING}],
        "checklist": [{"id": "C1", "clause": {"basis": "b", "article": "a"},
                       "method": "manual", "status": STATUS_PENDING}],
    })


def test_load_demo_ruleset(demo_ruleset):
    assert demo_ruleset.ruleset_id == "pipl-audit-demo"
    assert demo_ruleset.thresholds and demo_ruleset.checklist


def test_effective_gate_rejects_pending():
    """G2：status=pending 条目被拒，不得进入判定路径。"""
    with pytest.raises(PendingEntryError):
        effective_ruleset(_pending_ruleset())


def test_pending_entries_lists_both_kinds():
    assert _pending_ruleset().pending_entries() == ["threshold:T1", "checklist:C1"]


def test_effective_gate_rejects_unattributed_verified():
    """G2b：status=verified 但缺出处（channel/checked_at）→ 拒绝（不可追溯的"已核对"不生效）。"""
    rs = Ruleset.from_dict({
        "ruleset_id": "x",
        "thresholds": [{"id": "T1", "param": "scale", "op": ">", "value": 1,
                        "conclusion": "c", "frequency": "", "clause": {"basis": "b", "article": "a"},
                        "status": STATUS_VERIFIED, "source": {"channel": "", "checked_at": ""}}],
        "checklist": [],
    })
    assert rs.unattributed_entries() == ["threshold:T1"]
    with pytest.raises(UnattributedEntryError):
        effective_ruleset(rs)


def test_verified_with_channel_only_is_attributed():
    """出处口径：channel + checked_at 必填，url 可空（标准全文公开页需登录）。"""
    rs = Ruleset.from_dict({
        "ruleset_id": "x",
        "thresholds": [{"id": "T1", "param": "scale", "op": ">", "value": 1,
                        "conclusion": "c", "frequency": "", "clause": {"basis": "b", "article": "a"},
                        "status": STATUS_VERIFIED,
                        "source": {"channel": "cac.gov.cn", "url": "", "checked_at": "2026-10-13"}}],
        "checklist": [],
    })
    assert rs.unattributed_entries() == []
    assert effective_ruleset(rs) is rs


def test_authoritative_ruleset_is_effective_after_m1():
    """M1 后：权威规则包条目全部 verified 且挂出处 → 通过生效门。"""
    rs = load_ruleset(str(AUTHORITATIVE_RULESET))
    assert rs.pending_entries() == []
    assert rs.unattributed_entries() == []


def test_allow_pending_preview():
    """CLI 预览通路：allow_pending=True 可加载但标注 pending。"""
    rs = load_ruleset(str(AUTHORITATIVE_RULESET), allow_pending=True)
    assert rs.ruleset_id == "pipl-audit-2025"


def test_load_verified_only_when_all_verified():
    """全 verified 规则包应能通过生效门。"""
    rs = load_ruleset(str(DEMO_RULESET))
    assert rs.pending_entries() == []


def test_missing_rules_dir(tmp_path):
    with pytest.raises(RulesetError):
        load_ruleset(str(tmp_path))


def test_bad_json(tmp_path):
    p = tmp_path / "ruleset-bad.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(RulesetError):
        load_ruleset(str(p))


def test_missing_ruleset_id(tmp_path):
    p = tmp_path / "ruleset-noid.json"
    p.write_text(json.dumps({"schema_version": "1.0"}), encoding="utf-8")
    with pytest.raises(RulesetError):
        load_ruleset(str(p), allow_pending=True)
