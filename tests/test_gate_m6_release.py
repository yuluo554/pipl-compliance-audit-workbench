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
