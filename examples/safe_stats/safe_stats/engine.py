"""
engine.py — Public entry point for SAFE_STATS.

Public API:
    run_safe_stats(input_payload: dict) -> dict

Contract (from GOLDEN_IO_LOCK_SAFE_STATS.yaml):
- Input:  {values: [numbers...], meta: {run_id: str}}
- Output: {summary: {count, sum, mean, min, max}, metadata: {audit_quality: "NORMAL"}}
- Determinism: no wall clock, no random, no network
- Floats rounded to FLOAT_PRECISION (6) decimals at canonical boundary
- Raises SafeStatsError on any hard-fail
"""

from __future__ import annotations

import math

from .constants import FLOAT_PRECISION
from .exceptions import SafeStatsError
from .validation import validate_input


def run_safe_stats(input_payload: dict) -> dict:
    """Convert a numeric series into a deterministic statistical summary.

    This is the sole public entry point of the ``safe_stats`` package.  The
    function is designed to be fully deterministic: given the same input it
    always produces byte-for-byte identical output with no dependence on wall
    clock time, random state, or network resources.

    Args:
        input_payload: A dict with the following structure::

            {
                "values": [<finite numbers>],   # non-empty list, int or float
                "meta":   {"run_id": "<str>"}   # audit identifier
            }

    Returns:
        A dict matching the GOLDEN_IO_LOCK output contract::

            {
                "summary": {
                    "count": int,    # number of elements in 'values'
                    "sum":   float,  # rounded to FLOAT_PRECISION decimals
                    "mean":  float,  # clamped to [min, max] after rounding
                    "min":   float,
                    "max":   float,
                },
                "metadata": {
                    "audit_quality": "NORMAL",
                },
            }

    Raises:
        SafeStatsError: On any validation failure or unexpected internal error.
            ``reason_codes`` will contain exactly one code from
            ``REASON_CODE_ALLOWLIST``.
    """
    # Validate input — raises SafeStatsError with an allowlisted reason code
    # on any violation.  Unexpected exceptions are wrapped to prevent raw
    # Python tracebacks from leaking to callers.
    try:
        validate_input(input_payload)
    except Exception as exc:
        if isinstance(exc, SafeStatsError):
            raise
        raise SafeStatsError(
            reason_codes=["SAFE_STATS_INTERNAL_ERROR"],
            message=f"Unexpected error during input validation: {exc}",
        ) from exc

    values: list[int | float] = input_payload["values"]

    # Compute statistics — pure arithmetic, no wall clock, no random.
    # Any non-SafeStatsError exception is caught and re-raised as an
    # INTERNAL_ERROR so callers always receive a typed, allowlisted error.
    try:
        n: int = len(values)

        # Normalize all values to float so arithmetic is uniform regardless of
        # whether the caller supplied ints, floats, or a mix.
        floats = [float(v) for v in values]

        total: float = sum(floats)
        min_val: float = min(floats)
        max_val: float = max(floats)
        mean_val: float = total / n

        # Secondary NaN/Inf guard at the output boundary (invariant INV_NO_NAN_INF).
        # Validation already rejects NaN/Inf in the input, but very large finite
        # values could produce Inf via floating-point overflow in sum(), so we
        # check each computed statistic before proceeding to rounding.
        for label, val in (
            ("sum", total),
            ("mean", mean_val),
            ("min", min_val),
            ("max", max_val),
        ):
            if math.isnan(val) or math.isinf(val):
                raise SafeStatsError(
                    reason_codes=["SAFE_STATS_NAN_INF_DETECTED"],
                    message=(
                        f"Computed '{label}' is NaN or Infinity — "
                        "check input values for overflow"
                    ),
                )

        # Round each statistic to the canonical boundary precision.
        r_min = round(min_val, FLOAT_PRECISION)
        r_max = round(max_val, FLOAT_PRECISION)
        r_mean = round(mean_val, FLOAT_PRECISION)

        # Clamp r_mean to [r_min, r_max] (invariant INV_MEAN_WITHIN_BOUNDS).
        # When min, mean, and max are rounded independently, the rounded mean
        # can drift outside [rounded_min, rounded_max] by up to ±0.5 ULP at
        # the 6th decimal place.  The clamp makes the invariant exact.
        r_mean = max(r_min, min(r_max, r_mean))

        summary: dict = {
            "count": n,                          # always int, never float
            "sum": round(total, FLOAT_PRECISION),
            "mean": r_mean,
            "min": r_min,
            "max": r_max,
        }

    except SafeStatsError:
        # Re-raise typed errors unchanged so reason_codes reach the caller.
        raise
    except Exception as exc:
        raise SafeStatsError(
            reason_codes=["SAFE_STATS_INTERNAL_ERROR"],
            message=f"Unexpected error during computation: {exc}",
        ) from exc

    result: dict = {
        "summary": summary,
        "metadata": {
            # Fixed sentinel value declared in the output contract.
            "audit_quality": "NORMAL",
        },
    }

    return result
