"""
canonical_json.py

LOCKED canonical JSON utilities for Gate C.

WHY determinism matters:
- Gate C uses canonical JSON bytes as the single source of truth for SHA-256 hashing.
- Replay verification depends on byte-identical outputs across platforms.
- Cross-agent validation requires stable canonicalization for authority checks.

LOCKED Rules:
- sort_keys=True
- ensure_ascii=True
- separators=(",", ":")
- float rounding=6 decimals
- negative_zero -> 0.0
- NaN -> null
- Infinity -> "INF"
- -Infinity -> "-INF"

IMPORTANT:
- Do NOT change algorithm or serialization parameters.
- Same input MUST produce same output on Windows/Linux/Mac (Python 3.11+).
"""

from __future__ import annotations

import json
import math
from typing import Any

FLOAT_DECIMALS: int = 6


def _normalize_float(value: float, decimals: int = FLOAT_DECIMALS) -> Any:
    """Normalize float according to LOCK rules (bit-exact).

    Args:
        value: Input float.
        decimals: Number of decimals to round finite floats.

    Returns:
        JSON-safe representation:
            - None for NaN
            - "INF"/"-INF" for infinities
            - rounded float for finite values (6 decimals), with -0.0 -> 0.0

    Raises:
        None.

    Notes:
        JSON does not support NaN/Infinity. We normalize deterministically so
        canonical JSON and hashes are reproducible across platforms.
    """
    if math.isnan(value):
        return None
    if math.isinf(value):
        return "INF" if value > 0 else "-INF"
    if value == 0.0:
        value = 0.0  # -0.0 -> 0.0 (LOCK)
    return round(value, decimals)


def canonicalize(obj: Any, decimals: int = FLOAT_DECIMALS) -> Any:
    """Canonicalize a Python object into a JSON-stable structure.

    The canonicalization is recursive:
      - dict keys are sorted (deterministic order)
      - list order is preserved
      - floats are normalized via `_normalize_float`

    Args:
        obj: Input object (dict/list/primitives).
        decimals: Float rounding precision (LOCKED default=6).

    Returns:
        Canonicalized structure composed of JSON-safe primitives.

    Raises:
        None directly. `canonical_json()` may raise if final object cannot be serialized.

    Examples:
        >>> canonical_json({"b": 2, "a": 1})
        '{"a":1,"b":2}'

        >>> canonical_json({"x": float("nan"), "y": float("inf"), "z": -0.0})
        '{"x":null,"y":"INF","z":0.0}'
    """
    if obj is None or isinstance(obj, (str, int, bool)):
        return obj

    if isinstance(obj, float):
        return _normalize_float(obj, decimals=decimals)

    if isinstance(obj, list):
        return [canonicalize(item, decimals=decimals) for item in obj]

    if isinstance(obj, dict):
        return {key: canonicalize(obj[key], decimals=decimals) for key in sorted(obj.keys())}

    return obj


def canonical_json(obj: Any, decimals: int = FLOAT_DECIMALS) -> str:
    """Serialize an object into LOCKED canonical JSON.

    Args:
        obj: Input object (typically dict/list/primitives).
        decimals: Float rounding precision (LOCKED default=6).

    Returns:
        Canonical JSON string with:
          - sort_keys=True
          - ensure_ascii=True
          - separators=(",", ":")
          - allow_nan=False

    Raises:
        ValueError: If NaN/Inf bypasses normalization (allow_nan=False).
        TypeError: If object cannot be JSON-serialized after canonicalize().

    Why:
        canonical JSON is used for SHA-256 hashing and must be deterministic:
          - parameters_hash
          - evidence_set_hash
          - receipt_hash
          - determinism_key
    """
    canon = canonicalize(obj, decimals=decimals)
    return json.dumps(
        canon,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    )
