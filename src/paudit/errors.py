"""异常类型与退出码语义（定稿后锁进 CLI 测试）。"""

# CLI 退出码语义（不得漂移）
EXIT_OK = 0            # 完成
EXIT_NONCOMPLIANT = 1  # 检出非合规 / 未评估（check/scan）；基准未达标（bench）
EXIT_INPUT_ERROR = 2   # 输入不可用 / 用法错误
EXIT_MISSING_EXTRA = 3  # 缺可选依赖（如 gui）


class PauditError(Exception):
    """基础异常。"""


class RulesetError(PauditError):
    """规则包加载/校验失败。"""


class PendingEntryError(RulesetError):
    """试图使用 status=pending 的条目（未核对不得进入判定路径）。"""

    def __init__(self, entries):
        self.entries = list(entries)
        super().__init__(
            "以下条目 status=pending，未挂原文核对不得进入判定路径: "
            + ", ".join(str(e) for e in self.entries)
        )


class InputError(PauditError):
    """输入参数卡/底稿不可用。"""
