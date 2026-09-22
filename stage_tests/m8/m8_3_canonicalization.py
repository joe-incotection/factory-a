"""M8-3: Canonicalization & Determinism (M8_v2).

This module provides a *byte-stable* canonical JSON serializer and a deterministic
hash key derived from that canonical form.

Lock rules (as required by M8-3 golden tests):
- Dict keys are serialized in ascending order.
- No extra whitespace (compact separators): ',' and ':'.
- Float/Decimal numbers are rounded to 6 decimal places using ROUND_HALF_UP.
- NaN / Inf are forbidden (ValueError).
- Negative zero (-0.0) is normalized to "0".

Notes:
- We intentionally implement a custom serializer rather than relying on
  `json.dumps(...)` to guarantee stable numeric formatting and strict constraints.
"""

from __future__ import annotations

import hashlib
import math
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from json.encoder import encode_basestring
from typing import Any

_JSON_TRUE = "true"
_JSON_FALSE = "false"
_JSON_NULL = "null"

# Quantization target for numeric canonicalization (fixed precision, deterministic).
_QUANT_6DP = Decimal("0.000001")


@lru_cache(maxsize=4096)
def _escape_str(value: str) -> str:
    """Return JSON-escaped string including surrounding quotes (cached).

    Args:
        value: Input string.

    Returns:
        A JSON string literal with proper escaping and quotes, e.g. `"hello\n"`.

    Why cached:
        Canonical payloads often reuse the same keys/labels (e.g., "type", "id").
        Caching reduces repeated work on hot paths without changing semantics.
    """
    return encode_basestring(value)


def _format_decimal_6dp(value: Decimal) -> str:
    """Format a Decimal into canonical numeric JSON (6dp, HALF_UP, compact).

    Args:
        value: Decimal value to format.

    Returns:
        Canonical numeric string:
          - Rounded to 6 decimal places with ROUND_HALF_UP
          - No scientific notation
          - Trailing zeros and trailing '.' removed
          - Zero normalized to "0"
    """
    quantized = value.quantize(_QUANT_6DP, rounding=ROUND_HALF_UP)
    if quantized == 0:
        return "0"

    s = format(quantized, "f")  # force non-scientific notation
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def _format_float_6dp(value: float) -> str:
    """Format a float into canonical numeric JSON (6dp, HALF_UP, strict).

    Args:
        value: Float value to format.

    Returns:
        Canonical numeric string following the same rules as Decimal formatting.

    Raises:
        ValueError: If the float is NaN or Infinity (forbidden by lock rules).

    Details:
        - Reject NaN/Inf to avoid non-JSON and non-deterministic representations.
        - Normalize negative zero (-0.0) to "0" for deterministic equality.
        - Convert using Decimal(repr(value)) to avoid binary float artifacts
          affecting rounding deterministically.
    """
    if math.isnan(value):
        raise ValueError("NaN is forbidden in canonical JSON")
    if math.isinf(value):
        raise ValueError("Inf is forbidden in canonical JSON")

    # Normalize negative zero reliably (copysign distinguishes -0.0 vs +0.0).
    if value == 0.0 and math.copysign(1.0, value) < 0.0:
        return "0"

    # Use Decimal(repr(x)) for stable decimal rounding behavior.
    return _format_decimal_6dp(Decimal(repr(value)))


def _serialize(obj: Any) -> str:
    """Serialize an object into canonical JSON (recursive, deterministic).

    Args:
        obj: A JSON-compatible value:
          - dict (with string keys)
          - list/tuple
          - str, int, float, Decimal, bool, None

    Returns:
        Canonical JSON string fragment representing `obj`.

    Raises:
        ValueError: If:
          - dict contains non-string keys
          - float is NaN/Inf
          - obj is an unsupported type

    Implementation notes:
        - `bool` is a subclass of `int` in Python; boolean checks must come first.
        - Dict keys are sorted to guarantee deterministic ordering.
        - We build strings manually to enforce no-whitespace separators.
    """
    # Order matters: bool is a subclass of int.
    if obj is None:
        return _JSON_NULL
    if obj is True:
        return _JSON_TRUE
    if obj is False:
        return _JSON_FALSE

    if isinstance(obj, int) and not isinstance(obj, bool):
        return str(obj)

    if isinstance(obj, float):
        return _format_float_6dp(obj)

    if isinstance(obj, Decimal):
        return _format_decimal_6dp(obj)

    if isinstance(obj, str):
        # Cached escaping improves throughput on repeated keys/strings.
        return _escape_str(obj)

    if isinstance(obj, (list, tuple)):
        # List comprehension tends to be faster for join in CPython.
        return "[" + ",".join([_serialize(v) for v in obj]) + "]"

    if isinstance(obj, dict):
        # JSON object keys must be strings for this canonical serializer.
        # We sort keys to enforce deterministic ordering.
        items: list[str] = []
        for key in sorted(obj):
            if not isinstance(key, str):
                raise ValueError("Non-string dict key is forbidden in canonical JSON")
            items.append(_escape_str(key) + ":" + _serialize(obj[key]))
        return "{" + ",".join(items) + "}"

    raise ValueError(f"Unsupported type for canonical JSON: {type(obj).__name__}")


def canonical_json(payload: object) -> str:
    """Return canonical JSON string for the given payload.

    Args:
        payload: Any JSON-compatible structure (dict/list/str/int/float/bool/None).
            - dict keys MUST be strings
            - floats MUST NOT be NaN/Inf

    Returns:
        Canonical JSON string:
          - deterministic key ordering for objects
          - compact separators (no whitespace)
          - numeric rounding to 6dp (ROUND_HALF_UP)
          - -0.0 normalized to 0

    Raises:
        ValueError: If canonicalization fails due to forbidden/unsupported values.
    """
    return _serialize(payload)


def compute_determinism_key(canonical_payload: object) -> str:
    """Compute determinism key from a canonicalizable payload.

    The determinism key is defined as:
        "sha256:" + sha256_hex(canonical_json(payload))

    Args:
        canonical_payload: Payload to canonicalize then hash.

    Returns:
        Determinism key formatted as ``sha256:<hex>``.

    Raises:
        ValueError: If canonicalization fails due to forbidden/unsupported values.
    """
    canonical = canonical_json(canonical_payload)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
