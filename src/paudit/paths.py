"""数据目录定位（源码态 / 冻结态统一入口）。

优先级：显式参数 > 环境变量 PAUDIT_DATA_DIR > 冻结态内嵌（PyInstaller）> CWD 上溯。
"""

import os
import sys
from pathlib import Path

ENV_DATA_DIR = "PAUDIT_DATA_DIR"
_DATA_MARKER = "rules"  # data/ 下必须有该子目录才认定为数据根


def _looks_like_data_dir(p):
    return (p / _DATA_MARKER).is_dir()


def _frozen_candidates():
    """PyInstaller 冻结态候选：6.x 有 _internal/，5.x 平铺。"""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        base = Path(meipass)
        yield base / "data"
        yield base / "_internal" / "data"
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        yield exe_dir / "data"
        yield exe_dir / "_internal" / "data"


def find_data_dir(explicit=None):
    """定位 data/ 目录；找不到抛 FileNotFoundError。"""
    if explicit:
        p = Path(explicit)
        if _looks_like_data_dir(p):
            return p
        raise FileNotFoundError("指定的数据目录不含 rules/ 子目录: %s" % p)

    env = os.environ.get(ENV_DATA_DIR)
    if env:
        p = Path(env)
        if _looks_like_data_dir(p):
            return p

    for cand in _frozen_candidates():
        if _looks_like_data_dir(cand):
            return cand

    # 源码态：从当前文件上溯找 data/
    for start in (Path(__file__).resolve(), Path.cwd().resolve()):
        for parent in [start] + list(start.parents):
            cand = parent / "data"
            if _looks_like_data_dir(cand):
                return cand

    raise FileNotFoundError("未找到 data/ 目录；可用 PAUDIT_DATA_DIR 显式指定")
