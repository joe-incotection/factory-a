"""
constants.py — Allowlists and configuration constants for SAFE_STATS.
Source of truth: SAFE_STATS_REASON_CODES.yaml
"""

from __future__ import annotations

# Allowlisted reason codes (from SAFE_STATS_REASON_CODES.yaml v1.0).
# Any SafeStatsError raised by this package must use exactly one of these
# codes so that downstream callers can route on a stable, versioned signal.
REASON_CODE_ALLOWLIST: frozenset[str] = frozenset(
    {
        "SAFE_STATS_INPUT_SCHEMA_INVALID",   # payload is not a dict
        "SAFE_STATS_INPUT_MISSING_FIELD",    # required key absent
        "SAFE_STATS_INPUT_TYPE_MISMATCH",    # field has wrong Python type
        "SAFE_STATS_EMPTY_VALUES",           # values list is shorter than MIN_VALUES
        "SAFE_STATS_NAN_INF_DETECTED",       # NaN or Infinity found in numeric data
        "SAFE_STATS_INTERNAL_ERROR",         # unexpected exception in engine logic
    }
)

# Minimum number of items required in the 'values' array (invariant INV_INPUT_VALUES_MIN_1).
MIN_VALUES: int = 1

# Number of decimal places used when rounding floats at the canonical output
# boundary (invariant GOLDEN_IO_LOCK float_precision_decimals=6).
FLOAT_PRECISION: int = 6
