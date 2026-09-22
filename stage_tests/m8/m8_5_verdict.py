# File: m8/m8_5_verdict.py
"""M8-5 Final Verdict Clamp (M8_v2).

M8-5 is the final clamp that prevents false PASS. It computes PASS/FAIL from
upstream module state using a strict, deterministic priority order.

Locked behavior (do not change):
- Fixed failure priority selection ("first failure wins").
- PASS only if determinism_key matches: sha256:<64 hex>.
- No free-text reasons (allow-listed reason codes only).
- Output always includes determinism_key (may be None).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Final, Mapping, Optional, Sequence


@dataclass(frozen=True)
class FailureReason:
    """Structured failure reason (no free-text).

    Attributes:
        category: Short category label used by authority layer.
        code: Allow-listed reason code (must exist in REASON_CODES_M8.yaml).
    """

    category: str
    code: str

    def as_dict(self) -> Dict[str, str]:
        """Convert to the locked dict representation.

        Returns:
            Dict with keys: category, code.
        """
        return {"category": self.category, "code": self.code}


# Allow-listed codes used by M8-5 (must match REASON_CODES_M8.yaml).
M8_SCHEMA_FAIL: Final[str] = "M8_SCHEMA_FAIL"
M8_GRAPH_INCOMPLETE: Final[str] = "M8_GRAPH_INCOMPLETE"
M8_ARTIFACT_REF_INVALID: Final[str] = "M8_ARTIFACT_REF_INVALID"
M8_DETERMINISM_KEY_MISSING: Final[str] = "M8_DETERMINISM_KEY_MISSING"
M8_INVARIANT_FAIL: Final[str] = "M8_INVARIANT_FAIL"
M8_REPLAY_FAIL: Final[str] = "M8_REPLAY_FAIL"

_SHA256_PREFIX: Final[str] = "sha256:"
_SHA256_HEX_LEN: Final[int] = 64
_HEX_CHARS: Final[frozenset[str]] = frozenset("0123456789abcdefABCDEF")


def _build_output(
    *,
    state: Mapping[str, Any],
    status: str,
    failure_reason: Optional[FailureReason],
) -> Dict[str, Any]:
    """Build the output dict while preserving the locked I/O contract.

    Args:
        state: Input state from upstream modules.
        status: "PASS" or "FAIL".
        failure_reason: Optional structured reason (no free-text).

    Returns:
        Output payload dict with locked keys and passthrough summaries.
    """
    out: Dict[str, Any] = {
        "m8_version": "2.0",
        "status": status,
        "failure_reason": None if failure_reason is None else failure_reason.as_dict(),
        # Always include determinism_key (even if missing from input).
        "determinism_key": state.get("determinism_key"),
    }

    # Passthrough summaries only (no derived logic here).
    for key in ("invariants_checked", "invariants_passed", "failed_invariants"):
        if key in state:
            out[key] = state.get(key)

    return out


@lru_cache(maxsize=4096)
def _is_sha256_ref_str(value: str) -> bool:
    """Validate determinism_key in string form (cached).

    Args:
        value: Candidate determinism key.

    Returns:
        True iff value matches "sha256:<64 hex>".
    """
    if not value.startswith(_SHA256_PREFIX):
        return False

    hexdigest = value[len(_SHA256_PREFIX) :]
    if len(hexdigest) != _SHA256_HEX_LEN:
        return False

    # Fast membership check avoids regex overhead.
    for ch in hexdigest:
        if ch not in _HEX_CHARS:
            return False
    return True


def _is_sha256_ref(value: Any) -> bool:
    """Return True if value looks like a sha256 content-addressed ref.

    Args:
        value: Any candidate object (expected to be str).

    Returns:
        True iff value is a valid sha256 ref string.
    """
    if not isinstance(value, str):
        return False
    return _is_sha256_ref_str(value)


def _has_failed_invariants(value: Any) -> bool:
    """Return True if failed_invariants indicates at least one failure.

    Args:
        value: Candidate failed_invariants value from state.

    Returns:
        True if value is a non-empty sequence (excluding strings/bytes).
    """
    if value is None:
        return False
    if isinstance(value, (str, bytes, bytearray)):
        return False
    if isinstance(value, Sequence):
        return len(value) > 0
    return False


def _first_failure_reason(state: Mapping[str, Any]) -> Optional[FailureReason]:
    """Select the first failure reason using strict priority ordering.

    Args:
        state: Mapping containing upstream results.

    Returns:
        First matching FailureReason by priority, or None.

    Priority:
        1) hard_fail
        2) graph_complete is False
        3) artifacts_refs_ok is False
        4) determinism_key explicitly present but None
        5) failed_invariants non-empty
        6) replay_verified is False
    """
    if bool(state.get("hard_fail")):
        return FailureReason(category="SYSTEM_FAIL", code=M8_SCHEMA_FAIL)

    if state.get("graph_complete") is False:
        return FailureReason(category="SCHEMA_FAIL", code=M8_GRAPH_INCOMPLETE)

    if state.get("artifacts_refs_ok") is False:
        return FailureReason(category="SCHEMA_FAIL", code=M8_ARTIFACT_REF_INVALID)

    if "determinism_key" in state and state.get("determinism_key") is None:
        return FailureReason(category="SCHEMA_FAIL", code=M8_DETERMINISM_KEY_MISSING)

    if _has_failed_invariants(state.get("failed_invariants")):
        return FailureReason(category="INVARIANT_FAIL", code=M8_INVARIANT_FAIL)

    if state.get("replay_verified") is False:
        return FailureReason(category="REPLAY_FAIL", code=M8_REPLAY_FAIL)

    return None


def m8_5_final_verdict(state: Mapping[str, Any]) -> Dict[str, Any]:
    """Compute the final M8 verdict from upstream module state.

    Args:
        state: Mapping-like upstream state. Expected keys (all optional):
            - hard_fail: bool
            - graph_complete: bool
            - artifacts_refs_ok: bool
            - determinism_key: "sha256:<64 hex>"
            - failed_invariants: sequence (non-empty means failure)
            - replay_verified: bool
            - invariants_checked / invariants_passed: passthrough summaries

    Returns:
        Verdict payload dict (locked schema):
            - m8_version: str
            - status: "PASS" or "FAIL"
            - failure_reason: None or {"category": str, "code": str}
            - determinism_key: always present (may be None)
            - optional passthrough: invariants_checked, invariants_passed,
              failed_invariants

    Notes:
        - Do not change signature or I/O contract.
        - If state is None or not mapping-like, treat as empty (cannot PASS).
    """
    # Defensive input handling (does not loosen PASS criteria).
    if state is None or not hasattr(state, "get"):
        state = {}

    reason = _first_failure_reason(state)

    if reason is not None:
        status = "FAIL"
    else:
        dk = state.get("determinism_key")
        if dk is None or not _is_sha256_ref(dk):
            status = "FAIL"
            reason = FailureReason(category="SCHEMA_FAIL", code=M8_DETERMINISM_KEY_MISSING)
        else:
            status = "PASS"

    return _build_output(state=state, status=status, failure_reason=reason)
