"""演示素材生成器（M6 Release 附件用）：GUI 四页签截图 + 演示 GIF + CLI 基准卡片。

用途：给 GitHub Release 附**可复现**的演示素材——不靠人工录屏。
全部素材由脚本离线合成（零网络、零真实数据），随参数重跑结果一致。

用法：
  python tools/make_demo_assets.py                 # 写出到 docs/demo/
  python tools/make_demo_assets.py --out dist/demo
  python tools/make_demo_assets.py --no-gif        # 只出 PNG（无 Pillow 时的降级路径）

产出：
  01-trigger.png      触发判定页签（门槛结论 + 义务分栏）
  02-checklist.png    检查单页签（全项四态 + 依据）
  03-evidence.png     证据链页签（挂证 sha256 + 整改台账）
  04-report.png       报告导出页签（三格式导出日志）
  demo.gif            四帧轮播（时长由 --frame-ms 控制）
  cli-bench.png       CLI 基准输出卡片（206/206）
  MANIFEST.json       产物清单 + sha256（可核对）

纪律：
- offscreen 渲染须**显式注册 CJK 字体**（Qt offscreen 后端无 fontconfig，
  否则中文全为豆腐块）；字体按系统目录扫描选取，不写死个人路径；
- 演示一律用 `data/samples/` 示例规则包与合成的示例参数卡（非法规门槛）；
- 素材产物**入仓跟踪**（`docs/demo/`，供 README 内联展示 + Release 附件复用）；
  重跑须逐字节一致（脚本零随机源、零系统时钟）。
"""

import argparse
import hashlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
DEMO_RULESET = ROOT / "data" / "samples" / "ruleset-pipl-audit-demo.json"
DEMO_CARD = ROOT / "data" / "samples" / "card-demo.json"

TAB_TITLES = ("触发判定", "检查单", "证据链", "报告导出")

# 演示用最小证据文件（合成内容，非真实材料）
DEMO_EVIDENCE_BODY = "演示证据：示例企业隐私政策评审记录（合成材料，非真实）。\n"

# 演示台账：只补责任落实三字段（owner/due/status），不改判定结论
DEMO_LEDGER = (
    {"risk": "high", "owner": "合规负责人", "due": "2026-12-31", "status": "in_progress"},
    {"risk": "medium", "owner": "安全工程师", "due": "2026-11-30", "status": "open"},
)

# 显式注册的字体候选（按特征名匹配，不写死个人目录）
FONT_NAMES = ("msyh.ttc", "msyhbd.ttc", "simhei.ttf", "simsun.ttc", "Deng.ttf", "arial.ttf")
FONT_FAMILIES = ("Microsoft YaHei", "SimHei", "DengXian", "SimSun", "Arial")


def _windows_font_dirs():
    """系统字体目录（从环境变量取，避免写死盘符路径）。"""
    dirs = []
    windir = os.environ.get("WINDIR") or os.environ.get("SystemRoot")
    if windir:
        dirs.append(Path(windir) / "Fonts")
    local = os.environ.get("LOCALAPPDATA")
    if local:
        dirs.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
    return [d for d in dirs if d.is_dir()]


def find_font_file():
    """按候选名在系统字体目录里找可用字体文件（找不到返回 None）。"""
    for d in _windows_font_dirs():
        for name in FONT_NAMES:
            p = d / name
            if p.is_file():
                return p
    return None


def configure_offscreen():
    """在**导入 Qt 前**固定 offscreen 后端，并指向系统字体目录。"""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    font_file = find_font_file()
    if font_file is not None:
        os.environ.setdefault("QT_QPA_FONTDIR", str(font_file.parent))
    return font_file


def _apply_font(app, font_file):
    """注册并应用 CJK 字体；返回实际族名（可能为 None）。"""
    from PySide6.QtGui import QFont, QFontDatabase

    if font_file is not None:
        QFontDatabase.addApplicationFont(str(font_file))
    families = set(QFontDatabase.families())
    for fam in FONT_FAMILIES:
        if fam in families:
            app.setFont(QFont(fam, 10))
            return fam
    return None


def _pump(app, times=3):
    for _ in range(times):
        app.processEvents()


def _prepare_session(window):
    """载入示例规则包 + 参数卡并跑判定（与 CLI 同编排源）。"""
    window.session.load_ruleset(str(DEMO_RULESET))
    window.session.load_card(str(DEMO_CARD))
    window.session.run()
    window._refresh_all()


def _attach_demo_evidence(window, evidence_dir):
    """挂一条演示证据（仅登记文件名 + sha256）并填写台账。"""
    evidence_dir.mkdir(parents=True, exist_ok=True)
    ev_file = evidence_dir / "demo-evidence.txt"
    ev_file.write_text(DEMO_EVIDENCE_BODY, encoding="utf-8")
    item_ids = window.session.item_ids()
    if not item_ids:
        return None
    target = item_ids[0]
    window.session.attach_evidence(
        target, str(ev_file), collected_at="2026-10-14", owner="审计员A")
    window._refresh_all()
    return target


def _set_ledger(window):
    """按风险级把演示台账写进底稿（只写 owner/due/status）。"""
    entries = []
    for row in window.session.findings_rows():
        for demo in DEMO_LEDGER:
            if row.get("risk") == demo["risk"]:
                entries.append({
                    "finding_id": row["finding_id"],
                    "owner": demo["owner"],
                    "due": demo["due"],
                    "status": demo["status"],
                })
                break
    if entries:
        window.session.set_ledger(entries)
        window._refresh_all()
    return entries


def capture_tabs(out_dir, width=1080, height=720):
    """离屏渲染四页签为 PNG，返回 [(路径, 页签名)]。"""
    font_file = configure_offscreen()

    sys.path.insert(0, str(SRC))
    from PySide6.QtWidgets import QApplication

    from paudit.gui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    family = _apply_font(app, font_file)

    window = MainWindow()
    _prepare_session(window)
    window.win.resize(width, height)
    window.win.show()
    _pump(app)

    out_dir.mkdir(parents=True, exist_ok=True)
    produced = []
    for idx, title in enumerate(TAB_TITLES):
        window._tabs.setCurrentIndex(idx)
        if title == "证据链":
            with tempfile.TemporaryDirectory(prefix="paudit-demo-") as td:
                _attach_demo_evidence(window, Path(td))
                _set_ledger(window)
                _pump(app)
                path = out_dir / ("%02d-%s.png" % (idx + 1, _slug(idx)))
                window.win.grab().save(str(path))
        elif title == "报告导出":
            window._log("（演示）模板 self → 报告已写出：report.md")
            window._log("（演示）模板 third_party → 报告已写出：report.docx")
            window._log("（演示）底稿已导出：draft.json（draft_sha256 已固化）")
            _pump(app)
            path = out_dir / ("%02d-%s.png" % (idx + 1, _slug(idx)))
            window.win.grab().save(str(path))
        else:
            path = out_dir / ("%02d-%s.png" % (idx + 1, _slug(idx)))
            window.win.grab().save(str(path))
        produced.append((path, title))

    window.win.close()
    print("字体族：%s" % (family or "（未匹配到 CJK 字体，中文可能显示为方块）"))
    return produced


def _slug(index):
    return ("trigger", "checklist", "evidence", "report")[index]


def compose_gif(frames, gif_path, frame_ms=1400, max_width=880):
    """用 Pillow 把四张截图串成 GIF；无 Pillow 时返回 None（降级，不失败）。"""
    try:
        from PIL import Image
    except ImportError:
        print("未安装 Pillow → 跳过 GIF（PNG 截图已生成）")
        return None

    images = []
    for path, _title in frames:
        img = Image.open(str(path)).convert("RGB")
        if img.width > max_width:
            ratio = max_width / float(img.width)
            img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
        images.append(img)
    if not images:
        return None
    images[0].save(str(gif_path), save_all=True, append_images=images[1:],
                   duration=frame_ms, loop=0, optimize=True)
    print("GIF 已写出：%s（%d 帧）" % (gif_path, len(images)))
    return gif_path


def cli_bench_card(out_path):
    """渲染一张 CLI 基准输出卡片（纯 Pillow，不依赖 Qt）。

    字体须含 CJK 字形（基准输出为中文标签 + ASCII 数值），故不用 Consolas/Courier
    这类纯 ASCII 等宽字体——否则中文渲染为豆腐块。
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("未安装 Pillow → 跳过 CLI 基准卡片")
        return None

    font_file = find_font_file()
    body_font = ImageFont.truetype(str(font_file), 17) if font_file else ImageFont.load_default()
    title_font = ImageFont.truetype(str(font_file), 21) if font_file else ImageFont.load_default()

    bench_text = _bench_output()
    lines = bench_text.strip().splitlines()
    pad, line_h = 24, 26
    title = "paudit bench（权威规则包，离线可跑）"
    # 按实测文本宽度定卡片宽度，避免右侧截断（中文标签 + 长指标行）
    probe = Image.new("RGB", (8, 8))
    pdraw = ImageDraw.Draw(probe)
    widths = [pdraw.textlength(title, font=title_font)]
    widths += [pdraw.textlength(ln, font=body_font) for ln in lines]
    width = int(max(widths)) + pad * 2
    height = pad * 3 + line_h * (len(lines) + 1)
    img = Image.new("RGB", (width, height), (30, 32, 38))
    draw = ImageDraw.Draw(img)
    draw.text((pad, pad), title, font=title_font, fill=(240, 240, 240))
    y = pad * 2
    for line in lines:
        color = (126, 231, 135) if "206/206" in line or "达标=True" in line else (220, 220, 220)
        draw.text((pad, y), line, font=body_font, fill=color)
        y += line_h
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out_path))
    print("CLI 基准卡片已写出：%s" % out_path)
    return out_path


def _bench_output():
    """跑一次基准并抓取文本输出（子进程隔离，避免污染本进程导入状态）。

    默认权威规则包（README 对外的 206/206 口径），非示例包。
    """
    import subprocess

    proc = subprocess.run(
        [sys.executable, "-m", "paudit", "bench"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT), env=dict(os.environ, PYTHONPATH=str(SRC)))
    return proc.stdout or (proc.stdout + proc.stderr)


def _sha256(path):
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


def write_manifest(out_dir, files):
    entries = []
    for p in files:
        p = Path(p)
        if p.is_file():
            entries.append({"file": p.name, "bytes": p.stat().st_size, "sha256": _sha256(p)})
    manifest = {"generator": "tools/make_demo_assets.py", "files": entries}
    mp = out_dir / "MANIFEST.json"
    with open(mp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    print("清单已写出：%s（%d 项）" % (mp, len(entries)))
    return mp


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(description="生成演示素材（截图 / GIF / CLI 卡片）")
    ap.add_argument("--out", default=str(ROOT / "docs" / "demo"), help="产物目录")
    ap.add_argument("--frame-ms", type=int, default=1400, help="GIF 每帧时长（毫秒）")
    ap.add_argument("--no-gif", action="store_true", help="不合成 GIF（只出 PNG）")
    args = ap.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    frames = capture_tabs(out_dir)
    produced = [p for p, _ in frames]

    gif = None
    if not args.no_gif:
        gif = compose_gif(frames, out_dir / "demo.gif", frame_ms=args.frame_ms)
    if gif:
        produced.append(gif)

    card = cli_bench_card(out_dir / "cli-bench.png")
    if card:
        produced.append(card)

    write_manifest(out_dir, produced)
    print("完成：%d 项素材 → %s" % (len(produced), out_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
