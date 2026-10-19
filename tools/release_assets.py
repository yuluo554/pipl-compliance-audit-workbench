#!/usr/bin/env python3
"""Release 附件打包与台账（可复跑、可核对）。

子命令：
  pack     把 dist/paudit-cli、dist/paudit-gui 打成固定格式 zip（确定性）
  ledger   列出发布目录下 zip 的 sha256 与字节数（JSON）
  selftest 阳性/阴性对照：同输入两次打包逐字节一致；改一个字节即不同

确定性约束（与报告产物同口径）：
- 条目按相对路径排序；
- 每个条目 date_time 固定 (1980,1,1,0,0,0)、create_system=0；
- 只写相对路径（ASCII 名），不写本机绝对路径；
- 压缩级别固定。

注意：`pack` 会先调用 `tools/build_data.py` 的 `verify_built_dist()`，
产物树若夹带已排除的 PIL 则拒绝打包。
"""

import argparse
import hashlib
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
FIXED_DATE_TIME = (1980, 1, 1, 0, 0, 0)
PACKAGES = ("paudit-cli", "paudit-gui")
ZIP_SUFFIX = "-win64.zip"


def _import_build_data():
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    import build_data  # noqa: E402

    return build_data


def project_version():
    """从 pyproject.toml 读版本（不 import 包，避免依赖安装状态）。"""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    if not m:
        raise SystemExit("pyproject.toml 未声明 version")
    return m.group(1)


def _zip_info(name):
    info = zipfile.ZipInfo(name, date_time=FIXED_DATE_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 0
    info.external_attr = 0o600 << 16
    return info


def pack_tree(src_dir, out_zip, arc_root=None):
    """把 src_dir 下的文件按固定规则打成 zip。返回 (条目数, 字节数, sha256)。"""
    src = Path(src_dir)
    if not src.is_dir():
        raise SystemExit("打包源目录不存在: %s" % src)
    files = sorted(p for p in src.rglob("*") if p.is_file())
    if not files:
        raise SystemExit("打包源目录为空: %s" % src)

    out_zip = Path(out_zip)
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as zf:
        for f in files:
            rel = f.relative_to(src).as_posix()
            name = "%s/%s" % (arc_root, rel) if arc_root else rel
            try:
                name.encode("ascii")
            except UnicodeEncodeError:
                raise SystemExit("附件条目名必须为 ASCII: %s" % name)
            zf.writestr(_zip_info(name), f.read_bytes())

    payload = out_zip.read_bytes()
    return len(files), len(payload), hashlib.sha256(payload).hexdigest()


def ledger_entries(release_dir):
    entries = []
    for z in sorted(Path(release_dir).glob("*.zip")):
        payload = z.read_bytes()
        entries.append({
            "name": z.name,
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        })
    return entries


def cmd_pack(args):
    build_data = _import_build_data()
    version = args.version or project_version()
    dist = Path(args.dist)
    out_dir = Path(args.out)
    results = []
    for package in PACKAGES:
        src = dist / package
        # 先做构建后检查：夹带 PIL 等已排除包则拒绝打包
        build_data.verify_built_dist(src)
        out_zip = out_dir / ("%s-v%s%s" % (package, version, ZIP_SUFFIX))
        count, size, digest = pack_tree(src, out_zip, arc_root=package)
        results.append({"name": out_zip.name, "entries": count,
                        "bytes": size, "sha256": digest})
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


def cmd_ledger(args):
    entries = ledger_entries(args.release)
    if not entries:
        print("发布目录下没有 zip: %s" % args.release, file=sys.stderr)
        return 2
    print(json.dumps(entries, ensure_ascii=False, indent=2))
    return 0


def _read_zip(path):
    with zipfile.ZipFile(path) as zf:
        return [(i.filename, i.date_time, i.create_system) for i in zf.infolist()]


def cmd_selftest(args):
    with tempfile.TemporaryDirectory(prefix="paudit-release-selftest-") as td:
        root = Path(td)
        src = root / "tree"
        (src / "sub").mkdir(parents=True)
        (src / "a.txt").write_bytes(b"alpha")
        (src / "sub" / "b.txt").write_bytes(b"beta")

        z1 = root / "one.zip"
        z2 = root / "two.zip"
        pack_tree(src, z1, arc_root="pkg")
        pack_tree(src, z2, arc_root="pkg")
        assert z1.read_bytes() == z2.read_bytes(), "同输入两次打包不一致"

        e1 = ledger_entries(root)
        assert [e["sha256"] for e in e1 if e["name"] == "one.zip"] == \
               [e["sha256"] for e in e1 if e["name"] == "two.zip"], "台账哈希不一致"

        infos = _read_zip(z1)
        names = [i[0] for i in infos]
        assert names == sorted(names), "zip 条目未排序"
        assert all(i[1] == FIXED_DATE_TIME for i in infos), "zip 时间戳未固定"
        assert all(i[2] == 0 for i in infos), "zip create_system 未固定"
        assert all(n.isascii() for n in names), "zip 条目名非 ASCII"

        # 阴性对照：改一个字节 → 产物哈希必须变化
        (src / "sub" / "b.txt").write_bytes(b"beta!")
        z3 = root / "three.zip"
        pack_tree(src, z3, arc_root="pkg")
        assert z3.read_bytes() != z1.read_bytes(), "内容变化未反映到 zip"

        # 阴性对照：非 ASCII 条目名必须被拒绝
        bad = root / "bad"
        bad.mkdir()
        (bad / "中文.txt").write_bytes(b"x")
        try:
            pack_tree(bad, root / "bad.zip")
        except SystemExit:
            pass
        else:
            raise AssertionError("非 ASCII 条目名未被拒绝")

    print("SELFTEST OK")
    return 0


def _build_parser():
    p = argparse.ArgumentParser(prog="release_assets.py",
                                description="Release 附件打包 / 台账 / 自检")
    sub = p.add_subparsers(dest="command")

    pack = sub.add_parser("pack", help="打包 dist 下两个 onedir 产物为确定性 zip")
    pack.add_argument("--dist", default=str(ROOT / "dist"), help="构建产物根目录")
    pack.add_argument("--out", default=str(ROOT / "dist" / "release"), help="zip 输出目录")
    pack.add_argument("--version", default=None, help="版本号（默认读 pyproject.toml）")
    pack.set_defaults(func=cmd_pack)

    led = sub.add_parser("ledger", help="列出发布目录 zip 的 sha256/字节数")
    led.add_argument("--release", default=str(ROOT / "dist" / "release"), help="发布目录")
    led.set_defaults(func=cmd_ledger)

    st = sub.add_parser("selftest", help="确定性阳性/阴性对照")
    st.set_defaults(func=cmd_selftest)
    return p


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
