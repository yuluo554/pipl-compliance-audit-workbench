# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec：CLI 形态（onedir）。

与 GUI spec 共用 `tools/build_data.py` 的白名单与禁区拦截（单一实现源）。
CLI 不打包 PySide6（`excludes` 显式排除），保持产物精简。

构建：py -3.12 -m PyInstaller tools/paudit-cli.spec --noconfirm
产物：dist/paudit-cli/paudit-cli.exe（+ _internal/ 数据）
"""

import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent  # SPECPATH = tools/，其父即仓库根
sys.path.insert(0, str(ROOT / "tools"))

from build_data import collect_data_sources, verify_built_dist  # noqa: E402

datas = collect_data_sources(ROOT)

a = Analysis(
    [str(ROOT / "src" / "paudit" / "cli_entry.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=["paudit", "paudit.cli", "paudit.rules.loader",
                   "paudit.engine.pipeline", "paudit.report"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "PySide6", "PIL"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="paudit-cli",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="paudit-cli",
)

# 构建后检查：冻结产物不得夹带已显式排除的 PIL（openpyxl 的可选图像依赖）
verify_built_dist(Path(DISTPATH) / "paudit-cli")
