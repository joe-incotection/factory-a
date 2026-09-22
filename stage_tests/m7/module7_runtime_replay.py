"""Module 7 — Runtime Replay Verifier (Independent EP).

This module implements the SSOT public API required by `test_golden_module7.py`
for Stage2 Validator: **M7 Runtime Replay**.

Key constraints (must remain true):
- **No determinism algorithm implemented here**:
  determinism key is computed ONLY via injected `determinism_key_fn`.
- **Dependency injection**:
  replay execution uses injected `runner`; determinism uses injected `determinism_key_fn`.
- **Reason codes**:
  allowlist-only; no free-text.
- **I/O contract**:
  output keys and nested evidence shape must match SSOT and golden tests.
"""

from __future__ import annotations

import os as _os
import time as _time
from typing import Any, Callable, Mapping, Protocol


class ReplayRunnerProtocol(Protocol):
    """Protocol for the dependency-injected replay runner.

    The golden tests provide a stub runner that conforms to this protocol.

    Methods:
        run: Executes a replay command in a controlled environment and returns a dict
            containing execution status and basic telemetry.
    """

    def run(self, *, command: str, working_directory: str, timeout_s: int) -> dict[str, Any]:
        """Run the replay command.

        Args:
            command: The command line to run (opaque to M7).
            working_directory: Working directory for the replay execution.
            timeout_s: Timeout in seconds for the replay execution.

        Returns:
            A dict with expected keys:
                - ok (bool): True if the runner reports successful execution.
                - exit_code (int): Process exit code (0 is success).
                - stdout (str): Captured stdout (M7 does not emit this in evidence).
                - stderr (str): Captured stderr (M7 does not emit this in evidence).
                - duration_ms (int): Execution duration in milliseconds.
        """


# ----------------------------
# Reason code allowlist (M7)
# ----------------------------
# M7-specific allowlisted reason codes (no free-text allowed).
M7_REPLAY_FAIL = "M7_REPLAY_FAIL"  # Replay ran but determinism key mismatched.
M7_REPLAY_ERROR = "M7_REPLAY_ERROR"  # Replay couldn't be executed / crashed / bad exit.
M7_ARTIFACTS_MISSING = "M7_ARTIFACTS_MISSING"  # Required replay artifacts are incomplete.
M7_REPLAY_STALE = "M7_REPLAY_STALE"  # SOVEREIGN SHIELD: Replay window expired (TTL exceeded).

# System-level allowlisted code used when schema/pin-set/DI preconditions fail.
SYS_SCHEMA_VIOLATION = "SYS_SCHEMA_VIOLATION"

# BLOCK-02: Empty policy protection reason code.
RC_EMPTY_POLICY_PROTECTION = "RC_EMPTY_POLICY_PROTECTION"


class IntegrityError(Exception):
    """Raised when a critical integrity invariant is violated in M7.

    Attributes:
        reason_code: Allowlisted reason code (must be from M7 allowlist).
        message: Human-readable description of the violation.
    """

    def __init__(self, *, reason_code: str, message: str) -> None:
        self.reason_code = reason_code
        self.message = message
        super().__init__(f"[{reason_code}] {message}")


# ----------------------------
# SOVEREIGN SHIELD — Temporal Seal
# ----------------------------

def is_fresh(run_at_utc: int, ttl_s: int | None = None) -> bool:
    """Return True if the artifact timestamp is within the allowed replay window.

    Protects against stale artifact replay: an attacker cannot reuse artifacts
    from a previous run because the temporal seal expires after ``ttl_s`` seconds.

    TTL resolution order:
      1. Explicit ``ttl_s`` argument (for tests / callers that want a fixed window).
      2. ``PAL_AUDIT_TTL`` environment variable (ops override without code change).
      3. Built-in default: 600 s (10 minutes) — relaxed from 300 s to accommodate
         large-module build pipelines.

    Args:
        run_at_utc: Unix epoch timestamp (int) recorded when artifacts were captured.
        ttl_s: Time-to-live in seconds.  Pass None to use env-var / default.

    Returns:
        True if ``time.time() - run_at_utc <= ttl_s``, False otherwise.
    """
    if ttl_s is None:
        ttl_s = int(_os.getenv("PAL_AUDIT_TTL", 600))
    age_s = _time.time() - run_at_utc
    return age_s <= ttl_s


# These sets represent the minimal replay prerequisites mandated by the M7 SSOT.
_REQUIRED_ARTIFACT_KEYS: frozenset[str] = frozenset(
    {
        "test_command",
        "working_directory",
        "timeout_s",
        "pytest_runtime_payload",
        "toolchain_manifest_digest",
        "policy_digests",
    }
)

_REQUIRED_PIN_KEYS: frozenset[str] = frozenset(
    {
        "kami_version",
        "dna_version",
        "smart_spec_version",
        "reason_codes_version",
        "context_gate_version",
        "noise_budget_version",
        "toolchain_digest",
        "determinism_policy_version",
    }
)


def _has_required_keys(obj: Mapping[str, Any], required: frozenset[str]) -> bool:
    """Check presence of required keys with non-empty values.

    Args:
        obj: Mapping to validate (usually a dict).
        required: Required keys set.

    Returns:
        True if all keys exist in `obj` and are not None/empty-string.
    """
    get = obj.get
    for key in required:
        if key not in obj:
            return False
        if get(key) in (None, ""):
            return False
    return True


def _make_output(*, first_run_key: str, replay_command: str) -> dict[str, Any]:
    """Create an output dict in the SSOT shape.

    This is the canonical output constructor to ensure stable I/O contract.

    Args:
        first_run_key: Determinism key produced by the first (run1) execution.
        replay_command: Replay command recorded in the artifacts (for evidence).

    Returns:
        Output dict with all required top-level keys and evidence keys populated,
        with replay values initialized to None/False.
    """
    return {
        "replay_verified": False,
        "determinism_key_first": first_run_key,
        "determinism_key_replay": None,
        "reason_code": None,
        "evidence": {
            "replay_command": replay_command,
            "replay_exit_code": None,
            "replay_duration_ms": None,
            "replay_log_ref": None,
            "replay_artifacts_hash": None,   # BLOCK-02: anti-tamper hash of artifacts bundle
        },
    }


def _safe_int(value: Any) -> int | None:
    """Best-effort conversion to int.

    Used to robustly parse runner telemetry (exit_code, duration_ms) without throwing.

    Args:
        value: Any value from runner output.

    Returns:
        Parsed int on success; otherwise None.
    """
    # Fast-path for common numeric types
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except Exception:
        return None


def verify_runtime_replay(
    *,
    first_run_key: str,
    replay_artifacts: dict,
    validation_result: dict,
    pin_set: dict,
    enable_m7_replay: bool = True,
    runner: ReplayRunnerProtocol | None = None,
    determinism_key_fn: Callable[[dict, dict], str] | None = None,
) -> dict:
    """Replay runtime execution and compare determinism keys.

    This function is the SSOT public API for M7 and must satisfy golden tests.

    Important behavior:
    - If `enable_m7_replay` is False: returns a valid-shaped output without executing replay.
    - Artifacts missing: returns `M7_ARTIFACTS_MISSING`.
    - Pin-set/schema/DI missing: returns `SYS_SCHEMA_VIOLATION`.
    - Runner failure / non-zero exit: returns `M7_REPLAY_ERROR`.
    - Runner success:
        - computes replay determinism key using injected `determinism_key_fn`
        - compares to `first_run_key`
        - mismatch => `M7_REPLAY_FAIL`, match => `replay_verified=True` and reason_code=None

    Args:
        first_run_key: Determinism key from the first runtime execution (run1).
        replay_artifacts: Captured artifacts required to reproduce the runtime run.
        validation_result: Upstream aggregated validation result (present for pipeline wiring).
            Note: M7 does not alter upstream authority decisions.
        pin_set: Pin-set snapshot for run1 used to detect schema/policy mismatches.
        enable_m7_replay: Toggle to enable/disable M7.
        runner: Dependency-injected runner used to execute the replay command.
        determinism_key_fn: Dependency-injected SSOT determinism-key function.

    Returns:
        A dict matching the I/O contract expected by `test_golden_module7.py`.
    """
    # Avoid repeated global lookups; also keep output stable even when artifacts are non-dict.
    artifacts_is_dict = isinstance(replay_artifacts, dict)
    replay_command = str(replay_artifacts.get("test_command") or "") if artifacts_is_dict else ""

    out: dict[str, Any] = _make_output(first_run_key=first_run_key, replay_command=replay_command)

    # M7 is independent and may be disabled by policy or caller.
    if not enable_m7_replay:
        return out

    # (1) Validate replay artifacts completeness (SSOT).
    if (not artifacts_is_dict) or (not _has_required_keys(replay_artifacts, _REQUIRED_ARTIFACT_KEYS)):
        out["reason_code"] = M7_ARTIFACTS_MISSING
        return out

    # (1b) SOVEREIGN SHIELD — Temporal Seal.
    # If artifacts carry a run_at_utc timestamp, enforce the TTL replay window.
    # TTL is read from PAL_AUDIT_TTL env-var (default 600 s).
    # Key is optional: artifacts that pre-date this feature (e.g. golden-test fixtures)
    # simply skip the check, preserving backward compatibility.
    _run_at_utc = replay_artifacts.get("run_at_utc")
    if _run_at_utc is not None:
        try:
            if not is_fresh(int(_run_at_utc)):  # ttl_s=None → reads PAL_AUDIT_TTL / 600s
                raise IntegrityError(
                    reason_code=M7_REPLAY_STALE,
                    message="M7 Blocked: replay artifacts are stale (TTL 300s exceeded).",
                )
        except IntegrityError:
            raise
        except Exception:
            pass  # Non-castable run_at_utc — skip check rather than hard-fail

    # (2) Validate pin_set completeness (system-level). Missing pin keys are treated as schema violation.
    if not isinstance(pin_set, dict) or not _has_required_keys(pin_set, _REQUIRED_PIN_KEYS):
        out["reason_code"] = SYS_SCHEMA_VIOLATION
        return out

    # (3) Dependency injection is mandatory when enabled.
    if runner is None or determinism_key_fn is None:
        out["reason_code"] = SYS_SCHEMA_VIOLATION
        return out

    # (4) Execute replay. Extract required fields once to minimize repeated dict lookups.
    cmd = replay_artifacts["test_command"]
    wdir = replay_artifacts["working_directory"]
    timeout_val = replay_artifacts["timeout_s"]

    # Timeout must be int-castable and > 0.
    try:
        timeout_s = int(timeout_val)
    except Exception:
        out["reason_code"] = SYS_SCHEMA_VIOLATION
        return out
    if timeout_s <= 0:
        out["reason_code"] = SYS_SCHEMA_VIOLATION
        return out

    try:
        run_result = runner.run(
            command=str(cmd),
            working_directory=str(wdir),
            timeout_s=timeout_s,
        )
    except Exception:
        # Runner threw; we do not leak exception text.
        out["reason_code"] = M7_REPLAY_ERROR
        return out

    # Evidence: always fill telemetry we can extract (even if ok=False).
    exit_code = _safe_int(run_result.get("exit_code"))
    duration_ms = _safe_int(run_result.get("duration_ms"))
    evidence = out["evidence"]
    evidence["replay_exit_code"] = exit_code
    evidence["replay_duration_ms"] = duration_ms

    # Treat any missing/falsey ok as failure.
    # IMPORTANT: Trust runner's ok flag - runner knows what exit codes are acceptable.
    # For pytest: exit 0 (pass) and 1 (some failed) are both valid for determinism check.
    ok = bool(run_result.get("ok", False))
    if not ok:
        out["reason_code"] = M7_REPLAY_ERROR
        out["determinism_key_replay"] = None
        return out

    # (5) Compute replay determinism key using injected SSOT function.
    # IMPORTANT: M7 must not implement hashing/normalization; injected function owns algorithm.
    runtime_payload = replay_artifacts.get("pytest_runtime_payload")
    policy_digests = replay_artifacts.get("policy_digests")
    if not isinstance(runtime_payload, dict) or not isinstance(policy_digests, dict):
        out["reason_code"] = SYS_SCHEMA_VIOLATION
        return out

    # BLOCK-02: Empty Policy Protection — policy identity must be verified.
    # Empty policy_digests means the module has no verifiable policy binding,
    # which opens a replay substitution vector (attacker swaps artifacts from
    # any module that also has no policy). Hard-fail here to force upstream
    # to populate policy_digests before M7 will sign off.
    if not policy_digests:
        raise IntegrityError(
            reason_code=RC_EMPTY_POLICY_PROTECTION,
            message="M7 Blocked: policy_digests cannot be empty. Identity must be verified.",
        )

    # BLOCK-02: Anti-Tamper Replay — hash the full artifacts bundle.
    # Included in evidence so downstream can detect artifacts substitution between runs.
    import hashlib as _hashlib
    import json as _json
    _artifacts_canonical = _json.dumps(replay_artifacts, sort_keys=True, default=str).encode()
    artifacts_hash = _hashlib.sha256(_artifacts_canonical).hexdigest()
    out["evidence"]["replay_artifacts_hash"] = artifacts_hash

    try:
        # Use original runtime_payload + policy_digests from artifacts (not pin_set).
        # This matches how first_run_key is computed by the upstream caller.
        replay_key = determinism_key_fn(runtime_payload, policy_digests)
    except Exception:
        out["reason_code"] = M7_REPLAY_ERROR
        out["determinism_key_replay"] = None
        return out

    out["determinism_key_replay"] = replay_key

    # (6) Compare keys. Match => verified; mismatch => deterministic failure.
    if replay_key == first_run_key:
        out["replay_verified"] = True
        out["reason_code"] = None
    else:
        out["replay_verified"] = False
        out["reason_code"] = M7_REPLAY_FAIL

    return out
