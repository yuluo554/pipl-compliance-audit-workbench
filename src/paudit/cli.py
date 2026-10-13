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
    c.add_argument("--draft", action="store_true",
                   help="以底稿形态导出：带 schema_version/规则包坐标/自指纹（配 --out）")
    c.add_argument("--evidence", action="append", default=None, metavar="ITEM_ID=FILE",
                   help="挂证：检查项=证据文件（可重复）；路径仅登记文件名，内容不入底稿")
    c.add_argument("--evidence-owner", default="", help="挂证责任人（--evidence 共用）")
    c.add_argument("--evidence-date", default="", help="挂证采集时间（--evidence 共用）")

    b = sub.add_parser("bench", help="跑内置基准")
    b.add_argument("--ruleset", default=None, help="规则包路径或目录（默认权威规则包）")
    b.add_argument("--json", action="store_true", help="以 JSON 输出指标")

    r = sub.add_parser("report", help="导出报告（.md/.docx/.xlsx）")
    r.add_argument("input", help="底稿/参数卡 JSON")
    r.add_argument("-o", "--out", required=True, help="输出路径（.md/.docx/.xlsx）")
    r.add_argument("--ruleset", default=None)
    r.add_argument("--template", default="self", choices=["self", "third_party"])

    e = sub.add_parser("evidence", help="证据链：挂证 / 校验指纹")
    e.add_argument("draft", help="底稿 JSON 路径（--out 导出的结论）")
    e.add_argument("--add", action="append", default=None, metavar="ITEM_ID=FILE",
                   help="挂证：检查项=证据文件（可重复）")
    e.add_argument("--owner", default="", help="责任人")
    e.add_argument("--date", default="", help="采集时间")
    e.add_argument("--source", default="", help="来源说明（默认取文件名）")
    e.add_argument("--check", action="store_true", help="核对已挂证据与文件指纹是否一致")
    e.add_argument("-o", "--out", default=None, help="写回路径（默认原地写回）")

    d = sub.add_parser("draft", help="底稿：导出（自指纹）/ 导入（校验）")
    dsub = d.add_subparsers(dest="draft_command")
    d_export = dsub.add_parser("export", help="导出底稿并固化自指纹")
    d_export.add_argument("input", help="底稿/参数卡 JSON")
    d_export.add_argument("-o", "--out", required=True, help="输出底稿 JSON 路径")
    d_export.add_argument("--ruleset", default=None)
    d_import = dsub.add_parser("import", help="导入底稿并校验自指纹/schema/ruleset")
    d_import.add_argument("input", help="底稿 JSON 路径")
    d_import.add_argument("--ruleset", default=None)
    d_import.add_argument("-o", "--out", default=None, help="校验通过后另存路径（可选）")

    l = sub.add_parser("ledger", help="整改台账：填写 / 导出")
    l.add_argument("input", help="底稿 JSON 路径")
    l.add_argument("--apply", default=None, help="台账条目文件（JSON 数组或 CSV）")
    l.add_argument("-o", "--out", default=None, help="台账 CSV 输出路径（导出）")
    l.add_argument("--write-draft", default=None, help="把台账写回底稿并另存路径")

    g = sub.add_parser("gui", help="启动桌面应用")
    return p


def _parse_evidence_pairs(pairs):
    """解析 `ITEM_ID=FILE` 列表为 [(item_id, file), ...]。"""
    out = []
    for pair in pairs or []:
        if "=" not in pair:
            raise InputError("挂证参数格式应为 检查项=文件: %s" % pair)
        item_id, _, file_path = pair.partition("=")
        item_id = item_id.strip()
        file_path = file_path.strip()
        if not item_id or not file_path:
            raise InputError("挂证参数格式应为 检查项=文件: %s" % pair)
        out.append((item_id, file_path))
    return out


def _locate_evidence(file_ref, bases):
    """按候选基准目录定位证据文件（证据仅登记文件名）。找不到返回 None。"""
    for base in bases:
        cand = (base / file_ref)
        if cand.is_file():
            return cand
    return None


def cmd_check(args):
    from .engine.pipeline import AuditRequest, compute_audit
    from .evidence import attach_evidence, export_draft, has_item

    rs = load_ruleset(args.ruleset, allow_pending=args.preview)
    if args.preview:
        print("提示：--preview 仅预览，pending 条目不参与判定", file=sys.stderr)

    data = _load_json(args.input)
    card = data.get("input_card", data)
    manual = data.get("manual_results", {})
    scope = data.get("audit_scope", {})

    result = compute_audit(AuditRequest(card, manual, scope), rs)
    out = result.to_dict()

    # 挂证：先校验检查项存在于本规则包（防挂到未知项），再按文件名登记 + sha256
    pairs = _parse_evidence_pairs(getattr(args, "evidence", None))
    valid_ids = {it.id for it in rs.checklist}
    for item_id, file_path in pairs:
        if item_id not in valid_ids:
            raise InputError("挂证指向未知检查项: %s" % item_id)
        if not has_item(out, item_id):
            raise InputError("底稿中不存在检查项 %s（无法挂证）" % item_id)
        ev = attach_evidence(out, item_id, file_path, collected_at=args.evidence_date,
                             owner=args.evidence_owner)
        print("已挂证 %s → %s（sha256 %s…）"
              % (item_id, ev.file_ref, ev.sha256[:12]), file=sys.stderr)

    if args.out:
        if getattr(args, "draft", False):
            digest = export_draft(out, args.out)
            print("底稿已写出: %s（draft_sha256 %s）" % (args.out, digest))
        else:
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
    # 达标 = 全部套件无失败 **且** 三项门指标达标（准确率≥门值 / 误报率≤门值）
    if not report.gates_met:
        print("基准未达标：指标未过门（见 metrics/gates）", file=sys.stderr)
    return EXIT_OK if (report.passed and report.gates_met) else EXIT_NONCOMPLIANT


def cmd_report(args):
    from .report import render_to_file

    rs = load_ruleset(args.ruleset)
    data = _load_json(args.input)
    try:
        render_to_file(data, rs, args.out, template=args.template)
    except ImportError as exc:
        # DOCX/XLSX 走 optional extra；缺依赖按退出码语义记 3（缺可选依赖）
        print("缺少文档导出依赖，请安装: pip install -e \".[report]\"（%s）" % exc,
              file=sys.stderr)
        return EXIT_MISSING_EXTRA
    print("报告已写出: %s（模板 %s）" % (args.out, args.template))
    return EXIT_OK


def cmd_evidence(args):
    """证据链：往底稿挂证 / 核对已挂证据指纹。"""
    from .evidence import attach_evidence, verify_evidence_record

    data = _load_json(args.draft)
    pairs = _parse_evidence_pairs(args.add)
    if not pairs and not args.check:
        raise InputError("evidence 需指定 --add 检查项=文件 或 --check")

    valid_ids = {it.get("item_id") for it in data.get("item_results", [])}
    for item_id, file_path in pairs:
        if item_id not in valid_ids:
            raise InputError("底稿中不存在检查项 %s（无法挂证）" % item_id)
        ev = attach_evidence(data, item_id, file_path, source=args.source,
                             collected_at=args.date, owner=args.owner)
        print("已挂证 %s → %s（sha256 %s…）" % (item_id, ev.file_ref, ev.sha256[:12]))

    mismatches = []
    if args.check:
        # 证据正文只登记文件名（脱敏纪律）；核对时按"底稿所在目录 → 当前目录"定位
        bases = [Path(args.draft).resolve().parent, Path.cwd()]
        checked = 0
        for it in data.get("item_results", []):
            for ev in it.get("evidence", []):
                ref = ev.get("file_ref")
                if not ref:
                    continue
                target = _locate_evidence(ref, bases)
                if target is None:
                    continue
                checked += 1
                if not verify_evidence_record(ev, target):
                    mismatches.append("%s (%s)" % (ev.get("evidence_id"), ref))
        print("已核对 %d 条证据指纹" % checked)
        if mismatches:
            print("指纹不匹配: %s" % ", ".join(mismatches), file=sys.stderr)
            return EXIT_NONCOMPLIANT

    out = args.out or args.draft
    if pairs:
        # 挂证改变了底稿正文 → 旧自指纹失效；清除以免留下"看似有效"的陈旧指纹。
        # 需固化新指纹时用 `draft export` 重新导出。
        data.pop("draft_sha256", None)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
    if pairs:
        print("底稿已写出: %s（自指纹已清除；如需固化请跑 draft export）" % out)
    else:
        print("底稿已写出: %s" % out)
    return EXIT_OK


def cmd_draft(args):
    from .evidence import DRAFT_SCHEMA_VERSION, draft_ruleset_id, export_draft, import_draft

    sub = getattr(args, "draft_command", None)
    if sub == "export":
        from .engine.pipeline import AuditRequest, compute_audit

        rs = load_ruleset(args.ruleset)
        data = _load_json(args.input)
        # 参数卡输入 → 重算为底稿形态；已是底稿（含 item_results）则原样导出
        if "item_results" in data and "input_card" in data:
            draft = data
        else:
            card = data.get("input_card", data)
            audit = compute_audit(
                AuditRequest(card, data.get("manual_results", {}),
                             data.get("audit_scope", {})), rs)
            draft = audit.to_dict()
        digest = export_draft(draft, args.out)
        print("底稿已导出: %s（draft_sha256 %s）" % (args.out, digest))
        return EXIT_OK

    if sub == "import":
        rs = load_ruleset(args.ruleset)
        data = import_draft(args.input, expect_ruleset_id=rs.ruleset_id,
                            expect_schema_version=DRAFT_SCHEMA_VERSION)
        rid = draft_ruleset_id(data)
        # 往返一致性：用底稿输入重算结论，须与底稿记录一致
        from .evidence import verify_draft_consistency

        ok, detail = verify_draft_consistency(data, rs)
        if not ok:
            print("底稿往返校验失败：%s" % detail, file=sys.stderr)
            return EXIT_NONCOMPLIANT
        print("底稿校验通过: ruleset_id=%s schema_version=%s（往返结论一致）"
              % (rid, data.get("schema_version")))
        if args.out:
            with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
            print("底稿已另存: %s" % args.out)
        return EXIT_OK

    raise InputError("draft 需指定子命令 export 或 import")


def cmd_ledger(args):
    """整改台账：填写（--apply）并导出 CSV（-o）/ 写回底稿（--write-draft）。"""
    from .engine.remediation import apply_ledger, export_ledger, ledger_summary

    data = _load_json(args.input)
    if args.apply:
        from .engine.remediation import load_ledger

        n = apply_ledger(data, load_ledger(args.apply))
        print("已更新 %d 条台账" % n)
    if args.out:
        export_ledger(data, args.out)
        print("台账已导出: %s" % args.out)
    if args.write_draft:
        # 填台账改变了底稿正文 → 旧自指纹失效；清除以免留下"看似有效"的陈旧指纹
        data.pop("draft_sha256", None)
        with open(args.write_draft, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
        print("底稿已写出: %s（自指纹已清除；如需固化请跑 draft export）" % args.write_draft)
    if not (args.apply or args.out or args.write_draft):
        s = ledger_summary(data)
        print(json.dumps(s, ensure_ascii=False, indent=2))
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
    "evidence": cmd_evidence,
    "draft": cmd_draft,
    "ledger": cmd_ledger,
    "gui": cmd_gui,
}


def _force_utf8_stdio():
    """把 stdout/stderr 切到 UTF-8：CLI 输出含中文（结论文案、条款说明），
    Windows 非 UTF-8 代码页（如 CI 运行器默认 cp1252）下 print 会
    UnicodeEncodeError —— 工具本体不得因"终端编码"而崩。
    仅在可 reconfigure 时生效（py3.7+ 且有真实流）；失败静默降级。
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            pass


def main(argv=None):
    _force_utf8_stdio()
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse 的用法错误即以 2 退出（与 EXIT_INPUT_ERROR 同值）；
        # 转成返回值而非抛出，便于嵌入调用（GUI/测试）与统一退出码语义。
        code = exc.code if isinstance(exc.code, int) else EXIT_INPUT_ERROR
        return code
    if not args.command:
        parser.print_help()
        return EXIT_INPUT_ERROR
    try:
        return _DISPATCH[args.command](args)
    except PauditError as exc:
        print("错误：%s" % exc, file=sys.stderr)
        return EXIT_INPUT_ERROR
    except FileNotFoundError as exc:
        print("错误：%s" % exc, file=sys.stderr)
        return EXIT_INPUT_ERROR


if __name__ == "__main__":
    sys.exit(main())
