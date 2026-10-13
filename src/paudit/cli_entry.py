"""PyInstaller 冻结入口：CLI（spec 指向本文件）。

与 `python -m paudit` 等价；冻结态下 `sys.argv` 已由 exe 参数填充。
"""

import sys

from paudit.cli import main

if __name__ == "__main__":
    sys.exit(main())
