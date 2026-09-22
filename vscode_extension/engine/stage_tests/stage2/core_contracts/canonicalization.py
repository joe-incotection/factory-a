"""Canonical JSON serialization for determinism.

This module provides deterministic JSON serialization that guarantees the same
Python object always produces the same JSON bytes, regardless of platform,
Python version, or runtime state.

Key features:
    - Sorted keys (alphabetical order)
    - Stable float formatting (6 decimal places)
    - No NaN/Inf (rejected with error)
    - -0.0 normalized to 0.0
    - Minimal whitespace (compact)

AIEL-2 Optimizations:
- Combined NaN/Inf check (single isfinite() call)
- Better error messages (separate NaN and Inf)
- Added allow_nan=False in json.dumps (extra safety)

AIEL-3 Enhancements:
- Comprehensive docstrings with usage examples
- Inline comments explaining float handling
- Performance characteristics documented
"""

import json
import math
from typing import Any, Dict, List, Tuple, Union


def canonical_json(obj: Any) -> bytes:
    """Convert object to canonical JSON bytes.
    
    This function provides deterministic JSON serialization. The same object
    always produces the same bytes, which is critical for:
        - Hashing (same data → same hash)
        - Comparison (byte-level equality)
        - Storage (deduplicate identical objects)
        - Testing (predictable output)
    
    Determinism requirements:
        - Sorted keys (alphabetical order, case-sensitive)
        - Stable float formatting (6 decimal places, rounded)
        - No NaN/Inf (forbidden - raises ValueError)
        - -0.0 normalized to 0.0 (avoids sign ambiguity)
        - Minimal whitespace (no pretty-printing)
        - UTF-8 encoding (consistent across platforms)
    
    Args:
        obj: Python object to serialize. Supported types:
            - dict, list, tuple (nested structures OK)
            - str, int, float, bool, None (primitives)
            - Must be JSON-serializable
            - Must NOT contain NaN or Inf
        
    Returns:
        UTF-8 encoded JSON bytes. Deterministic output means:
            canonical_json(obj) == canonical_json(obj) always
        
    Raises:
        ValueError: If object contains NaN or Inf, or if canonicalization fails.
            NaN and Inf are forbidden because they don't have a standard JSON
            representation and would break determinism.
        TypeError: If object is not JSON-serializable.
    
    Examples:
        Sorted keys:
            >>> canonical_json({"b": 1, "a": 2})
            b'{"a":2,"b":1}'
        
        Float rounding:
            >>> canonical_json({"x": 1.23456789})
            b'{"x":1.234568}'
        
        No NaN/Inf:
            >>> canonical_json({"x": float('nan')})
            ValueError: NaN not allowed in canonical JSON
    
    Performance:
        - O(n) where n = total elements in nested structure
        - Single-pass sanitization
        - Optimized type checking with isinstance
    """
    # Sanitize floats in single pass (converts NaN/Inf → error, rounds floats)
    sanitized = _sanitize_floats(obj)
    
    # Serialize with sorted keys and compact format
    try:
        json_str = json.dumps(
            sanitized,
            ensure_ascii=True,      # ASCII-only (portable)
            sort_keys=True,         # Alphabetical key order
            separators=(',', ':'),  # Minimal whitespace
            allow_nan=False         # Extra safety: reject NaN/Inf
        )
    except (TypeError, ValueError) as e:
        # Serialization error: Object not JSON-serializable or other issue
        raise ValueError(f"Failed to serialize to canonical JSON: {e}")
    
    # Encode to UTF-8 bytes (deterministic encoding)
    return json_str.encode('utf-8')


def _sanitize_floats(obj: Any) -> Any:
    """Sanitize floats in object for canonical JSON (internal helper).
    
    This function recursively processes an object to ensure all floats are
    safe for canonical JSON serialization:
        - NaN and Inf are rejected (not allowed in canonical JSON)
        - -0.0 is converted to 0.0 (avoid sign ambiguity)
        - Floats are rounded to 6 decimal places (stable formatting)
    
    Rules:
        - Round to 6 decimal places (balance precision vs compactness)
        - Convert -0.0 to 0.0 (only one representation of zero)
        - Reject NaN and Inf (no standard JSON representation)
    
    Args:
        obj: Python object (may contain floats at any nesting level).
        
    Returns:
        Sanitized object with all floats processed.
        Primitive types (int, str, bool, None) pass through unchanged.
        
    Raises:
        ValueError: If NaN or Inf detected anywhere in the object tree.
    """
    # Type-specific handling for better performance
    if isinstance(obj, float):
        # Fast NaN/Inf check using single isfinite() call
        # isfinite() returns False for both NaN and Inf
        if not math.isfinite(obj):
            # Determine which error (NaN or Inf) for better message
            if math.isnan(obj):
                raise ValueError("NaN not allowed in canonical JSON")
            else:
                # Inf or -Inf
                raise ValueError(f"Inf not allowed in canonical JSON: {obj}")
        
        # Convert -0.0 to 0.0 (avoid sign ambiguity)
        # In Python, -0.0 == 0.0 is True, but they're distinct objects
        if obj == 0.0:
            return 0.0
        
        # Round to 6 decimal places (stable formatting)
        # 6 decimals balances precision with compactness
        return round(obj, 6)
    
    elif isinstance(obj, dict):
        # Recursively sanitize dictionary values
        # Dictionary comprehension is efficient and pythonic
        return {k: _sanitize_floats(v) for k, v in obj.items()}
    
    elif isinstance(obj, (list, tuple)):
        # Handle both list and tuple with same logic
        result = [_sanitize_floats(item) for item in obj]
        # Preserve tuple type (return tuple if input was tuple)
        return tuple(result) if isinstance(obj, tuple) else result
    
    else:
        # Primitive types (int, str, bool, None) pass through unchanged
        # No sanitization needed for these types
        return obj
