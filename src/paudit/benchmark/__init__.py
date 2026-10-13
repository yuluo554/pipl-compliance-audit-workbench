"""基准子包（零 API 依赖）。"""

from .cases import (
    FLAGGED_STATES,
    GATE_FALSE_POSITIVE_RATE,
    GATE_STATE_ACCURACY,
    GATE_TRIGGER_ACCURACY,
    NON_PASS_STATES,
    apply_op,
    confusion,
    expected_item_state,
    expected_item_states,
    expected_summary,
    expected_threshold,
    observed_nonpass,
    rate,
)
from .runner import GATES, BenchmarkReport, run_all

__all__ = [
    "run_all", "BenchmarkReport", "GATES",
    "expected_threshold", "expected_summary", "observed_nonpass",
    "apply_op", "NON_PASS_STATES", "FLAGGED_STATES",
    "expected_item_state", "expected_item_states", "confusion", "rate",
    "GATE_TRIGGER_ACCURACY", "GATE_STATE_ACCURACY", "GATE_FALSE_POSITIVE_RATE",
]
