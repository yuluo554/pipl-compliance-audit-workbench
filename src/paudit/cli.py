"""命令行入口（双形态之一）：子命令 + 退出码语义。

退出码（定稿，锁进测试）：
  0 = 完成 / 达标
  1 = 检出非合规或未评估（check/scan） / 基准未达标（bench）
  2 = 输入不可用 / 用法错误
  3 = 缺可选依赖（如 gui）
"""

import argparse
import json
import sys
from pathlib import Path

from . import __version__, DISCLAIMER
from .errors import (
    EXIT_INPUT_ERROR,
    EXIT_MISSING_EXTRA,
    EXIT_NONCOMPLIANT,
    EXIT_OK,
    InputError,
    PauditError,
)
from .rules.loader import load_ruleset
from .rules.model import SUMMARY_COMPLIANT, SUMMARY_NOT_ASSESSED


def _load_json(path):
    p = Path(path)
    if not p.is_file():
        raise InputError("输入文件不存在: %s" % p)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise InputError("输入 JSON 解析失败: %s (%s)" % (p, exc))


def _build_parser():
    p = argparse.ArgumentParser(
        prog="paudit",
        description="个人信息保护合规审计工作台（全本地、零上传）",
    )
    p.add_argument("--version", action="version", version="paudit %s" % __version__)
    sub = p.add_subparsers(dest="command")

    c = sub.add_parser("check", help="单件：跑门槛+检查单，输出结论")
    c.add_argument("input", help="参数卡 JSON（含 input_card / manual_results）")
    c.add_argument("--ruleset", default=None, help="规则包路径或目录（默认自动定位）")
    c.add_argument("--out", default=None, help="结论输出 JSON 路径（可选）")
    c.add_argument("--preview", action="store_true", help="允许含 pending 条目（仅预览，不判定）")

    b = sub.add_parser("bench", help="跑内置基准")
    b.add_argument("--ruleset", default=None, help="规则包路径或目录（默认权威规则包）")
    b.add_argument("--json", action="store_true", help="以 JSON 输出指标")

    r = sub.add_parser("report", help="导出报告")
    r.add_argument("input", help="底稿/参数卡 JSON")
    r.add_argument("-o", "--out", required=True, help="输出路径（.md/.docx/.xlsx）")
    r.add_argument("--ruleset", default=None)
    r.add_argument("--template", default="self", choices=["self", "third_party"])

    g = sub.add_parser("gui", help="启动桌面应用")
    return p


def cmd_check(args):
    from .engine.pipeline import AuditRequest, compute_audit

    rs = load_ruleset(args.ruleset, allow_pending=args.preview)
    if args.preview:
        print("提示：--preview 仅预览，pending 条目不参与判定", file=sys.stderr)

    data = _load_json(args.input)
    card = data.get("input_card", data)
    manual = data.get("manual_results", {})
    scope = data.get("audit_scope", {})

    result = compute_audit(AuditRequest(card, manual, scope), rs)
    out = result.to_dict()

    if args.out:
        Path(args.out).write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print("结论已写出: %s" % args.out)
    else:
        print(json.dumps(out, ensure_ascii=False, indent=2))

    print(DISCLAIMER, file=sys.stderr)
    return EXIT_OK if out["summary"] == SUMMARY_COMPLIANT else EXIT_NONCOMPLIANT


def cmd_bench(args):
    from .benchmark.runner import run_all
    from .errors import PendingEntryError

    rs = None
    if getattr(args, "ruleset", None):
        rs = load_ruleset(args.ruleset, allow_pending=True)
    try:
        report = run_all(rs) if rs is not None else run_all()
    except PendingEntryError as exc:
        # 门控拦截 = 未达标（规则包未核对生效，基准无法跑）→ 退出码 1
        print("基准未达标：规则包未生效（%s）" % exc, file=sys.stderr)
        return EXIT_NONCOMPLIANT
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        for line in report.lines():
            print(line)
    return EXIT_OK if report.passed else EXIT_NONCOMPLIANT


def cmd_report(args):
    from .report.markdown import render_markdown

    rs = load_ruleset(args.ruleset)
    data = _load_json(args.input)
    text = render_markdown(data, rs, template=args.template)
    out = Path(args.out)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("报告已写出: %s" % out)
    return EXIT_OK


def cmd_gui(args):
    # 惰性导入边界 = "第一个真正触及重件的调用"，try 包住整段（缺 extra → exit 3）
    try:
        from .gui import main as gui_main

        return gui_main()
    except ImportError as exc:
        print("缺少桌面依赖，请安装: pip install -e \".[gui]\"（%s）" % exc, file=sys.stderr)
        return EXIT_MISSING_EXTRA


_DISPATCH = {
    "check": cmd_check,
    "bench": cmd_bench,
    "report": cmd_report,
    "gui": cmd_gui,
}


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return EXIT_INPUT_ERROR
    try:
        return _DISPATCH[args.command](args)
    except PauditError as exc:
        print("错误：%s" % exc, file=sys.stderr)
        return EXIT_INPUT_ERROR


if __name__ == "__main__":
    sys.exit(main())
