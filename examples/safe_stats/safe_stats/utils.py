"""
utils.py — Deterministic canonicalization and hashing utilities for SAFE_STATS.

Rules (from GOLDEN_IO_LOCK_SAFE_STATS.yaml):
- sort_keys = true
- float_precision_decimals = 6
- allow_nan = false
- sha256 over UTF-8 encoded canonical JSON bytes
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from .constants import FLOAT_PRECISION


def canonical_json(obj: Any, *, float_precision_decimals: int = FLOAT_PRECISION) -> str:
    """Produce a deterministic canonical JSON string per GOLDEN_IO_LOCK rules.

    The output is byte-for-byte stable for equal inputs regardless of Python
    version or dict insertion order, because keys are always sorted and floats
    are normalized to a fixed number of decimal places before serialization.

    Args:
        obj: The Python object to serialize.  May be a dict, list, int, float,
            bool, str, or ``None``.  Nested structures are handled recursively.
        float_precision_decimals: Number of decimal places to round floats to.
            Defaults to ``FLOAT_PRECISION`` (6) as mandated by the lock file.

    Returns:
        Compact canonical JSON string (no extra whitespace, keys sorted).

    Raises:
        ValueError: If any float value is NaN or Infinity, which are forbidden
            by the ``allow_nan=false`` constraint in the lock file.
    """

    def _normalize(x: Any) -> Any:
        """Recursively normalize a value before JSON serialization.

        Floats are rounded and validated; collections are traversed depth-first.
        bool must be checked before int because bool is a subclass of int in
        Python — json.dumps already serialises booleans correctly, so they
        pass through unchanged.
        """
        if isinstance(x, float):
            # NaN/Infinity cannot be represented in strict JSON (RFC 8259).
            if not math.isfinite(x):
                raise ValueError(
                    f"NaN/Infinity not allowed in canonical_json; got {x!r}"
                )
            # Round to the canonical precision so two floats that differ only
            # past the 6th decimal place produce identical JSON strings.
            return round(x, float_precision_decimals)
        if isinstance(x, bool):
            # bool is a subclass of int; preserve as-is so json.dumps emits
            # true/false rather than 1/0.
            return x
        if isinstance(x, int):
            # Integers need no rounding — pass through unchanged.
            return x
        if isinstance(x, list):
            return [_normalize(item) for item in x]
        if isinstance(x, dict):
            return {k: _normalize(v) for k, v in x.items()}
        # str, None, and other JSON-serializable scalars pass through as-is.
        return x

    normalized = _normalize(obj)
    return json.dumps(
        normalized,
        sort_keys=True,       # deterministic key order regardless of insertion order
        separators=(",", ":"),  # compact: no spaces after , or :
        ensure_ascii=False,   # preserve non-ASCII characters verbatim
        allow_nan=False,      # raise on NaN/Inf that slipped past _normalize
    )


def sha256_hex(s: str) -> str:
    """Return the lowercase SHA-256 hex digest of a UTF-8 encoded string.

    Used to produce a stable fingerprint of the canonical JSON output so that
    determinism can be verified by comparing digests across independent runs.

    Args:
        s: The string to hash.  Must be valid UTF-8 (all Python ``str`` are).

    Returns:
        64-character lowercase hexadecimal SHA-256 digest string.
    """
    return hashlib.sha256(s.encode("utf-8")).hexdigest()
