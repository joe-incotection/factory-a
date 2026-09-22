"""
M8 Core Utilities and Replay Verifier (AIEL-3 Polished).

This module provides the implementation for M8-4: Replay Verifier, ensuring 
that all module outputs and artifacts can be re-run and verified with 
100% bit-exact determinism.
"""

import hashlib
import json
from typing import Any, Dict, Optional, Final
from decimal import Decimal, ROUND_HALF_UP

# Constants - DNA System Locks
ENCODING: Final[str] = "utf-8"
HASH_ALGO: Final[str] = "sha256"
# DNA Lock: float precision = 6 (ROUND_HALF_UP_6DP)
FLOAT_PRECISION_STR: Final[str] = "1.000000"

def compute_determinism_key(payload: Dict[str, Any]) -> Optional[str]:
    """Computes a deterministic SHA-256 hash using an optimized canonicalization flow.

    Args:
        payload (Dict[str, Any]): The data to be hashed.

    Returns:
        Optional[str]: A string prefixed with 'sha256:' or None if hashing fails.

    Raises:
        ValueError: If illegal values like NaN or Inf are encountered.
    """
    if not payload:
        return None

    def _optimized_handler(obj: Any) -> Any:
        """Handles type-specific canonicalization rules for JSON serialization."""
        if isinstance(obj, float):
            # DNA Lock: forbid NaN/Inf to ensure mathematical stability
            if obj != obj or obj in (float('inf'), float('-inf')):
                raise ValueError("M8_CANONICAL_FAIL: NaN/Inf forbidden")
            
            # DNA Lock: normalize negative zero (-0.0 -> 0.0)
            if obj == 0.0:
                return 0.0
            
            # DNA Lock: ROUND_HALF_UP_6DP using Decimal for bit-exact precision
            return float(Decimal(str(obj)).quantize(
                Decimal(FLOAT_PRECISION_STR), 
                rounding=ROUND_HALF_UP
            ))
        return obj

    try:
        # Canonicalization process:
        # 1. sort_keys=True: Ensures key order stability.
        # 2. separators=(",", ":"): Removes non-essential whitespace.
        # 3. ensure_ascii=True: Ensures consistent byte representation.
        canonical_json = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=_optimized_handler,
            ensure_ascii=True
        )
        
        digest = hashlib.sha256(canonical_json.encode(ENCODING)).hexdigest()
        return f"{HASH_ALGO}:{digest}"
    except (TypeError, ValueError, OverflowError):
        # M8 Rule: Any error in canonicalization leads to a HARD_FAIL
        return None

def m8_4_replay_verify(
    payload: Dict[str, Any],
    expected_key: Optional[str] = None,
    runtime_evidence_key: Optional[str] = None,
    replay_evidence_key: Optional[str] = None,
) -> Dict[str, Any]:
    """M8-4: Replay Verifier.

    Performs a bit-exact replay check by re-calculating the determinism key.
    Additionally (optional), if runtime evidence keys are provided by the runner,
    verifies that the evidence is stable across the replay.

    Args:
        payload: The canonical payload to verify.
        expected_key: (Optional) The expected determinism key for `payload`.
            If provided and does not match, replay fails.
        runtime_evidence_key: (Optional) A Stage2-produced runtime evidence key
            from the *first* execution.
        replay_evidence_key: (Optional) A Stage2-produced runtime evidence key
            from the *replay* execution.

    Returns:
        Dict[str, Any]: Minimal contract containing:
            - replay_verified (bool): Status of the bit-exact match.
            - determinism_key (str): The calculated SHA-256 key.
            - rehash_matches (bool): Verification of consistency.
    """
    # 1) Structural determinism: canonical payload -> determinism key
    current_key: Optional[str] = compute_determinism_key(payload)
    if current_key is None:
        return {
            "replay_verified": False,
            "determinism_key": None,
            "rehash_matches": False,
            "reason": "M8_CANONICAL_FAIL",
        }

    if expected_key is not None and current_key != expected_key:
        return {
            "replay_verified": False,
            "determinism_key": current_key,
            "rehash_matches": False,
            "reason": "M8_REPLAY_FAIL",
            "mismatch": "expected_key",
        }

    # 2) Runtime determinism (optional): Stage2 evidence must match across runs
    if runtime_evidence_key is not None and replay_evidence_key is not None:
        if runtime_evidence_key != replay_evidence_key:
            return {
                "replay_verified": False,
                "determinism_key": current_key,
                "rehash_matches": True,
                "reason": "M8_REPLAY_FAIL",
                "mismatch": "runtime_evidence_key",
                "runtime_first": runtime_evidence_key,
                "runtime_replay": replay_evidence_key,
            }

    return {
        "replay_verified": True,
        "determinism_key": current_key,
        "rehash_matches": True,
    }