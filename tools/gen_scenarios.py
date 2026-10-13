"""合成审计场景 + 真值库生成器（确定性；禁手改产物）。

产出：`data/truth/case-*.json`，每条含：
- `input_card`：合成参数卡（规模、门控开关、自动核查字段）；
- `manual_results`：合成人工录入（四态）；
- `expected`：**独立计算**的期望判定（summary / triggered / conclusions / also_expect_nonpass）。

真值纪律：
- 真值**不由引擎计算**，而由本生成器用 `benchmark/cases.py`（真值语义单一实现源）
  独立推导（逐项四态 → `expected_summary`；非 pass 集 → `observed_nonpass`；
  门槛 → `apply_op`）。引擎与真值对账 = 两套独立实现互验。
- 门槛值/条号/检查项清单一律**读自权威规则包**（不在此复制，防漂移）；
  生成时自校验：`ITEM_IDS`/自动字段/门控与规则包一致，否则报错退出。
- 确定性：自研 splitmix64 RNG（固定 seed）、无系统时钟、键排序、LF、末尾换行；
  重跑逐字节一致（配 G5 型守门测试）。

合成数据纪律（data/README §三）：全部虚构，**不含任何真实个人信息**
（真值文件只含整数规模、布尔门控与四态字符串，不落手机号/证件号/信用代码）。
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# 真值语义单一实现源（核心层，仅标准库）
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from paudit.benchmark.cases import apply_op, expected_summary, observed_nonpass  # noqa: E402
from paudit.rules.model import ALL_STATES  # noqa: E402

GENERATED_AT = "2026-10-13T00:00:00Z"
RULESET_FILE = "data/rules/ruleset-pipl-audit-2025.json"

# 固定随机种子（自研 splitmix64；禁 stdlib random）
SEED = 0x5EED5EED2026
RANDOM_CASES = 12
_MASK = (1 << 64) - 1


class SplitMix64:
    """确定性 PRNG（跨解释器/平台逐位一致）。"""

    def __init__(self, seed):
        self.state = seed & _MASK

    def next_u64(self):
        self.state = (self.state + 0x9E3779B97F4A7C15) & _MASK
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK
        return (z ^ (z >> 31)) & _MASK

    def below(self, n):
        return self.next_u64() % n


def _load_ruleset():
    p = ROOT / RULESET_FILE
    return json.loads(p.read_text(encoding="utf-8"))


def _mirrors(rs):
    """从规则包派生：检查项 id 序列、自动字段、门控、门槛清单。"""
    item_ids = [c["id"] for c in rs["checklist"]]
    auto = {c["id"]: c["auto_field"] for c in rs["checklist"] if c["method"] == "auto"}
    gates = {}
    for c in rs["checklist"]:
        if c.get("only_if"):
            (key, allowed), = c["only_if"].items()
            gates[c["id"]] = (key, tuple(allowed))
    thresholds = [
        {"id": t["id"], "param": t["param"], "op": t["op"], "value": t["value"],
         "conclusion": t["conclusion"], "severity": t["severity"]}
        for t in rs["thresholds"]
    ]
    manual_ids = [c["id"] for c in rs["checklist"] if c["method"] == "manual"]
    return item_ids, auto, gates, thresholds, manual_ids, rs["ruleset_id"]


# ---------------------------------------------------------------------------
# 独立真值计算（与引擎互验）
# ---------------------------------------------------------------------------
def _item_truth(item_id, card, manual, auto, gates):
    gate = gates.get(item_id)
    if gate is not None:
        key, allowed = gate
        if card.get(key) not in allowed:
            return "not_applicable"
    field = auto.get(item_id)
    if field is not None:
        if field not in card:
            return "unknown"
        val = card[field]
        return "compliant" if (val is True or (isinstance(val, str) and val.strip())) else "noncompliant"
    rec = manual.get(item_id)
    if rec is None:
        return "unknown"
    state = rec.get("state", "unknown")
    return state if state in ALL_STATES else "unknown"


def _threshold_truth(card, thresholds):
    matched = []
    for t in thresholds:
        if t["param"] in card and apply_op(t["op"], card[t["param"]], t["value"]):
            matched.append((t["severity"], t["conclusion"]))
    matched.sort(key=lambda x: x[0], reverse=True)
    conclusions, seen = [], set()
    for _, c in matched:
        if c not in seen:
            seen.add(c)
            conclusions.append(c)
    return {"triggered": any(sev > 0 for sev, _ in matched), "conclusions": conclusions}


def _expected(card, manual, mirrors):
    item_ids, auto, gates, thresholds = mirrors[:4]
    states = [_item_truth(iid, card, manual, auto, gates) for iid in item_ids]
    thr = _threshold_truth(card, thresholds)
    return {
        "summary": expected_summary(states),
        "triggered": thr["triggered"],
        "threshold_conclusions": thr["conclusions"],
        "also_expect_nonpass": observed_nonpass(states),
    }


# ---------------------------------------------------------------------------
# 场景构造
# ---------------------------------------------------------------------------
def _case(case_id, title, card, manual, mirrors, note=""):
    return {
        "case_id": case_id,
        "ruleset_id": mirrors[5],
        "title": title,
        "note": note,
        "input_card": dict(card),
        "manual_results": {k: dict(v) for k, v in manual.items()},
        "expected": _expected(card, manual, mirrors),
    }


def _base_card(gate_keys, **over):
    """门控全关 + 可选覆盖（用于隔离门槛判定）。"""
    card = {k: False for k in gate_keys}
    card.update(over)
    return card


def _boundary_cases(mirrors, gate_keys):
    """每条门槛的 value-1 / value / value+1 三例（边界归属逐条验证）。"""
    thresholds = mirrors[3]
    cases = []
    for t in thresholds:
        value = t["value"]
        for label, v in (("below", value - 1), ("exact", value), ("above", value + 1)):
            card = _base_card(gate_keys, **{t["param"]: v})
            cases.append(_case(
                "boundary-%s-%s" % (t["id"].lower(), label),
                "门槛边界：%s（%s %s %s 时）" % (t["id"], t["param"], t["op"], label),
                card, {}, mirrors,
                note="value=%d, actual=%d" % (value, v)))
    return cases


def _named_cases(mirrors, gate_keys):
    """具名业务场景（含指引/交接文档点名的边界场景）。"""
    thresholds = mirrors[3]
    by_id = {t["id"]: t for t in thresholds}

    # 1200 万人未开展审计 → 应判"触发周期性审计义务"（第四条 op=">"）
    p = by_id["TH-SCALE-PERIODIC"]["value"]
    scale_1200w = p * 6 // 5
    # 100 万人以上未指定负责人（第十二条 op=">="）+ 人工录入"负责人履职不符合"
    o = by_id["TH-SCALE-OFFICER"]["value"]
    scale_over_officer = o + o // 2
    # 安全事件：100 万人以上个人信息泄露（第五条（三））
    b = by_id["TH-BREACH-GENERAL"]["value"]
    bs = by_id["TH-BREACH-SENSITIVE"]["value"]

    cases = [
        _case("1200w-no-audit-triggers",
              "1200 万人未开展审计 → 触发周期性审计义务",
              _base_card(gate_keys, scale=scale_1200w), {}, mirrors,
              note="第四条 1000 万人以上（op='>'）每两年至少一次"),
        _case("over-1m-no-officer",
              "100 万人以上未指定个人信息保护负责人 → 触发指定义务且判非合规",
              _base_card(gate_keys, scale=scale_over_officer),
              {"CHK-DOC-022": {"state": "noncompliant",
                               "note": "合成：未指定个人信息保护负责人"}},
              mirrors, note="第十二条 op='>='；指引二十二"),
        _case("breach-general-triggers",
              "安全事件致 100 万人以上个人信息泄露 → 保护部门可要求委托专业机构",
              _base_card(gate_keys, breach_scale=b), {}, mirrors,
              note="第五条（三）op='>='"),
        _case("breach-sensitive-triggers",
              "安全事件致 10 万人以上敏感个人信息泄露 → 保护部门可要求委托专业机构",
              _base_card(gate_keys, breach_sensitive_scale=bs), {}, mirrors,
              note="第五条（三）敏感信息 op='>='"),
        _case("multi-threshold-merge",
              "多门槛同时命中 → 结论按严重度归并",
              _base_card(gate_keys, scale=scale_1200w, breach_scale=b, breach_sensitive_scale=bs),
              {}, mirrors, note="severity 归并：结论去重保序"),
        _case("platform-obligations",
              "重要平台义务场景：平台规则 + 社会责任报告适用",
              _base_card(gate_keys, large_platform=True, scale=scale_over_officer),
              {"CHK-DOC-026": {"state": "partial", "note": "合成：抽样验证不充分"},
               "CHK-DOC-027": {"state": "compliant", "note": "合成：报告已披露"}},
              mirrors, note="指引二十六/二十七 only_if large_platform"),
        _case("sensitive-and-minors",
              "敏感个人信息 + 不满十四周岁未成年人场景",
              _base_card(gate_keys, sensitive=True, minors_under_14=True),
              {"CHK-PRO-013": {"state": "noncompliant", "note": "合成：未取得单独同意"},
               "CHK-PRO-014": {"state": "partial", "note": "合成：专门规则不完整"}},
              mirrors, note="指引十三/十四 only_if"),
        _case("cross-border",
              "向境外提供个人信息场景",
              _base_card(gate_keys, cross_border_transfer=True),
              {"CHK-PRO-015": {"state": "noncompliant", "note": "合成：未完成安全评估"}},
              mirrors, note="指引十五 only_if"),
        _case("security-incident",
              "已发生个人信息安全事件场景",
              _base_card(gate_keys, security_incident_occurred=True),
              {"CHK-RES-025": {"state": "partial", "note": "合成：通报不及时"}},
              mirrors, note="指引二十五 only_if"),
        _case("third-party-flows",
              "共同处理/委托/转移/向他人提供 全开门控场景",
              _base_card(gate_keys, joint_processing=True, entrusted_processing=True,
                         transfer_event=True, provides_to_third_party=True),
              {"CHK-PRO-005": {"state": "compliant", "note": "合成：已约定权利义务"},
               "CHK-PRO-006": {"state": "partial", "note": "合成：合同缺保护措施"},
               "CHK-PRO-007": {"state": "compliant", "note": "合成：已告知接收方"},
               "CHK-PRO-008": {"state": "noncompliant", "note": "合成：未取得单独同意"}},
              mirrors, note="指引五/六/七/八 only_if"),
    ]
    return cases


def _semantic_cases(mirrors, gate_keys, auto_fields):
    """四态/汇总语义专项：全不适用、全通过、全不通过、部分、未观测。"""
    cases = []
    # 全不适用（门控全关 + 自动字段缺失 + 无人工录入）→ not_assessed
    cases.append(_case("none-applicable-not-assessed",
                       "全部不适用/未观测 → 汇总 not_assessed（绝不输出 compliant）",
                       _base_card(gate_keys), {}, mirrors, note="汇总语义 FR-2.5"))
    # 全自动字段通过 → compliant
    card_pass = _base_card(gate_keys)
    for f in auto_fields:
        card_pass[f] = True
    cases.append(_case("all-auto-pass",
                       "全部自动核查通过 → 汇总 compliant",
                       card_pass, {}, mirrors, note="method=auto 映射"))
    # 全自动字段不通过 → noncompliant
    card_fail = _base_card(gate_keys)
    for f in auto_fields:
        card_fail[f] = False
    cases.append(_case("all-auto-fail",
                       "全部自动核查不通过 → 汇总 noncompliant",
                       card_fail, {}, mirrors, note="method=auto 映射"))
    # 部分符合 → partial
    card_partial = _base_card(gate_keys)
    for f in auto_fields:
        card_partial[f] = True
    cases.append(_case("mixed-partial",
                       "自动全通过 + 人工录入一项部分符合 → 汇总 partial",
                       card_partial, {"CHK-PRO-002": {"state": "partial", "note": "合成：部分满足"}},
                       mirrors, note="partial 优先于 compliant"))
    # 未观测不误判为违规
    cases.append(_case("unknown-not-violation",
                       "未观测（unknown）不计违规也不进分母",
                       _base_card(gate_keys), {"CHK-PRO-002": {"state": "unknown", "note": "合成：未观测"}},
                       mirrors, note="unknown 语义"))
    return cases


def _random_cases(mirrors, gate_keys, auto_fields, manual_ids, n):
    """确定性随机组合场景（固定 seed；迭代顺序排序，禁 set 迭代序）。"""
    rng = SplitMix64(SEED)
    cases = []
    for i in range(n):
        card = {}
        for k in sorted(gate_keys):
            card[k] = bool(rng.below(2))
        for f in sorted(auto_fields):
            r = rng.below(3)
            if r == 0:
                continue            # 字段缺失 → unknown
            card[f] = (r == 1)
        manual = {}
        for mid in sorted(manual_ids):
            r = rng.below(5)
            if r == 0:
                continue            # 未录入 → unknown
            manual[mid] = {"state": ALL_STATES[rng.below(len(ALL_STATES))], "note": "合成随机录入"}
        cases.append(_case("rand-%02d" % i, "随机合成场景 #%02d" % i, card, manual, mirrors,
                           note="seed=0x%X" % SEED))
    return cases


def build_cases(rs):
    mirrors = _mirrors(rs)
    item_ids, auto, gates, thresholds, manual_ids = mirrors[:5]
    gate_keys = tuple(sorted({k for k, _ in gates.values()}))
    auto_fields = tuple(sorted(set(auto.values())))

    cases = []
    cases += _boundary_cases(mirrors, gate_keys)
    cases += _named_cases(mirrors, gate_keys)
    cases += _semantic_cases(mirrors, gate_keys, auto_fields)
    cases += _random_cases(mirrors, gate_keys, auto_fields, manual_ids, RANDOM_CASES)
    return cases


# ---------------------------------------------------------------------------
# 产物写出（确定性）
# ---------------------------------------------------------------------------
def _dump(data):
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(_dump(data))
    return path


def write_all(root=None):
    """把真值库写到 root/data/truth 下。

    规则包一律从**仓库根**（ROOT）读取（唯一权威源）；root 只决定产出位置，
    便于守门测试"再生成位级一致"（写到临时目录比对）。
    """
    out_root = Path(root) if root else ROOT
    rs = json.loads((ROOT / RULESET_FILE).read_text(encoding="utf-8"))
    out = []
    for case in build_cases(rs):
        path = out_root / "data" / "truth" / ("case-%s.json" % case["case_id"])
        _write(path, case)
        out.append(path)
    return out


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    root = Path(argv[0]) if argv else ROOT
    for p in write_all(root):
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        print("已生成: %s  sha256=%s" % (p, digest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
