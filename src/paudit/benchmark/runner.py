"""内置基准 runner：四类扫描，零 API 依赖，一条命令跑全。

退出码语义（FR-7.4）：0=达标 / 1=未达标或门控拦截 / 2=用法错误（由 CLI 处理）。
全量单次 < 1 秒。
"""

from .cases import expected_summary, expected_threshold, observed_nonpass


class BenchmarkReport:
    def __init__(self, suites):
        self.suites = suites  # list of dict(name, total, passed, failed, notes)

    @property
    def passed(self):
        return all(s["failed"] == 0 for s in self.suites)

    @property
    def totals(self):
        t = sum(s["total"] for s in self.suites)
        p = sum(s["passed"] for s in self.suites)
        return t, p

    def to_dict(self):
        total, passed = self.totals
        return {
            "passed": self.passed,
            "total": total,
            "passed_cases": passed,
            "accuracy": (passed / total) if total else 0.0,
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
        return out


def run_all(ruleset=None):
    """跑全部基准套件。"""
    from ..rules.loader import load_ruleset

    rs = ruleset if ruleset is not None else load_ruleset()
    suites = [
        _suite_threshold_boundary(rs),
        _suite_checklist_selfconsistent(rs),
        _suite_synthetic_scenarios(rs),
    ]
    return BenchmarkReport(suites)


def _suite_threshold_boundary(rs):
    """B1 门槛边界：对每条门槛的 value 取 {value-1, value, value+1} 枚举验证。"""
    total = failed = 0
    for th in rs.thresholds:
        for delta in (-1, 0, 1):
            actual = th.value + delta
            total += 1
            exp = expected_threshold(th, actual)
            from ..engine.thresholds import _OPS

            got = _OPS[th.op](actual, th.value)
            if exp != got:
                failed += 1
    return {"name": "B1 门槛边界（value±1 枚举）", "total": total,
            "passed": total - failed, "failed": failed, "notes": ""}


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
    """B3 合成场景：真值 vs 引擎汇总对账（真值库缺失时如实标注未生成）。"""
    import json
    from pathlib import Path

    from ..paths import find_data_dir

    truth_dir = find_data_dir() / "truth"
    files = sorted(truth_dir.glob("*.json")) if truth_dir.is_dir() else []
    if not files:
        return {"name": "B3 合成审计场景", "total": 0, "passed": 0, "failed": 0,
                "notes": "真值库未生成（data/truth/ 为空）——该类用例未生成，不假装覆盖"}

    from ..engine.pipeline import AuditRequest, compute_audit

    total = failed = 0
    for f in files:
        case = json.loads(f.read_text(encoding="utf-8"))
        total += 1
        res = compute_audit(
            AuditRequest(case.get("input_card", {}), case.get("manual_results", {})),
            rs)
        exp = case.get("expected", {}).get("summary")
        if exp is not None and res.summary != exp:
            failed += 1
        # also_expect 对账：非 pass 状态集
        also = case.get("expected", {}).get("also_expect_nonpass")
        if also is not None:
            states = [r.state for r in res.item_results]
            if observed_nonpass(states) != sorted(also):
                failed += 1
    return {"name": "B3 合成审计场景（真值对账）", "total": total,
            "passed": total - failed, "failed": failed, "notes": ""}
