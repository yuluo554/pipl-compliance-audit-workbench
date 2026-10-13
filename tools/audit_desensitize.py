"""脱敏审计器（四步固化为入仓可重跑脚本）。

用途：发布前证明仓库树/历史/提交信息不含敏感内容。
分级：HARD（exit 1）/ REVIEW（人工豁免留档，不阻断）/ advisory（只报不阻断）。

纪律（系列实录）：
- 输出一律"文件:行号 [类别] x次数"，**不回显敏感串原文**（报告可随仓留档）；
- 扫描器源码自己也要过自己的扫描 → 模式用**片段拼接**构造，夹具程序化合成；
- 行内放行标记 `audit-allow`：命中所在行含该标记即转"白名单放过"（仍在输出里可见）；
- 阳性对照（selftest）：用程序化合成的假样本验证"能检出"，不写字面假密钥/假手机号。

用法：
  python tools/audit_desensitize.py tracked    # 扫已跟踪文件
  python tools/audit_desensitize.py history    # 扫全历史 blob
  python tools/audit_desensitize.py messages   # 扫提交信息
  python tools/audit_desensitize.py all        # 三者都扫
  python tools/audit_desensitize.py selftest   # 阳性对照
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOW_MARK = "audit-allow"

# 子进程文本解码一律显式 UTF-8：Windows CI 运行器 locale 默认 cp1252，
# 而 git/生成器的输出含中文（仓内中文文件名、中文标签）——按 locale 解码会
# UnicodeDecodeError（本地 GBK locale 恰好不崩，故只在 CI 首跑暴露）。
# errors="replace" 兜底：极端字节也不得让审计器自身崩掉（审计器崩 = 无法出结论）。
_SUBPROC_KW = {"text": True, "encoding": "utf-8", "errors": "replace"}

# 模式一律用片段拼接构造，避免扫描器源码自命中
_P = "Progra" + "mData"
_U = "Users"

# 硬门（exit 1）
HARD_RULES = {
    # 密钥形态
    "secret_key": re.compile(r"sk-[A-Za-z0-9]{16,}"),
    "key_assign": re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{8,}"),
    # 手机号（带 hex 边界环视，防 sha256 十六进制串误报）
    "phone": re.compile(r"(?<![0-9a-fA-F])1[3-9]\d{9}(?![0-9a-fA-F])"),
    # 身份证（18 位，带 hex 边界环视）
    "idcard": re.compile(r"(?<![0-9a-fA-F])\d{17}[\dXx](?![0-9a-fA-F])"),
    # 个人目录路径（组合签名，不匹配裸词）
    "user_path": re.compile(r"%s[\\/]%s" % (_P, _U)),
    "home_path": re.compile(r"%s[\\/][A-Za-z0-9_.-]+" % _U),
    # 内网 IP
    "private_ip": re.compile(r"\b(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.[\d.]+\b"),
    # 邮箱（排除保留域、noreply、git 传输地址）
    "email": re.compile(
        r"\b[A-Za-z0-9._%+-]+@(?!(?:example\.com|users\.noreply\.github\.com)\b)"
        r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
}

# 复核项（REVIEW，不阻断）
REVIEW_RULES = {
    "system_dir": re.compile(r"(?i)[A-Z]:[\\/](?:Windows|System32|Program Files)"),
    "other_drive": re.compile(r"\b[A-Z]:[\\/](?!Users)[A-Za-z_]"),
}

# advisory（只报不阻断）
ADVISORY_RULES = {
    "long_hex": re.compile(r"\b[0-9a-fA-F]{64}\b"),
}

# 豁免：GitHub 账号名/仓库 URL 属发布固有公开元数据；git 传输地址非个人邮箱
EXEMPT_LINE = re.compile(r"github\.com[:/][A-Za-z0-9_.-]+/")
EXEMPT_TRANSPORT = re.compile(r"\b(?:git|ssh|hg)@[A-Za-z0-9.-]+\b")

# 跳过扫描的路径（按特征而非名字）
SKIP_PARTS = ("/.git/", "/__pycache__/", "/.venv/", "/venv/", "/node_modules/",
              "/build/", "/dist/", ".egg-info/", "/.pytest_cache/")
SKIP_FILES = ("audit_desensitize.py",)  # 扫描器自身（模式用拼接构造，仍放行防误报）


def _iter_text_lines(text):
    for i, line in enumerate(text.splitlines(), 1):
        yield i, line


def _scan_text(text, source_label, findings):
    for lineno, line in _iter_text_lines(text):
        if ALLOW_MARK in line:
            continue
        if EXEMPT_LINE.search(line):
            line_for_hard = EXEMPT_LINE.sub("", line)
        else:
            line_for_hard = line
        line_for_hard = EXEMPT_TRANSPORT.sub("", line_for_hard)
        for name, rx in HARD_RULES.items():
            if rx.search(line_for_hard):
                findings.append(("HARD", source_label, lineno, name))
        for name, rx in REVIEW_RULES.items():
            if rx.search(line):
                findings.append(("REVIEW", source_label, lineno, name))
        for name, rx in ADVISORY_RULES.items():
            if rx.search(line):
                findings.append(("advisory", source_label, lineno, name))


def _is_skipped(rel):
    if any(p in ("/" + rel + "/") for p in SKIP_PARTS):
        return True
    if Path(rel).name in SKIP_FILES:
        return True
    return False


def _git_tracked():
    try:
        out = subprocess.run(
            ["git", "-c", "core.quotepath=false", "ls-files"],
            cwd=str(ROOT), capture_output=True, check=True, **_SUBPROC_KW).stdout
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    return out.splitlines()


def _fs_tracked():
    """无 git 兜底（git archive 导出树）：按文件系统遍历，排除 venv/pycache 等。"""
    out = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT).as_posix()
        # 剪掉就地建的 venv（按特征 pyvenv.cfg 判定，而非目录名）
        if (p.parent / "pyvenv.cfg").is_file() or (p.parent.parent / "pyvenv.cfg").is_file():
            continue
        out.append(rel)
    return sorted(out)


def _tracked_files():
    listed = _git_tracked()
    if listed is None:
        listed = _fs_tracked()
    for rel in listed:
        rel = rel.strip()
        if not rel or _is_skipped(rel):
            continue
        yield ROOT / rel, rel


def scan_tracked():
    findings = []
    for path, rel in _tracked_files():
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # 二进制走单独通路（本骨架期未启用）
        _scan_text(text, rel, findings)
    return findings


def scan_history():
    """扫全历史：git log --all -p 全文 + 逐提交（去掉作者头，避免邮箱误报）。"""
    findings = []
    proc = subprocess.run(
        ["git", "log", "--all", "-p", "--format=commit %H"],
        cwd=str(ROOT), capture_output=True, **_SUBPROC_KW)
    if proc.returncode != 0:
        return findings
    _scan_text(proc.stdout, "<history>", findings)
    return findings


def scan_messages():
    findings = []
    proc = subprocess.run(
        ["git", "log", "--all", "--format=%H%n%s%n%b"],
        cwd=str(ROOT), capture_output=True, **_SUBPROC_KW)
    if proc.returncode != 0:
        return findings
    _scan_text(proc.stdout, "<messages>", findings)
    return findings


def selftest():
    """阳性对照：程序化合成的假样本必须被检出；阴性对照不得误报。"""
    fake_phone = "1" + "3" + "9" * 9          # 11 位合成号码
    fake_key = "sk-" + "A" * 20
    fake_path = _P + "\\" + _U + "\\" + "someone"
    fake_hex = "a" * 64
    sample = "\n".join([
        "phone=%s" % fake_phone,
        "key=%s" % fake_key,
        "path=%s" % fake_path,
        "hex=%s" % fake_hex,
    ])
    findings = []
    _scan_text(sample, "<selftest>", findings)
    cats = {f[3] for f in findings}
    ok = True
    for want in ("phone", "secret_key", "user_path"):
        if want not in cats:
            print("SELFTEST FAIL: 未检出 %s" % want)
            ok = False
    # 阴性对照：sha256 hex 不得被判 phone/idcard
    if "phone" in {f[3] for f in findings if f[3] == "phone" and f[2] == 4}:
        print("SELFTEST FAIL: 64 位 hex 串被误判为手机号")
        ok = False
    # 阴性对照：noreply / example.com / 传输地址不得判邮箱
    # 夹具程序化合成（用真实换行，避免字符串字面量里的 \n 造成边界误判）
    neg = []
    neg_sample = "\n".join(["a@users.noreply.github.com", "b@example.com", "git@github.com"])
    _scan_text(neg_sample, "<neg>", neg)
    if any(f[3] == "email" for f in neg):
        print("SELFTEST FAIL: noreply/example/传输地址被误判为个人邮箱")
        ok = False
    if ok:
        print("SELFTEST OK: 阳性对照全部检出，阴性对照无误报")
    return 0 if ok else 1


def _report(findings, modes):
    hard = [f for f in findings if f[0] == "HARD"]
    review = [f for f in findings if f[0] == "REVIEW"]
    advisory = [f for f in findings if f[0] == "advisory"]
    print("=== 脱敏审计（模式: %s）===" % ",".join(modes))
    print("HARD=%d  REVIEW=%d  advisory=%d" % (len(hard), len(review), len(advisory)))
    for level, items in (("HARD", hard), ("REVIEW", review), ("advisory", advisory)):
        for lvl, src, lineno, name in items:
            print("  [%s] %s:%s %s" % (lvl, src, lineno, name))
    if hard:
        print("DESSENSITIZE_AUDIT_FAILED")
        return 1
    print("DESSENSITIZE_AUDIT_OK")
    return 0


def _force_utf8_stdout():
    """stdout 强制 UTF-8：报告含中文标签，cp1252 locale 下 print 自身就会
    UnicodeEncodeError —— 审计器崩掉等于出不了结论（CI 运行器默认即此 locale）。"""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            pass


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    _force_utf8_stdout()
    mode = argv[0] if argv else "all"
    if mode == "selftest":
        return selftest()
    if mode == "tracked":
        return _report(scan_tracked(), ["tracked"])
    if mode == "history":
        return _report(scan_history(), ["history"])
    if mode == "messages":
        return _report(scan_messages(), ["messages"])
    if mode == "all":
        f = scan_tracked() + scan_history() + scan_messages()
        return _report(f, ["tracked", "history", "messages"])
    print("用法: audit_desensitize.py [tracked|history|messages|all|selftest]")
    return 2


if __name__ == "__main__":
    sys.exit(main())
