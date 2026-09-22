"""
gate_c.py

Gate C — Decision Receipt Builder & Enforcer (v1.0)

AIEL-3 (Polish & Verification):
- Added Google-style docstrings (Args/Returns/Raises) everywhere.
- Added inline comments for complex invariants:
  - canonical_json determinism
  - timestamp_utc excluded from receipt_hash
  - allowlist-only reason codes
  - hash chain: parameters -> evidence -> receipt -> determinism_key

CONSTRAINTS:
- Do NOT change logic.
- Do NOT change function signatures.
- Do NOT change I/O contract.
- Do NOT change canonical_json behavior (must be bit-exact).
"""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, List, Optional, Set

from canonical_json import canonical_json


class GateCError(ValueError):
    """Hard-fail error used by Gate C with a locked reason_code.

    Attributes:
        reason_code: Machine-checkable reason code (must be allowlisted).
    """

    def __init__(self, message: str, reason_code: str) -> None:
        super().__init__(message)
        self.reason_code: str = reason_code


@lru_cache(maxsize=4096)
def sha256_hex(text: str) -> str:
    """Compute SHA-256 hex digest of a UTF-8 string.

    Args:
        text: Input text, typically canonical JSON.

    Returns:
        SHA-256 hex digest string.

    Raises:
        None.

    Notes:
        Cached for performance only; SHA-256 is pure/deterministic.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_receipt_hash(receipt: Dict[str, Any]) -> str:
    """Compute receipt_hash according to LOCK rules.

    LOCK rules:
        - receipt_hash excludes timestamp_utc
        - receipt_hash MUST NOT include itself (hashes.receipt_hash)

    Args:
        receipt: Receipt dictionary.

    Returns:
        SHA-256 hex digest of canonical JSON of receipt excluding timestamp_utc
        and excluding hashes.receipt_hash.

    Why exclude timestamp_utc:
        timestamp_utc changes per run. If included, identical decisions would hash
        differently across time, breaking replay comparability.

    Why exclude hashes.receipt_hash:
        receipt_hash is derived from the receipt content. If the field is included
        in the content being hashed, validation becomes self-referential:
        setting receipt_hash changes the hashed payload, producing a mismatch.
    """
    payload: Dict[str, Any] = {k: v for k, v in receipt.items() if k != "timestamp_utc"}

    # FIX: exclude the self-referential field to keep hashing stable across build/validate.
    hashes = payload.get("hashes")
    if isinstance(hashes, dict) and "receipt_hash" in hashes:
        payload["hashes"] = {k: v for k, v in hashes.items() if k != "receipt_hash"}

    return sha256_hex(canonical_json(payload))


def compute_determinism_key(config: Dict[str, Any], toolchain_manifest_digest: str, locks_digest: str) -> str:
    """Compute determinism_key according to LOCK rules.

    Args:
        config: Identity/config binding (project_id/module_id/language).
        toolchain_manifest_digest: Digest of toolchain/runtime manifest.
        locks_digest: Digest of lock version/schema.

    Returns:
        SHA-256 hex digest.

    Why:
        determinism_key binds the receipt to the (config + environment + lock version)
        so drift can be detected and replay is meaningful.
    """
    base: Dict[str, Any] = {
        "config": config,
        "toolchain_manifest_digest": toolchain_manifest_digest,
        "locks_digest": locks_digest,
    }
    return sha256_hex(canonical_json(base))


def _try_import_yaml() -> Any:
    """Try importing PyYAML (optional).

    Returns:
        yaml module if installed, else None.
    """
    try:
        import yaml  # type: ignore

        return yaml
    except Exception:
        return None


def _load_yaml(path: str) -> Dict[str, Any]:
    """Load YAML as a dict.

    Args:
        path: YAML file path.

    Returns:
        Parsed YAML dict. If PyYAML is unavailable, uses a minimal fallback
        that reads only top-level key:value pairs.

    Raises:
        OSError: If file cannot be read.
    """
    yaml_mod = _try_import_yaml()
    if yaml_mod is not None:
        with open(path, "r", encoding="utf-8") as f:
            loaded = yaml_mod.safe_load(f)
        return loaded or {}

    # Minimal fallback (top-level only)
    data: Dict[str, Any] = {}
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            if ":" in raw and not raw.startswith(" "):
                key, val = raw.split(":", 1)
                data[key.strip()] = val.strip().strip('"').strip("'")
    return data


def _extract_reason_codes(node: Any) -> Set[str]:
    """Recursively extract keys that look like 'RC_*' from YAML structure.

    Args:
        node: Parsed YAML node.

    Returns:
        Set of reason codes.
    """
    out: Set[str] = set()
    if isinstance(node, dict):
        for key, val in node.items():
            if isinstance(key, str) and key.startswith("RC_"):
                out.add(key)
            out |= _extract_reason_codes(val)
    elif isinstance(node, list):
        for item in node:
            out |= _extract_reason_codes(item)
    return out


def load_allowed_reason_codes(reasons_yaml_path: str) -> Set[str]:
    """Load allowlisted reason codes from REASON_CODES YAML (no hardcoding).

    Args:
        reasons_yaml_path: Path to REASON_CODES YAML.

    Returns:
        Set of allowlisted reason codes.

    Raises:
        GateCError: If allowlist cannot be loaded.
    """
    data = _load_yaml(reasons_yaml_path)
    codes = _extract_reason_codes(data)
    if not codes:
        raise GateCError("Failed to load reason codes allowlist", "RC_RECEIPT_REASON_CODE_UNKNOWN")
    return codes


def _ensure(condition: bool, message: str, reason_code: str) -> None:
    """Internal guard to raise GateCError when condition is False."""
    if not condition:
        raise GateCError(message, reason_code)


def _is_digestish(val: Any) -> bool:
    """Return True if value looks like a digest string (permissive)."""
    return isinstance(val, str) and len(val) >= 8


def validate_receipt_schema(receipt: Dict[str, Any]) -> None:
    """Validate receipt against minimal locked schema (stdlib-only).

    Args:
        receipt: Receipt dict.

    Raises:
        GateCError: If required fields/types/values are invalid.
    """
    required_top: List[str] = [
        "decision_id",
        "timestamp_utc",
        "project_id",
        "module_id",
        "language",
        "toolchain_manifest_digest",
        "context",
        "decision",
        "hashes",
        "evidence_refs",
        "reason_codes",
        "determinism_key",
    ]
    for key in required_top:
        _ensure(key in receipt, f"Missing required field: {key}", "RC_RECEIPT_SCHEMA_INVALID")

    context = receipt["context"]
    decision = receipt["decision"]
    hashes = receipt["hashes"]
    evidence_refs = receipt["evidence_refs"]
    reason_codes = receipt["reason_codes"]

    _ensure(isinstance(context, dict), "context must be object", "RC_RECEIPT_SCHEMA_INVALID")
    _ensure(isinstance(decision, dict), "decision must be object", "RC_RECEIPT_SCHEMA_INVALID")
    _ensure(isinstance(hashes, dict), "hashes must be object", "RC_RECEIPT_SCHEMA_INVALID")
    _ensure(isinstance(reason_codes, list), "reason_codes must be array", "RC_RECEIPT_SCHEMA_INVALID")
    _ensure(isinstance(evidence_refs, list) and len(evidence_refs) >= 1, "evidence_refs must be non-empty array", "RC_RECEIPT_SCHEMA_INVALID")

    allowed_levels = {"L0", "L1", "L2", "L3"}
    _ensure(context.get("context_level") in allowed_levels, "invalid context_level", "RC_RECEIPT_SCHEMA_INVALID")
    _ensure(_is_digestish(context.get("context_hash")), "invalid context_hash", "RC_RECEIPT_SCHEMA_INVALID")

    for key in ("router_decision", "guard_verdict", "risk_params"):
        _ensure(key in decision, f"Missing decision.{key}", "RC_RECEIPT_SCHEMA_INVALID")
    _ensure(decision.get("guard_verdict") in {"APPROVED", "REJECTED", "DEGRADED", "SAFE_MODE"}, "invalid guard_verdict", "RC_RECEIPT_SCHEMA_INVALID")
    _ensure(isinstance(decision.get("risk_params"), dict), "risk_params must be object", "RC_RECEIPT_SCHEMA_INVALID")

    if "hybrid" in decision:
        hybrid = decision["hybrid"]
        _ensure(isinstance(hybrid, dict), "decision.hybrid must be object", "RC_RECEIPT_SCHEMA_INVALID")
        if "falsifier_reason_codes" in hybrid:
            _ensure(isinstance(hybrid["falsifier_reason_codes"], list), "hybrid.falsifier_reason_codes must be array", "RC_RECEIPT_SCHEMA_INVALID")

    for key in ("parameters_hash", "evidence_set_hash", "receipt_hash"):
        _ensure(_is_digestish(hashes.get(key)), f"Missing/invalid hashes.{key}", "RC_RECEIPT_SCHEMA_INVALID")

    for item in evidence_refs:
        _ensure(isinstance(item, dict), "evidence_refs items must be objects", "RC_RECEIPT_SCHEMA_INVALID")
        for k in ("name", "ref_type", "ref_hash"):
            _ensure(k in item, f"evidence_refs item missing {k}", "RC_RECEIPT_SCHEMA_INVALID")
        _ensure(item.get("ref_type") in {"sha256", "path", "uri", "memory_ref"}, "invalid evidence_refs.ref_type", "RC_RECEIPT_SCHEMA_INVALID")
        _ensure(isinstance(item.get("name"), str) and len(item["name"]) >= 1, "invalid evidence_refs.name", "RC_RECEIPT_SCHEMA_INVALID")
        _ensure(isinstance(item.get("ref_hash"), str) and len(item["ref_hash"]) >= 1, "invalid evidence_refs.ref_hash", "RC_RECEIPT_SCHEMA_INVALID")

    _ensure(_is_digestish(receipt.get("toolchain_manifest_digest")), "invalid toolchain_manifest_digest", "RC_RECEIPT_SCHEMA_INVALID")
    _ensure(isinstance(receipt.get("determinism_key"), str) and len(receipt["determinism_key"]) >= 8, "invalid determinism_key", "RC_RECEIPT_SCHEMA_INVALID")
    _ensure(isinstance(receipt.get("decision_id"), str) and len(receipt["decision_id"]) >= 8, "invalid decision_id", "RC_RECEIPT_SCHEMA_INVALID")
    _ensure(isinstance(receipt.get("timestamp_utc"), str) and "T" in receipt["timestamp_utc"], "invalid timestamp_utc", "RC_RECEIPT_SCHEMA_INVALID")


def enforce_reason_allowlist(receipt: Dict[str, Any], allowed: Set[str]) -> None:
    """Enforce allowlist-only reason codes.

    Args:
        receipt: Receipt dict.
        allowed: Allowlisted reason code set loaded from YAML.

    Raises:
        GateCError: If any reason code is unknown or types are invalid.
    """
    rc_list = receipt.get("reason_codes", [])
    _ensure(isinstance(rc_list, list), "reason_codes must be list", "RC_RECEIPT_SCHEMA_INVALID")

    for rc in rc_list:
        if rc not in allowed:
            raise GateCError(f"Unknown reason code: {rc}", "RC_RECEIPT_REASON_CODE_UNKNOWN")

    decision = receipt.get("decision", {})
    if isinstance(decision, dict):
        hybrid = decision.get("hybrid")
        if isinstance(hybrid, dict) and "falsifier_reason_codes" in hybrid:
            frc = hybrid.get("falsifier_reason_codes", [])
            _ensure(isinstance(frc, list), "hybrid.falsifier_reason_codes must be list", "RC_RECEIPT_SCHEMA_INVALID")
            for rc in frc:
                if rc not in allowed:
                    raise GateCError(f"Unknown hybrid reason code: {rc}", "RC_RECEIPT_REASON_CODE_UNKNOWN")


def _utc_now_rfc3339() -> str:
    """Return current UTC timestamp in RFC3339 with 'Z' suffix."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class GateC:
    """Decision Receipt Builder & Enforcer.

    WHY deterministic canonical_json:
        All hashes are computed from canonical JSON bytes. Any platform variance breaks replay.

    WHY exclude timestamp_utc from receipt_hash:
        timestamp_utc changes every run; excluding it keeps receipt_hash content-based and replayable.

    WHY allowlist-only reason codes:
        Prevent free-text semantic drift and block policy bypass. Must load from YAML allowlist.
    """

    def __init__(
        self,
        base_dir: Optional[str] = None,
        reasons_path: str = "REASON_CODES_v1.yaml",
        locks_path: str = "GOLDEN_IO_LOCK_GATEC_v1.yaml",
        locks_digest: str = "locks_v1",
    ) -> None:
        """Initialize GateC and load allowlisted reason codes.

        Args:
            base_dir: Base directory for resolving relative paths.
            reasons_path: Path to reason code allowlist YAML.
            locks_path: Path to lock YAML (kept for compatibility).
            locks_digest: Lock digest included in determinism_key.

        Raises:
            GateCError: If allowlist cannot be loaded.
        """
        self.base_dir: str = base_dir or os.getcwd()
        self.reasons_path: str = os.path.join(self.base_dir, reasons_path)
        self.locks_path: str = os.path.join(self.base_dir, locks_path)
        self.locks_digest: str = locks_digest

        self._allowed_reason_codes: Set[str] = load_allowed_reason_codes(self.reasons_path)

    @property
    def allowed_reason_codes(self) -> Set[str]:
        """Return a copy of allowlisted reason codes."""
        return set(self._allowed_reason_codes)

    def build_receipt(
        self,
        *,
        toolchain_manifest_digest: str,
        context_level: str,
        context_hash: str,
        router_decision: str,
        guard_verdict: str,
        risk_params: Dict[str, Any],
        parameters_payload: Dict[str, Any],
        evidence_set_payload: Dict[str, Any],
        evidence_refs: List[Dict[str, Any]],
        reason_codes: Optional[List[str]] = None,
        hybrid: Optional[Dict[str, Any]] = None,
        decision_id: Optional[str] = None,
        timestamp_utc: Optional[str] = None,
        project_id: Optional[str] = None,
        module_id: Optional[str] = None,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build a locked receipt and compute the hash chain.

        Args:
            toolchain_manifest_digest: Digest describing runtime/toolchain manifest.
            context_level: One of {"L0","L1","L2","L3"}.
            context_hash: Digest of context snapshot.
            router_decision: Router decision string.
            guard_verdict: One of {"APPROVED","REJECTED","DEGRADED","SAFE_MODE"}.
            risk_params: Risk parameters dict.
            parameters_payload: Payload for parameters_hash.
            evidence_set_payload: Payload for evidence_set_hash.
            evidence_refs: Non-empty list of evidence references.
            reason_codes: Optional list of allowlisted reason codes.
            hybrid: Optional decision.hybrid dict.
            decision_id: Optional decision id; generated if None.
            timestamp_utc: Optional timestamp; generated if None.
            project_id: Optional; defaults to "unknown_project".
            module_id: Optional; defaults to "unknown_module".
            language: Optional; defaults to "python".

        Returns:
            Receipt dict.

        Raises:
            GateCError: On schema violations or unknown reason codes.
        """
        params_canon = canonical_json(parameters_payload)
        evidence_canon = canonical_json(evidence_set_payload)

        receipt_project_id = project_id or "unknown_project"
        receipt_module_id = module_id or "unknown_module"
        receipt_language = language or "python"

        receipt: Dict[str, Any] = {
            "decision_id": decision_id or f"dec_{uuid.uuid4().hex[:12]}",
            "timestamp_utc": timestamp_utc or _utc_now_rfc3339(),
            "project_id": receipt_project_id,
            "module_id": receipt_module_id,
            "language": receipt_language,
            "toolchain_manifest_digest": toolchain_manifest_digest,
            "context": {"context_level": context_level, "context_hash": context_hash},
            "decision": {
                "router_decision": router_decision,
                "guard_verdict": guard_verdict,
                "risk_params": risk_params,
            },
            "hashes": {
                "parameters_hash": sha256_hex(params_canon),
                "evidence_set_hash": sha256_hex(evidence_canon),
                "receipt_hash": "TEMP",
            },
            "evidence_refs": evidence_refs,
            "reason_codes": list(reason_codes or []),
            "determinism_key": "TEMP",
        }

        if hybrid is not None:
            receipt["decision"]["hybrid"] = hybrid

        enforce_reason_allowlist(receipt, self._allowed_reason_codes)

        config: Dict[str, Any] = {
            "project_id": receipt["project_id"],
            "module_id": receipt["module_id"],
            "language": receipt["language"],
        }
        receipt["determinism_key"] = compute_determinism_key(config, toolchain_manifest_digest, self.locks_digest)
        receipt["hashes"]["receipt_hash"] = compute_receipt_hash(receipt)

        validate_receipt_schema(receipt)

        return receipt

    def validate(self, receipt: Dict[str, Any]) -> None:
        """Validate receipt: schema + allowlist + receipt_hash + determinism_key."""
        validate_receipt_schema(receipt)
        enforce_reason_allowlist(receipt, self._allowed_reason_codes)

        hashes = receipt.get("hashes")
        _ensure(isinstance(hashes, dict), "hashes must be object", "RC_RECEIPT_SCHEMA_INVALID")

        expected_hash = compute_receipt_hash(receipt)
        if hashes.get("receipt_hash") != expected_hash:
            raise GateCError("receipt_hash mismatch", "RC_RECEIPT_SCHEMA_INVALID")

        if not receipt.get("determinism_key"):
            raise GateCError("determinism_key missing", "RC_DETERMINISM_KEY_MISSING")

    def write_receipt(self, receipt: Dict[str, Any], path: str) -> str:
        """Write receipt to disk as canonical JSON with write-once semantics."""
        self.validate(receipt)

        abs_path = path if os.path.isabs(path) else os.path.join(self.base_dir, path)
        payload = canonical_json(receipt)

        os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)

        try:
            with open(abs_path, "x", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
        except FileExistsError as exc:
            raise GateCError(
                "Receipt already exists (must be write-once)",
                "RC_RECEIPT_NOT_WRITTEN_PRE_EXECUTION",
            ) from exc

        return abs_path
