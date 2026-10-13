"""PyInstaller 冻结入口：GUI（spec 指向本文件，非 `-m` 形态）。

冻结态需把 `src/` 加入 sys.path（Analysis 的 pathex 已带，此处兜底），
再委派 `paudit.gui.main()`。
"""

import os
import sys

if getattr(sys, "frozen", False):
    # 冻结态：包已打进 PYZ，直接导入即可；保证 data/ 定位走 paths 的冻结态候选
    os.environ.setdefault("QT_QPA_PLATFORM", "windows")

from paudit.gui import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
