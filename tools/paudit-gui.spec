# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec：GUI 形态（onedir）。

数据白名单由 `tools/build_data.py` 单一实现源展开；版权禁区（官方原文快照目录，
见 data/README §二·2）在构建前即抛错拦截（三重守门之一）。用 onedir 而非 onefile：
Qt 插件目录（platforms/qwindows.dll 等）在 onefile 下解压路径不稳，onedir 更可控。

构建：py -3.12 -m PyInstaller tools/paudit-gui.spec --noconfirm
产物：dist/paudit-gui/paudit-gui.exe（+ _internal/ 数据与 Qt 插件）
"""

import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent  # SPECPATH = tools/，其父即仓库根
sys.path.insert(0, str(ROOT / "tools"))

from build_data import collect_data_sources  # noqa: E402

datas = collect_data_sources(ROOT)

a = Analysis(
    [str(ROOT / "src" / "paudit" / "gui_entry.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=["paudit.gui", "paudit.gui.main_window", "paudit.gui.session"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="paudit-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="paudit-gui",
)
