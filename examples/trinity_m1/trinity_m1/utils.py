"""
TRINITY_M1 — Pure Deterministic Utilities
Canonicalization, hashing, and validation helpers.
No wall-clock. No randomness.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, List

from trinity_m1.constants import (
    CANONICAL_ALLOW_NAN,
    CANONICAL_FLOAT_PRECISION,
    CANONICAL_SORT_KEYS,
    RC_INPUT_MISSING_FIELD,
    RC_INPUT_SCHEMA_INVALID,
    RC_INPUT_TYPE_MISMATCH,
    RC_INSUFFICIENT_BARS,
    RC_NAN_INF_DETECTED,
    RC_SYMBOL_INVALID,
    RC_TIMESTAMP_INVALID,
    MIN_BARS,
)
from trinity_m1.exceptions import TrinityM1Error
from trinity_m1.models import BarItem, InputPayload, MetaInput


# ---------------------------------------------------------------------------
# Canonicalization
# ---------------------------------------------------------------------------

def _normalize_value(x: Any, float_precision: int) -> Any:
    """Recursively normalize a value for canonical JSON.

    Args:
        x: Value to normalize.
        float_precision: Decimal precision for floats.

    Returns:
        Normalized value.

    Raises:
        ValueError: If NaN or Infinity encountered.
    """
    if isinstance(x, float):
        if math.isnan(x) or math.isinf(x):
            raise ValueError("NaN/Infinity not allowed in canonical_json")
        return round(x, float_precision)
    if isinstance(x, list):
        return [_normalize_value(i, float_precision) for i in x]
    if isinstance(x, dict):
        return {k: _normalize_value(v, float_precision) for k, v in x.items()}
    return x


def canonical_json(
    obj: Any,
    float_precision_decimals: int = CANONICAL_FLOAT_PRECISION,
) -> str:
    """Produce canonical JSON string per Factory-A law.

    Rules:
    - sort_keys = True
    - float precision = float_precision_decimals
    - NaN/Infinity not allowed

    Args:
        obj: Python object to serialize.
        float_precision_decimals: Decimal precision for floats.

    Returns:
        Canonical JSON string.

    Raises:
        ValueError: If NaN/Infinity found.
    """
    normed = _normalize_value(obj, float_precision_decimals)
    return json.dumps(
        normed,
        sort_keys=CANONICAL_SORT_KEYS,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def sha256_hex(s: str) -> str:
    """Compute SHA-256 hex digest of a UTF-8 string.

    Args:
        s: Input string.

    Returns:
        Hex SHA-256 string.
    """
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def hash_output(obj: Any, float_precision_decimals: int = CANONICAL_FLOAT_PRECISION) -> str:
    """Canonical JSON → SHA-256 hash of an output payload dict.

    Args:
        obj: Output payload dict.
        float_precision_decimals: Decimal precision.

    Returns:
        Hex SHA-256 string.
    """
    cj = canonical_json(obj, float_precision_decimals)
    return sha256_hex(cj)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def validate_input(raw: dict) -> InputPayload:
    """Validate and parse raw input dict into InputPayload.

    Args:
        raw: Raw input dictionary.

    Returns:
        Validated InputPayload.

    Raises:
        TrinityM1Error: On any validation failure with allowlisted reason codes.
    """
    if not isinstance(raw, dict):
        raise TrinityM1Error(
            reason_codes=[RC_INPUT_SCHEMA_INVALID],
            message="Input must be a dict",
        )

    # Check required top-level fields
    for field in ("symbol", "timeframe", "bars", "meta"):
        if field not in raw:
            raise TrinityM1Error(
                reason_codes=[RC_INPUT_MISSING_FIELD],
                message=f"Missing required field: {field}",
            )

    # Validate symbol
    symbol = raw["symbol"]
    if not isinstance(symbol, str) or not symbol.strip():
        raise TrinityM1Error(
            reason_codes=[RC_SYMBOL_INVALID],
            message=f"symbol must be a non-empty string, got: {symbol!r}",
        )

    # Validate timeframe
    timeframe = raw["timeframe"]
    if not isinstance(timeframe, str) or not timeframe.strip():
        raise TrinityM1Error(
            reason_codes=[RC_INPUT_TYPE_MISMATCH],
            message=f"timeframe must be a non-empty string, got: {timeframe!r}",
        )

    # Validate meta
    meta_raw = raw["meta"]
    if not isinstance(meta_raw, dict):
        raise TrinityM1Error(
            reason_codes=[RC_INPUT_TYPE_MISMATCH],
            message="meta must be a dict",
        )
    for mf in ("source", "run_id"):
        if mf not in meta_raw:
            raise TrinityM1Error(
                reason_codes=[RC_INPUT_MISSING_FIELD],
                message=f"meta missing required field: {mf}",
            )
        if not isinstance(meta_raw[mf], str):
            raise TrinityM1Error(
                reason_codes=[RC_INPUT_TYPE_MISMATCH],
                message=f"meta.{mf} must be a string",
            )
    meta = MetaInput(source=meta_raw["source"], run_id=meta_raw["run_id"])

    # Validate bars
    bars_raw = raw["bars"]
    if not isinstance(bars_raw, list):
        raise TrinityM1Error(
            reason_codes=[RC_INPUT_TYPE_MISMATCH],
            message="bars must be a list",
        )
    if len(bars_raw) < MIN_BARS:
        raise TrinityM1Error(
            reason_codes=[RC_INSUFFICIENT_BARS],
            message=f"bars must have at least {MIN_BARS} items, got {len(bars_raw)}",
        )

    bars: List[BarItem] = []
    for i, bar in enumerate(bars_raw):
        if not isinstance(bar, dict):
            raise TrinityM1Error(
                reason_codes=[RC_INPUT_TYPE_MISMATCH],
                message=f"bars[{i}] must be a dict",
            )
        for bf in ("ts_utc", "o", "h", "l", "c", "v"):
            if bf not in bar:
                raise TrinityM1Error(
                    reason_codes=[RC_INPUT_MISSING_FIELD],
                    message=f"bars[{i}] missing field: {bf}",
                )

        # Validate ts_utc
        ts_utc = bar["ts_utc"]
        if not isinstance(ts_utc, str) or not ts_utc.strip():
            raise TrinityM1Error(
                reason_codes=[RC_TIMESTAMP_INVALID],
                message=f"bars[{i}].ts_utc must be a non-empty string",
            )

        # Validate numeric fields
        for nf in ("o", "h", "l", "c", "v"):
            val = bar[nf]
            if not isinstance(val, (int, float)):
                raise TrinityM1Error(
                    reason_codes=[RC_INPUT_TYPE_MISMATCH],
                    message=f"bars[{i}].{nf} must be numeric, got {type(val).__name__}",
                )
            fval = float(val)
            if math.isnan(fval) or math.isinf(fval):
                raise TrinityM1Error(
                    reason_codes=[RC_NAN_INF_DETECTED],
                    message=f"bars[{i}].{nf} is NaN/Inf",
                )

        bars.append(
            BarItem(
                ts_utc=bar["ts_utc"],
                o=float(bar["o"]),
                h=float(bar["h"]),
                l=float(bar["l"]),
                c=float(bar["c"]),
                v=float(bar["v"]),
            )
        )

    return InputPayload(
        symbol=symbol,
        timeframe=timeframe,
        bars=bars,
        meta=meta,
    )
