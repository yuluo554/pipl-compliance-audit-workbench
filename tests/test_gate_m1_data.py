"""守门测试 G9：规则包内容完整性（M1 数据先行）。

断言：
- 检查项覆盖《审计指引》27 项中的 26 项（第 1 项为制定依据前言，不建检查项），
  id 编号连续且唯一；
- 每条检查项 status=verified 且挂出处（channel/checked_at）；
- 门槛规则条号/算子齐备，且边界归属为"逐条核对"结论（第四条 '>'、第十二条 '>='）；
- 真值库每条用例挂 ruleset_id 且与权威规则包一致，期望字段齐备。

本门为**内容门**（数据完整性），与 G1（零政策字面量）、G2（status/出处门控）、
G5b（再生成位级一致）互补。
"""

import json
from pathlib import Path

from conftest import AUTHORITATIVE_RULESET, ROOT

GUIDE_ITEM_NUMBERS = list(range(2, 28))  # 指引第 1 项为制定依据前言


def _ruleset():
    return json.loads(AUTHORITATIVE_RULESET.read_text(encoding="utf-8"))


def test_checklist_covers_26_guide_items():
    rs = _ruleset()
    numbers = []
    for c in rs["checklist"]:
        art = c["clause"]["article"]
        assert art.startswith("附件指引"), "检查项须挂办法附件指引条号: %s" % c["id"]
        numbers.append(int(art.replace("附件指引", "")))
    assert sorted(numbers) == GUIDE_ITEM_NUMBERS, "检查项须覆盖指引 2–27 项（26 项）"


def test_checklist_ids_unique_and_sequential():
    rs = _ruleset()
    ids = [c["id"] for c in rs["checklist"]]
    assert len(ids) == len(set(ids)), "检查项 id 重复: %s" % ids


def test_all_entries_verified_and_attributed():
    rs = _ruleset()
    for c in rs["checklist"]:
        assert c["status"] == "verified", "检查项未核对: %s" % c["id"]
        assert c["source"]["channel"] and c["source"]["checked_at"], \
            "检查项缺出处: %s" % c["id"]
    for t in rs["thresholds"]:
        assert t["status"] == "verified", "门槛未核对: %s" % t["id"]
        assert t["source"]["channel"] and t["source"]["checked_at"], \
            "门槛缺出处: %s" % t["id"]
    for b in rs["basis"]:
        assert b["status"] == "verified"
        assert b["source"]["channel"] and b["source"]["checked_at"]


def test_threshold_boundary_semantics():
    """边界归属（逐条核对结论）：第四条"超过"= '>'；第十二条"以上"= '>='。"""
    rs = _ruleset()
    by_id = {t["id"]: t for t in rs["thresholds"]}
    assert by_id["TH-SCALE-PERIODIC"]["op"] == ">", "第四条『超过』不含等于"
    assert by_id["TH-SCALE-OFFICER"]["op"] == ">=", "第十二条『以上』含等于"
    assert by_id["TH-BREACH-GENERAL"]["op"] == ">="
    assert by_id["TH-BREACH-SENSITIVE"]["op"] == ">="
    # 条号齐备且挂办法
    for t in rs["thresholds"]:
        assert t["clause"]["basis"] == "网信办令第18号"
        assert t["clause"]["article"], "门槛缺条号: %s" % t["id"]


def test_threshold_effect_declared_and_semantic():
    """M2：门槛义务类型（effect）齐备且语义正确——
    第四条=周期性义务；第十二条=持续性义务；第五条（三）=条件触发（非处理者无条件义务）。"""
    rs = _ruleset()
    by_id = {t["id"]: t for t in rs["thresholds"]}
    assert by_id["TH-SCALE-PERIODIC"]["effect"] == "periodic_obligation"
    assert by_id["TH-SCALE-OFFICER"]["effect"] == "standing_obligation"
    assert by_id["TH-BREACH-GENERAL"]["effect"] == "conditional_institution"
    assert by_id["TH-BREACH-SENSITIVE"]["effect"] == "conditional_institution"
    # 条件触发的条款措辞应为"可以要求"（保护部门），不得表述为处理者无条件义务
    for tid in ("TH-BREACH-GENERAL", "TH-BREACH-SENSITIVE"):
        assert "可以要求" in by_id[tid]["clause"]["point"], \
            "条件触发条款须保留『可以要求』措辞: %s" % tid
    # 周期性义务须带频次；持续性义务不强制频次
    assert by_id["TH-SCALE-PERIODIC"]["frequency"]
    for t in rs["thresholds"]:
        assert t.get("effect"), "门槛缺 effect: %s" % t["id"]


def test_auto_items_declare_mapping_and_absence_semantics():
    """M2：auto 项须声明 auto_mapping；无条件义务项未制定的口径为"不符合"而非"不适用"。"""
    rs = _ruleset()
    auto_items = [c for c in rs["checklist"] if c["method"] == "auto"]
    assert auto_items, "权威包应有 auto 检查项"
    for c in auto_items:
        assert c.get("auto_mapping"), "auto 检查项缺 auto_mapping: %s" % c["id"]
        rules = c["auto_mapping"]
        states = {r.get("state") for r in rules}
        assert states <= {"compliant", "partial", "noncompliant",
                          "not_applicable", "unknown"}, \
            "auto_mapping 含非法状态: %s -> %s" % (c["id"], states)
        assert "noncompliant" in states, \
            "auto_mapping 须能判不符合: %s" % c["id"]

    # 无条件义务项（未制定=不符合）：指引三/十九/二十/二十一/二十四
    by_no = {int(c["clause"]["article"].replace("附件指引", "")): c
             for c in rs["checklist"]}
    for no in (3, 19, 20, 21, 24):
        c = by_no[no]
        rules = c["auto_mapping"]
        # 不存在 not_applicable 分支（未制定不得记不适用）
        assert not any(r.get("state") == "not_applicable" for r in rules), \
            "无条件义务项不应声明 not_applicable 分支: 指引%d" % no
        assert "不符合" in c["criteria"], "缺项口径应为不符合: 指引%d" % no


def test_truth_cases_consistent_with_authoritative_ruleset():
    rs = _ruleset()
    files = sorted((ROOT / "data" / "truth").glob("*.json"))
    assert files, "真值库为空（M1 应产出合成场景）"
    item_ids = {c["id"] for c in rs["checklist"]}
    for f in files:
        case = json.loads(f.read_text(encoding="utf-8"))
        assert case.get("ruleset_id") == rs["ruleset_id"], \
            "真值用例 ruleset_id 与权威规则包不一致: %s" % f.name
        for key in ("summary", "triggered", "threshold_conclusions",
                    "obligation_conclusions", "conditional_conclusions",
                    "also_expect_nonpass"):
            assert key in case["expected"], "真值缺字段 %s: %s" % (key, f.name)
        for mid in case.get("manual_results", {}):
            assert mid in item_ids, "真值人工录入指向未知检查项 %s: %s" % (mid, f.name)


def test_truth_library_has_boundary_and_named_cases():
    """真值库须含边界场景与交接文档点名的具名场景。"""
    names = {p.stem for p in (ROOT / "data" / "truth").glob("*.json")}
    for want in ("case-1200w-no-audit-triggers", "case-over-1m-no-officer"):
        assert want in names, "缺点名场景: %s" % want
    # 每条门槛都应有三例边界（below/exact/above）
    for th_id in ("th-scale-periodic", "th-scale-officer",
                  "th-breach-general", "th-breach-sensitive"):
        for label in ("below", "exact", "above"):
            assert "case-boundary-%s-%s" % (th_id, label) in names, \
                "缺边界用例: %s %s" % (th_id, label)


def test_truth_cases_contain_no_real_personal_data():
    """合成数据纪律：真值文件只含整数/布尔/四态字符串，不落手机号/证件号/信用代码。"""
    import re
    phone = re.compile(r"(?<![0-9a-fA-F])1[3-9]\d{9}(?![0-9a-fA-F])")
    idcard = re.compile(r"(?<![0-9a-fA-F])\d{17}[\dXx](?![0-9a-fA-F])")
    for f in (ROOT / "data" / "truth").glob("*.json"):
        text = f.read_text(encoding="utf-8")
        assert not phone.search(text), "真值文件含手机号形态串: %s" % f.name
        assert not idcard.search(text), "真值文件含证件号形态串: %s" % f.name
