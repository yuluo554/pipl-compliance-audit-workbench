"""守门测试 G13：M6 发布面（防"发布素材/状态行/审计入口"漂移回归）。

断言：
- 演示素材生成器存在且**顶层不 import Qt/重件**（可无 Qt 环境导入并给出降级路径）；
  素材确定性：四页签标题齐备、GIF 组装与清单 sha256 逻辑为单一实现源；
- README 状态行**已转正**（不含 🚧/"下一棒"），且演示素材被 README 引用；
- 脱敏审计器支持四步 `all` 模式（发布前必跑面）；
- 版本号与 Release tag 口径一致（pyproject 为语义化版本）。

本门与 G6（workflow 可解析）、G12（打包白名单）互补：G12 守"产物不含版权红线"，
本门守"对外发布面（素材/状态行/审计）真的齐备且可复现"。
"""

import ast
import re

from conftest import ROOT

DOCS_DEMO = ROOT / "docs" / "demo"
TAB_TITLES = ("触发判定", "检查单", "证据链", "报告导出")


def _text(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 演示素材生成器
# ---------------------------------------------------------------------------
def test_demo_asset_tool_exists_and_toplevel_is_light():
    """生成器须可被普通 Python 导入（Qt 只在函数体内导入），以便无 GUI 环境降级。"""
    path = ROOT / "tools" / "make_demo_assets.py"
    assert path.is_file(), "缺演示素材生成器 tools/make_demo_assets.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    top = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            top.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            top.add(node.module.split(".")[0])
    assert "PySide6" not in top, "生成器顶层不得 import Qt"
    assert "PIL" not in top, "生成器顶层不得 import Pillow（须在函数体内，支持降级）"


def test_demo_asset_tool_renders_all_four_tabs():
    """四页签标题须齐备（素材覆盖整个审计工作流）。"""
    text = _text("tools/make_demo_assets.py")
    for title in TAB_TITLES:
        assert title in text, "生成器未覆盖页签: %s" % title
    for name in ("demo.gif", "cli-bench.png", "MANIFEST.json"):
        assert name in text, "生成器未产出: %s" % name


def test_demo_asset_tool_is_deterministic_by_construction():
    """素材可复现：清单走 sha256 单一实现源，且不引入系统时钟/随机数。"""
    text = _text("tools/make_demo_assets.py")
    assert "sha256" in text, "生成器未做产物指纹登记"
    assert "MANIFEST" in text, "生成器未产出清单"
    # 确定性纪律：不得用随机数或系统时间戳命名/写入
    for banned in ("random.", "datetime.now", "time.time"):
        assert banned not in text, "生成器引入非确定源: %s" % banned


def test_demo_asset_tool_uses_demo_ruleset_not_authoritative():
    """演示素材须用示例规则包（非法规门槛），不得据以作出合规结论。"""
    text = _text("tools/make_demo_assets.py")
    assert "samples" in text, "生成器应使用 data/samples 示例规则包"


# ---------------------------------------------------------------------------
# README 状态行转正 + 素材引用
# ---------------------------------------------------------------------------
def test_readme_status_line_is_transposed():
    """发布后 README 状态行不得再是进行中（🚧 / "下一棒"）。"""
    text = _text("README.md")
    head = text.split("## ", 1)[0]
    assert "🚧" not in head, "README 状态行仍为进行中（🚧）"
    assert "下一棒" not in head, "README 状态行仍标注下一棒"


def test_readme_references_demo_assets():
    text = _text("README.md")
    assert "docs/demo" in text, "README 未引用演示素材目录"


def test_readme_referenced_repo_paths_exist():
    """README 引用的仓内路径必须真实存在（干净环境逐字执行 README 的守门）。

    M6 实测缺陷：快速开始第二步挂证引用 `证据文件.pdf`、第三步台账引用 `ledger.json`，
    两文件都不存在——本地开发期因工作目录残留而从未暴露，仅在 `git archive` 干净树
    逐字执行时才断链（同批缺陷还会打挂首次 CI）。本门把"README 引用的输入必须存在"
    变为常驻断言。只校验**仓内目录前缀**的路径（data/tools/docs/plan/src/tests）——
    链路上的输出文件（draft.json / ledger.csv / report.docx 等）本就不该预先存在。
    """
    import re

    text = _text("README.md")
    prefixes = ("data/", "tools/", "docs/", "plan/", "src/", "tests/")
    pattern = re.compile(r"(?:%s)[\w\u4e00-\u9fff./-]*" % "|".join(re.escape(p) for p in prefixes))
    missing = []
    for m in pattern.finditer(text):
        # 紧跟 `]` 的是 Markdown 链接**标签**（如 [plan/01](plan/01-xxx.md)），不是路径引用
        if text[m.end():m.end() + 1] == "]":
            continue
        rel = m.group(0).rstrip("./")   # 目录引用允许带尾斜杠
        if rel and not (ROOT / rel).exists():
            missing.append(rel)
    assert not missing, "README 引用了不存在的仓内路径: %s" % sorted(set(missing))


def test_readme_quickstart_fixtures_are_generated():
    """快速开始用到的示例夹具须由生成器产出（防"文档引用了没人在产的文件"）。"""
    gen = _text("tools/gen_rulesets.py")
    for name in ("evidence-demo.txt", "ledger-demo.json"):
        assert name in gen, "生成器未产出快速开始夹具: %s" % name
        assert (ROOT / "data" / "samples" / name).is_file(), \
            "快速开始夹具缺失（跑 tools/gen_rulesets.py 重生成）: %s" % name


def test_readme_quickstart_fixture_paths_are_referenced():
    """生成器产出的夹具须真的被 README 快速开始引用（防"产了但没用"）。"""
    text = _text("README.md")
    assert "data/samples/evidence-demo.txt" in text, "README 未引用示例证据文件"
    assert "data/samples/ledger-demo.json" in text, "README 未引用示例台账"


def _quickstart_block():
    """截取 README「快速开始」首个 bash 代码块（逐字执行的输入来源）。"""
    text = _text("README.md")
    marker = "## 快速开始"
    body = text[text.index(marker):]
    start = body.index("```bash") + len("```bash")
    end = body.index("```", start)
    return body[start:end]


def test_readme_quickstart_fixture_args_resolve():
    """快速开始各步的**输入**夹具（--evidence / --apply）必须真实存在。

    这是对 M6 实测缺陷的直接回归：README 曾引用 `证据文件.pdf` 与 `ledger.json`
    两个不存在的输入，本地因残留文件未暴露，干净树逐字执行即断链。
    """
    block = _quickstart_block()
    # `--evidence "ITEM=FILE"` 的 FILE 与 `--apply FILE` 都在链路上作为输入
    refs = re.findall(r'--evidence\s+"?[^"=\s]+=([^"\s]+)', block)
    refs += re.findall(r"--apply\s+([^\s\\]+)", block)
    assert refs, "未从快速开始解析到输入夹具（README 结构变了？）"
    missing = [r for r in refs if not (ROOT / r).is_file()]
    assert not missing, "快速开始引用了不存在的输入夹具: %s" % missing


def test_readme_quickstart_chain_runs_end_to_end(tmp_path):
    """逐字执行快速开始链（步骤 1–5）——干净环境跑通的常驻版本。

    以 README 里的夹具路径为输入、把链路产物写到 tmp_path；命令与顺序照抄 README，
    断言退出码符合 README「CLI 命令与退出码」表（0=完成 / 1=检出非合规）。
    DOCX 步骤需 report extra，缺则退化为 Markdown（与 README 第 5 步注释一致）。
    """
    from paudit.cli import main

    block = _quickstart_block()
    ev = re.search(r'--evidence\s+"[^"=\s]+=([^"\s]+)"', block).group(1)
    ledger = re.search(r"--apply\s+([^\s\\]+)", block).group(1)
    demo_ruleset = re.search(r"--ruleset\s+(data/samples/\S+)", block).group(1)
    assert (ROOT / ev).is_file() and (ROOT / ledger).is_file()

    draft = tmp_path / "draft.json"
    draft2 = tmp_path / "draft2.json"
    frozen = tmp_path / "frozen.json"

    # 步骤 2：单件审计 + 挂证（示例卡有问题项 → exit 1）
    rc = main(["check", str(ROOT / "data/samples/card-demo.json"),
               "--ruleset", str(ROOT / demo_ruleset), "--out", str(draft),
               "--draft", "--evidence", "CHK-DEMO-001=%s" % (ROOT / ev),
               "--evidence-owner", "审计员A"])
    assert rc == 1, "步骤2 check 期望 exit 1（检出非合规），实得 %s" % rc
    assert draft.is_file()

    # 步骤 3：整改台账
    rc = main(["ledger", str(draft), "--apply", str(ROOT / ledger),
               "-o", str(tmp_path / "ledger.csv"), "--write-draft", str(draft2)])
    assert rc == 0, "步骤3 ledger 期望 exit 0，实得 %s" % rc
    assert (tmp_path / "ledger.csv").is_file()

    # 步骤 4：底稿导出 → 导入（往返一致）
    assert main(["draft", "export", str(draft2), "-o", str(frozen),
                 "--ruleset", str(ROOT / demo_ruleset)]) == 0
    assert main(["draft", "import", str(frozen),
                 "--ruleset", str(ROOT / demo_ruleset)]) == 0

    # 步骤 5：报告导出（docx 需 extra；缺则验 md）
    ext = "docx" if _has_report_extra() else "md"
    out = tmp_path / ("report.%s" % ext)
    rc = main(["report", str(frozen), "--ruleset", str(ROOT / demo_ruleset),
               "-o", str(out), "--template", "third_party"])
    assert rc == 0, "步骤5 report(%s) 期望 exit 0，实得 %s" % (ext, rc)
    assert out.is_file() and out.stat().st_size > 0


def _has_report_extra():
    try:
        import docx  # noqa: F401
        import openpyxl  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# 非 UTF-8 locale（Windows CI 首跑实测缺陷）
# ---------------------------------------------------------------------------
def _non_utf8_env(encoding):
    import os

    env = dict(os.environ)
    env["PYTHONUTF8"] = "0"           # 关掉 UTF-8 模式
    env["PYTHONIOENCODING"] = encoding
    return env


def test_entry_points_survive_non_utf8_locale():
    """CLI / 脱敏审计器在非 UTF-8 控制台编码下不得崩（M6 首跑 CI 实测缺陷）。

    Windows CI 运行器默认 locale 为 cp1252：本仓源码/数据/输出含中文，
    ① 打印中文即 UnicodeEncodeError；② 按 locale 解码子进程输出（git ls-files
    的中文文件名）同样失败。首次 CI 三个 Windows job 有两个因此变红，Ubuntu 正常。
    本地 zh-CN（GBK）恰好不触发，故必须**显式模拟**才守得住。
    """
    import subprocess
    import sys

    env = _non_utf8_env("cp1252")
    cases = [
        ([str(ROOT / "tools" / "audit_desensitize.py"), "tracked"], 0),
        ([str(ROOT / "tools" / "audit_desensitize.py"), "selftest"], 0),
    ]
    for args, expect in cases:
        r = subprocess.run([sys.executable] + args, capture_output=True, env=env,
                           cwd=str(ROOT))
        assert r.returncode == expect, \
            "%s 在 cp1252 下 rc=%s（期望 %s）\n%s" % (
                args[-1], r.returncode, expect,
                r.stderr.decode("utf-8", "replace")[-500:])


def test_cli_main_forces_utf8_stdio():
    """CLI 入口须把 stdout/stderr 切到 UTF-8（否则 cp1252 下打印中文即崩）。"""
    text = _text("src/paudit/cli.py")
    assert "reconfigure" in text, "CLI 未做 stdout/stderr 编码兜底"
    assert "utf-8" in text


def test_cli_survives_non_utf8_locale_behaviorally():
    """行为验证：cp1252 下跑 CLI（含中文输出）不得崩。

    静态断言抓不到"兜底函数存在但没被调用"——必须真跑一次。
    """
    import subprocess
    import sys

    env = _non_utf8_env("cp1252")
    env["PYTHONPATH"] = str(ROOT / "src")
    r = subprocess.run([sys.executable, "-m", "paudit", "bench"], capture_output=True,
                       env=env, cwd=str(ROOT))
    assert r.returncode == 0, \
        "cp1252 下 CLI bench 失败 rc=%s\n%s" % (
            r.returncode, r.stderr.decode("utf-8", "replace")[-600:])



def test_no_locale_dependent_subprocess_decode():
    """子进程文本解码须显式指定编码，不得依赖 locale 默认。

    否则 Windows（cp1252）解码含中文的输出即崩——且只在非 UTF-8 机器暴露。
    允许的形态：同时出现 encoding= 参数，或用 bytes（capture_output 后自行解码）。
    """
    import re as _re

    offenders = []
    for rel in ("tools/audit_desensitize.py", "tools/gen_rulesets.py",
                "tools/gen_scenarios.py", "tools/make_demo_assets.py",
                "tests/test_repo_gate.py", "tests/test_gate_frozen.py"):
        text = _text(rel)
        for m in _re.finditer(r"subprocess\.\w+\((.*?)\)\s*$", text, _re.M | _re.S):
            call = m.group(0)
            if "text=True" in call and "encoding=" not in call:
                offenders.append("%s: %s" % (rel, call.strip()[:80]))
    assert not offenders, \
        "subprocess 以 text=True 但未指定 encoding（locale 依赖）: %s" % offenders


# ---------------------------------------------------------------------------
# 脱敏审计四步入口
# ---------------------------------------------------------------------------
def test_audit_tool_supports_all_mode():
    text = _text("tools/audit_desensitize.py")
    for mode in ("tracked", "history", "messages", "selftest"):
        assert mode in text, "脱敏审计器缺模式: %s" % mode
    assert '"all"' in text or "'all'" in text, "脱敏审计器缺 all 汇总模式"
    assert "audit-allow" in text, "脱敏审计器缺行内放行标记"


# ---------------------------------------------------------------------------
# 版本口径
# ---------------------------------------------------------------------------
def test_version_is_semver_for_release_tag():
    m = re.search(r'^version\s*=\s*"([^"]+)"', _text("pyproject.toml"), re.M)
    assert m, "pyproject 未声明 version"
    assert re.match(r"^\d+\.\d+\.\d+$", m.group(1)), \
        "版本号须为语义化（Release tag vX.Y.Z）: %s" % m.group(1)
