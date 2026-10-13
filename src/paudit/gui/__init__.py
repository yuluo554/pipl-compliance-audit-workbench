"""桌面应用子包（PySide6 只在函数体内导入）。

`session.py` 为纯 Python 数据面（零 Qt，可无头测试）；`main_window.py` 为 Qt 装配层。
"""

from .main_window import build_window, main
from .session import Session, SessionError

__all__ = ["main", "build_window", "Session", "SessionError"]
