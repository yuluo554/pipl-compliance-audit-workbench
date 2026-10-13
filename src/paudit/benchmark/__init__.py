"""基准子包（零 API 依赖）。"""

from .cases import (
    NON_PASS_STATES,
    apply_op,
    expected_summary,
    expected_threshold,
    observed_nonpass,
)
from .runner import BenchmarkReport, run_all

__all__ = [
    "run_all", "BenchmarkReport",
    "expected_threshold", "expected_summary", "observed_nonpass",
    "apply_op", "NON_PASS_STATES",
]
