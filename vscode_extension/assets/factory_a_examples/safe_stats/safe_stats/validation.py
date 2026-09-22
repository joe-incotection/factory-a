"""
validation.py — Input validation for SAFE_STATS.

Validates input_payload against GOLDEN_IO_LOCK_SAFE_STATS.yaml input_contract.
Raises SafeStatsError with allowlisted reason codes on any hard-fail.
"""

from __future__ import annotations

import math
from typing import Any

from .constants import MIN_VALUES, REASON_CODE_ALLOWLIST
from .exceptions import SafeStatsError


def _hard_fail(reason_code: str, message: str) -> None:
    """Raise SafeStatsError for a single allowlisted reason code.

    The assertion acts as a developer-time guard: if a caller ever passes an
    unregistered code the bug is surfaced immediately rather than silently
    emitting a non-allowlisted code into the wild.

    Args:
        reason_code: One of the codes from REASON_CODE_ALLOWLIST.
        message: Human-readable diagnostic; callers must not route on this.

    Raises:
        AssertionError: If ``reason_code`` is not in REASON_CODE_ALLOWLIST
            (developer bug, not a runtime user error).
        SafeStatsError: Always raised when the assertion passes.
    """
    # Developer-time guard: the allowlist is the canonical set of valid codes.
    assert reason_code in REASON_CODE_ALLOWLIST, (
        f"BUG: reason code '{reason_code}' not in allowlist — fix the code"
    )
    raise SafeStatsError(reason_codes=[reason_code], message=message)


def validate_input(payload: Any) -> None:
    """Validate the input payload against the GOLDEN_IO_LOCK input_contract.

    Checks are applied in dependency order so that the first meaningful error
    is reported rather than a cascade of confusing secondary failures.

    Required top-level fields:
        - ``values``: non-empty list of at least MIN_VALUES finite numbers.
        - ``meta``: dict containing at least ``run_id`` (str).

    Args:
        payload: The raw object passed by the caller to ``run_safe_stats``.
            Expected to be a dict; any other type triggers a schema error.

    Raises:
        SafeStatsError: On any hard-fail condition.  The ``reason_codes``
            attribute will contain exactly one code from REASON_CODE_ALLOWLIST.
    """
    # Top-level must be a dict — anything else is a schema violation.
    if not isinstance(payload, dict):
        _hard_fail(
            "SAFE_STATS_INPUT_SCHEMA_INVALID",
            f"input_payload must be a dict, got {type(payload).__name__!r}",
        )

    # Both 'values' and 'meta' are mandatory; check before dereferencing them.
    for field in ("values", "meta"):
        if field not in payload:
            _hard_fail(
                "SAFE_STATS_INPUT_MISSING_FIELD",
                f"Required field '{field}' is missing from input_payload",
            )

    values = payload["values"]
    meta = payload["meta"]

    # --- values validation ---

    if not isinstance(values, list):
        _hard_fail(
            "SAFE_STATS_INPUT_TYPE_MISMATCH",
            f"'values' must be a list, got {type(values).__name__!r}",
        )

    if len(values) < MIN_VALUES:
        _hard_fail(
            "SAFE_STATS_EMPTY_VALUES",
            f"'values' must have at least {MIN_VALUES} item(s); got {len(values)}",
        )

    for idx, item in enumerate(values):
        # bool is a subclass of int in Python, so the isinstance(item, int) check
        # below would accept True/False as numbers — reject bools explicitly first.
        if isinstance(item, bool):
            _hard_fail(
                "SAFE_STATS_INPUT_TYPE_MISMATCH",
                f"'values[{idx}]' is bool, which is not a numeric type",
            )
        if not isinstance(item, (int, float)):
            _hard_fail(
                "SAFE_STATS_INPUT_TYPE_MISMATCH",
                f"'values[{idx}]' must be a number, got {type(item).__name__!r}: {item!r}",
            )
        # NaN and Infinity are only representable as float in Python;
        # integers are always finite, so skip the isfinite check for them.
        if isinstance(item, float) and not math.isfinite(item):
            _hard_fail(
                "SAFE_STATS_NAN_INF_DETECTED",
                f"'values[{idx}]' contains NaN or Infinity: {item!r}",
            )

    # --- meta validation ---

    if not isinstance(meta, dict):
        _hard_fail(
            "SAFE_STATS_INPUT_TYPE_MISMATCH",
            f"'meta' must be an object/dict, got {type(meta).__name__!r}",
        )

    if "run_id" not in meta:
        _hard_fail(
            "SAFE_STATS_INPUT_MISSING_FIELD",
            "'meta.run_id' is required but missing",
        )

    if not isinstance(meta["run_id"], str):
        _hard_fail(
            "SAFE_STATS_INPUT_TYPE_MISMATCH",
            f"'meta.run_id' must be a string, got {type(meta['run_id']).__name__!r}",
        )
