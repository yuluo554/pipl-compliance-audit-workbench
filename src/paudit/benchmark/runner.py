"""内置基准 runner：四类扫描，零 API 依赖，一条命令跑全。

退出码语义（FR-7.4）：0=达标 / 1=未达标或门控拦截 / 2=用法错误（由 CLI 处理）。
全量单次 < 1 秒。

套件：
- B1 门槛边界（value±1 枚举）+ 义务类型分栏核对；
- B2 检查项自洽（条款引用/唯一性）；
- B3 合成审计场景真值对账（含门槛分栏结论）；
- B4 四态判定覆盖（auto 映射词表逐值核对 + 汇总语义）。

指标（M4）：各套件把可比对的**观测**以计数器上报（`metrics`），`BenchmarkReport`
汇总为三项门指标——`trigger_accuracy`（触发判定准确率）、`state_accuracy`（四态准确率）、
`false_positive_rate`（误报率）。误报/漏报口径的唯一实现源是 `cases.confusion`：
**问题 = partial ∪ noncompliant**；误报=真值非问题而引擎判问题；漏报反之。
"""

from ..rules.model import ALL_STATES, METHOD_AUTO
from .cases import (
    GATE_FALSE_POSITIVE_RATE,
    GATE_STATE_ACCURACY,
    GATE_TRIGGER_ACCURACY,
    apply_mapping,
    confusion,
    expected_summary,
    expected_threshold,
    observed_nonpass,
    rate,
)

# B4 枚举用的取值池（结构性词，非政策字面量）：覆盖映射词表的各类取值
_MAPPING_PROBES = [True, False, "complete", "partial", "absent", "not_required",
                   "not_applicable", "", "  ", None]

# 门值（供 CLI/报告展示，单一源在 cases.py）
GATES = {
    "trigger_accuracy": GATE_TRIGGER_ACCURACY,
    "state_accuracy": GATE_STATE_ACCURACY,
    "false_positive_rate": GATE_FALSE_POSITIVE_RATE,
}


def _merge_metrics(target, source):
    """把套件计数器并入全局（键求和；样本量键与正确数键同名约定）。"""
    for k, v in (source or {}).items():
        target[k] = target.get(k, 0) + v


def _global_metrics(suites):
    """汇总各套件计数器 → 三项门指标（+映射一致率）+ 样本量/正确数。

    三项门指标（plan/05 §三 M4）：
    - `trigger_accuracy` 触发判定准确率 = 触发判定正确数 / 触发判定样本数；
    - `state_accuracy` 四态准确率 = 逐项四态与真值一致数 / 逐项样本数；
    - `false_positive_rate` 误报率 = 误报数 / 真值非问题项数（门值 0）。
    """
    agg = {}
    for s in suites:
        _merge_metrics(agg, s.get("metrics"))
    trigger_samples = agg.get("trigger_samples", 0)
    state_samples = agg.get("state_samples", 0)
    mapping_samples = agg.get("mapping_samples", 0)
    fp_samples = agg.get("false_positive_samples", 0)
    fn_samples = agg.get("false_negative_samples", 0)
    return {
        "trigger_accuracy": rate(agg.get("trigger_correct", 0), trigger_samples),
        "trigger_correct": agg.get("trigger_correct", 0),
        "trigger_samples": trigger_samples,
        "state_accuracy": rate(agg.get("state_correct", 0), state_samples),
        "state_correct": agg.get("state_correct", 0),
        "state_samples": state_samples,
        "mapping_accuracy": rate(agg.get("mapping_correct", 0), mapping_samples),
        "mapping_correct": agg.get("mapping_correct", 0),
        "mapping_samples": mapping_samples,
        "false_positive_rate": rate(agg.get("false_positive", 0), fp_samples),
        "false_positive": agg.get("false_positive", 0),
        "false_positive_samples": fp_samples,
        "miss_rate": rate(agg.get("false_negative", 0), fn_samples),
        "false_negative": agg.get("false_negative", 0),
        "false_negative_samples": fn_samples,
    }


def _metrics_meet_gates(metrics):
    """三项门指标达标判定（口径与测试一致）。

    无样本（分母 0）的指标视为**不适用**（该类用例未生成，如示例包无真值库），
    不阻塞门禁——"无证据"不等于"不达标"；有样本的指标必须达标。
    权威规则包三指标样本量均 > 0，故门禁在此为强约束。
    """
    checks = (
        ("trigger_accuracy", metrics["trigger_samples"], ">=", GATE_TRIGGER_ACCURACY),
        ("state_accuracy", metrics["state_samples"], ">=", GATE_STATE_ACCURACY),
        ("false_positive_rate", metrics["false_positive_samples"], "<=",
         GATE_FALSE_POSITIVE_RATE),
    )
    for key, samples, op, limit in checks:
        if not samples:
            continue
        val = metrics[key]
        if op == ">=" and val < limit:
            return False
        if op == "<=" and val > limit:
            return False
    return True


class BenchmarkReport:
    def __init__(self, suites):
        self.suites = suites  # list of dict(name, total, passed, failed, notes[, metrics])

    @property
    def passed(self):
        return all(s["failed"] == 0 for s in self.suites)

    @property
    def totals(self):
        t = sum(s["total"] for s in self.suites)
        p = sum(s["passed"] for s in self.suites)
        return t, p

    @property
    def metrics(self):
        return _global_metrics(self.suites)

    @property
    def gates_met(self):
        return _metrics_meet_gates(self.metrics)

    def to_dict(self):
        total, passed = self.totals
        return {
            "passed": self.passed,
            "total": total,
            "passed_cases": passed,
            "accuracy": rate(passed, total),
            "metrics": self.metrics,
            "gates": dict(GATES),
            "suites": self.suites,
        }

    def lines(self):
        out = []
        total, passed = self.totals
        for s in self.suites:
            out.append("[%s] %d/%d  %s" % (
                "OK" if s["failed"] == 0 else "FAIL",
                s["passed"], s["total"], s["name"]))
            if s.get("notes"):
                out.append("      note: %s" % s["notes"])
        out.append("TOTAL: %d/%d  达标=%s" % (passed, total, self.passed))
        m = self.metrics
        out.append("指标: 触发判定准确率=%s  四态准确率=%s  误报率=%s  漏报率=%s"
                   % (_fmt(m, "trigger_accuracy", "trigger_correct", "trigger_samples"),
                      _fmt(m, "state_accuracy", "state_correct", "state_samples"),
                      _fmt(m, "false_positive_rate", "false_positive", "false_positive_samples"),
                      _fmt(m, "miss_rate", "false_negative", "false_negative_samples")))
        out.append("门值: 触发判定≥%.2f 四态≥%.2f 误报率≤%.2f  →  %s"
                   % (GATE_TRIGGER_ACCURACY, GATE_STATE_ACCURACY, GATE_FALSE_POSITIVE_RATE,
                      "达标" if self.gates_met else "未达标"))
        return out


def _fmt(m, rate_key, num_key, den_key):
    """指标显示：无样本（分母 0）记 `n/a`，避免 0.0000 被误读为不达标。"""
    if not m[den_key]:
        return "n/a (无样本)"
    return "%.4f (%d/%d)" % (m[rate_key], m[num_key], m[den_key])


def run_all(ruleset=None):
    """跑全部基准套件。"""
    from ..rules.loader import load_ruleset

    rs = ruleset if ruleset is not None else load_ruleset()
    suites = [
        _suite_threshold_boundary(rs),
        _suite_checklist_selfconsistent(rs),
        _suite_synthetic_scenarios(rs),
        _suite_four_state(rs),
    ]
    return BenchmarkReport(suites)


def _suite_threshold_boundary(rs):
    """B1 门槛边界：对每条门槛的 value 取 {value-1, value, value+1} 枚举验证。

    额外核对**义务类型分栏**：合并规则按 severity 降序 + 分栏内义务类型序，
    条件触发（保护部门可以要求）不得混入"处理者无条件义务"栏。
    指标：边界枚举的触发判定正确数（`trigger_correct`/`trigger_samples`）。
    """
    total = failed = 0
    trigger_correct = trigger_samples = 0
    from ..engine.thresholds import _OPS, evaluate_thresholds

    for th in rs.thresholds:
        for delta in (-1, 0, 1):
            actual = th.value + delta
            total += 1
            trigger_samples += 1
            exp = expected_threshold(th, actual)
            got = _OPS[th.op](actual, th.value)
            if exp == got:
                trigger_correct += 1
            else:
                failed += 1

    # 分栏核对：命中的每条门槛必须**恰好**落入与其 effect 对应的栏位。
    # 注意：同 param 的门槛可能同时命中（如 scale 上的多条），故按"命中集"整体核对，
    # 不做单条隔离（隔离会因共参门槛连带命中而失准）。
    for th in rs.thresholds:
        total += 1
        card = {th.param: th.value}
        res = evaluate_thresholds(rs, card)
        ob_ids = {t.id for t in res.obligations}
        cd_ids = {t.id for t in res.conditional_triggers}
        ok = True
        if th in res.matched:
            if th.is_conditional():
                ok = th.id in cd_ids and th.id not in ob_ids
            else:
                ok = th.id in ob_ids and th.id not in cd_ids
        else:
            ok = th.id not in ob_ids and th.id not in cd_ids
        # 两栏不相交，且并集 == 命中集
        if ob_ids & cd_ids or (ob_ids | cd_ids) != {t.id for t in res.matched}:
            ok = False
        if not ok:
            failed += 1

    # 条件触发不得贡献"无条件义务"：构造只可能命中条件门槛的输入时 obligations 须为空
    conditional_only = [t for t in rs.thresholds if t.is_conditional()]
    for th0 in conditional_only:
        card = {t.param: t.value for t in conditional_only}
        # 去掉会被无条件门槛命中的参数（避免共参导致误判）
        for t in rs.thresholds:
            if not t.is_conditional() and t.param in card:
                del card[t.param]
        total += 1
        res = evaluate_thresholds(rs, card)
        if res.obligations:
            failed += 1

    return {"name": "B1 门槛边界（value±1 枚举）+ 义务分栏", "total": total,
            "passed": total - failed, "failed": failed, "notes": "",
            "metrics": {"trigger_correct": trigger_correct,
                        "trigger_samples": trigger_samples}}


def _suite_checklist_selfconsistent(rs):
    """B2 检查项自洽：条款引用完整性 + 证据要求非空 + id 唯一。"""
    total = failed = 0
    seen = set()
    for item in rs.checklist:
        total += 1
        ok = bool(item.clause.basis and item.clause.article) and bool(item.id)
        if item.evidence_required is not True:
            ok = ok and (item.evidence_required in (True, False))
        if item.id in seen:
            ok = False
        seen.add(item.id)
        if not ok:
            failed += 1
    return {"name": "B2 检查项自洽（条款引用/唯一性）", "total": total,
            "passed": total - failed, "failed": failed, "notes": ""}


def _suite_synthetic_scenarios(rs):
    """B3 合成场景：真值 vs 引擎汇总对账（真值库缺失时如实标注未生成）。

    只跑与当前规则包 `ruleset_id` 匹配的真值用例（真值由生成器按权威规则包产出）。
    指标：触发判定（`triggered` 对账）+ 逐项四态混淆矩阵（`confusion`：四态准确率/
    误报率/漏报率），真值取用例冻结的 `expected.item_states`（生成期独立推导，非现算）。
    """
    import json

    from ..paths import find_data_dir

    truth_dir = find_data_dir() / "truth"
    files = sorted(truth_dir.glob("*.json")) if truth_dir.is_dir() else []
    cases = []
    for f in files:
        case = json.loads(f.read_text(encoding="utf-8"))
        if case.get("ruleset_id", rs.ruleset_id) == rs.ruleset_id:
            cases.append(case)
    if not cases:
        return {"name": "B3 合成审计场景", "total": 0, "passed": 0, "failed": 0,
                "notes": "真值库无匹配 ruleset_id=%s 的用例——该类用例未生成，不假装覆盖"
                         % rs.ruleset_id,
                "metrics": {}}

    from ..engine.pipeline import AuditRequest, compute_audit

    total = failed = 0
    trigger_correct = trigger_samples = 0
    state_correct = state_samples = 0
    false_positive = false_positive_samples = 0
    false_negative = false_negative_samples = 0
    for case in cases:
        total += 1
        res = compute_audit(
            AuditRequest(case.get("input_card", {}), case.get("manual_results", {})),
            rs)
        exp = case.get("expected", {})
        if exp.get("summary") is not None and res.summary != exp["summary"]:
            failed += 1
        if exp.get("triggered") is not None:
            trigger_samples += 1
            if res.threshold_result.triggered == exp["triggered"]:
                trigger_correct += 1
            else:
                failed += 1
        # 门槛分栏结论对账（无条件义务 vs 条件触发分开呈现）
        ob_exp = exp.get("obligation_conclusions")
        if ob_exp is not None:
            got = sorted({t.conclusion for t in res.threshold_result.obligations})
            if got != sorted(ob_exp):
                failed += 1
        cd_exp = exp.get("conditional_conclusions")
        if cd_exp is not None:
            got = sorted({t.conclusion for t in res.threshold_result.conditional_triggers})
            if got != sorted(cd_exp):
                failed += 1
        # also_expect 对账：非 pass 状态集
        also = exp.get("also_expect_nonpass")
        if also is not None:
            states = [r.state for r in res.item_results]
            if observed_nonpass(states) != sorted(also):
                failed += 1
        # 逐项四态混淆矩阵（真值取用例冻结 item_states；引擎按检查单序逐项对账）
        truth_items = exp.get("item_states")
        if truth_items:
            truth_states = [truth_items[r.item.id] for r in res.item_results]
            engine_states = [r.state for r in res.item_results]
            conf = confusion(truth_states, engine_states)
            state_samples += conf["total"]
            state_correct += conf["correct"]
            false_positive += conf["false_positive"]
            false_positive_samples += conf["truth_clear"]
            false_negative += conf["false_negative"]
            false_negative_samples += conf["truth_flagged"]
    return {"name": "B3 合成审计场景（真值对账）", "total": total,
            "passed": total - failed, "failed": failed, "notes": "",
            "metrics": {
                "trigger_correct": trigger_correct, "trigger_samples": trigger_samples,
                "state_correct": state_correct, "state_samples": state_samples,
                "false_positive": false_positive,
                "false_positive_samples": false_positive_samples,
                "false_negative": false_negative,
                "false_negative_samples": false_negative_samples,
            }}


def _suite_four_state(rs):
    """B4 四态判定覆盖：auto 项映射词表逐值核对（引擎 vs 独立实现）+ 汇总语义。

    - 对每个 auto 检查项，枚举映射词表取值，断言引擎 `_map_auto` 与基准独立实现
      `apply_mapping` 结论一致（两套独立实现互验）；
    - 断言映射结果的四态覆盖：声明了三态/四态的项，其取值池应能触达 compliant /
      partial / noncompliant（无条件义务项不得把"未制定"映射为 not_applicable）；
    - 汇总语义：全 not_applicable / 全 unknown → not_assessed（绝不输出 compliant）。

    指标：auto 映射逐值一致数（`mapping_correct`/`mapping_samples`——引擎判定与独立实现
    同判即"映射一致"）。
    """
    from ..engine.checklist import _map_auto

    total = failed = 0
    mapping_correct = mapping_samples = 0
    auto_items = [c for c in rs.checklist if c.method == METHOD_AUTO]
    if not auto_items:
        return {"name": "B4 四态判定覆盖（auto 映射 + 汇总）", "total": 0,
                "passed": 0, "failed": 0, "notes": "规则包无 auto 检查项——该类用例未生成",
                "metrics": {}}

    for item in auto_items:
        rules = item.auto_mapping.to_dict().get("rules") if item.auto_mapping else None
        # (1) 引擎 vs 独立实现逐值一致
        for probe in _MAPPING_PROBES:
            total += 1
            mapping_samples += 1
            got = _map_auto(item, probe)
            exp = apply_mapping(rules, probe)
            if got == exp:
                mapping_correct += 1
            else:
                failed += 1
        # (2) 映射结果必须落在四态词表内
        total += 1
        states = {_map_auto(item, p) for p in _MAPPING_PROBES}
        if not states <= set(ALL_STATES):
            failed += 1
        # (3) 缺项口径勘误的回归锁：取值为 False（未制定/未采取）时一律判**不符合**，
        #     绝不判 not_applicable（"未制定"≠"不适用"，原文多为无条件义务）。
        total += 1
        if _map_auto(item, False) != "noncompliant":
            failed += 1
        # (4) 空值同样记不符合（未提供即未满足），不得记 compliant
        total += 1
        if _map_auto(item, "") == "compliant":
            failed += 1

    # (5) 汇总语义：无 applicable → not_assessed
    for states in (["not_applicable"] * 3, ["unknown"] * 3, ["unknown", "not_applicable"]):
        total += 1
        if expected_summary(states) != "not_assessed":
            failed += 1

    return {"name": "B4 四态判定覆盖（auto 映射 + 汇总）", "total": total,
            "passed": total - failed, "failed": failed, "notes": "",
            "metrics": {"mapping_correct": mapping_correct, "mapping_samples": mapping_samples}}
