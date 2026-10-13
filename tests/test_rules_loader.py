"""规则加载器 + status 门控（G2）。"""

import json

import pytest

from conftest import AUTHORITATIVE_RULESET, DEMO_RULESET
from paudit.errors import PendingEntryError, RulesetError
from paudit.rules.loader import effective_ruleset, load_ruleset
from paudit.rules.model import STATUS_PENDING, STATUS_VERIFIED, Ruleset


def test_load_demo_ruleset(demo_ruleset):
    assert demo_ruleset.ruleset_id == "pipl-audit-demo"
    assert demo_ruleset.thresholds and demo_ruleset.checklist


def test_effective_gate_rejects_pending():
    """G2：status=pending 条目被拒，不得进入判定路径。"""
    rs = load_ruleset(str(AUTHORITATIVE_RULESET), allow_pending=True)
    assert rs.pending_entries(), "权威规则包应有 pending 条目（M0 未核对）"
    with pytest.raises(PendingEntryError):
        effective_ruleset(rs)


def test_allow_pending_preview():
    """CLI 预览通路：allow_pending=True 可加载但标注 pending。"""
    rs = load_ruleset(str(AUTHORITATIVE_RULESET), allow_pending=True)
    assert rs.pending_entries()


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


def test_pending_entries_lists_both_kinds():
    rs = Ruleset.from_dict({
        "ruleset_id": "x",
        "thresholds": [{"id": "T1", "param": "scale", "op": ">", "value": 1,
                        "conclusion": "c", "frequency": "", "clause": {"basis": "b", "article": "a"},
                        "status": STATUS_PENDING}],
        "checklist": [{"id": "C1", "clause": {"basis": "b", "article": "a"},
                       "method": "manual", "status": STATUS_PENDING}],
    })
    assert rs.pending_entries() == ["threshold:T1", "checklist:C1"]
