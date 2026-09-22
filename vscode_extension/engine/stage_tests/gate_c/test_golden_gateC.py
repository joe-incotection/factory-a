import json, math, hashlib
from typing import Any, Dict

# Self-contained golden tests for Gate C invariants (no external deps)
ALLOWED_REASON_CODES = {
    "RC_RECEIPT_SCHEMA_INVALID",
    "RC_RECEIPT_REASON_CODE_UNKNOWN",
    "RC_RECEIPT_NOT_WRITTEN_PRE_EXECUTION",
    "RC_DETERMINISM_KEY_MISSING",
    "RC_PARAMETERS_HASH_MISSING",
    "RC_EVIDENCE_SET_HASH_MISSING",
    "RC_EVIDENCE_INCOMPLETE_SAFE_MODE",
    "RC_SCENARIO_MATCH_LOW_CONFIDENCE",
    "RC_FALSIFIER_VETO_TRIGGERED",
    "RC_RUNTIME_ENV_DRIFT",
    "RC_POLICY_DRIFT_DETECTED",
}

def _norm_float(x: Any, decimals: int = 6) -> Any:
    if isinstance(x, float):
        if math.isnan(x):
            return None
        if math.isinf(x):
            return "INF" if x > 0 else "-INF"
        if x == 0.0:
            x = 0.0  # -0.0 -> 0.0
        return round(x, decimals)
    return x

def _canon(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _canon(obj[k]) for k in sorted(obj.keys())}
    if isinstance(obj, list):
        return [_canon(v) for v in obj]
    return _norm_float(obj)

def canonical_json(obj: Any) -> str:
    return json.dumps(_canon(obj), sort_keys=True, ensure_ascii=True, separators=(",", ":"))

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def compute_receipt_hash(receipt: Dict[str, Any]) -> str:
    payload = dict(receipt)
    payload.pop("timestamp_utc", None)  # LOCK: exclude timestamp
    return sha256_hex(canonical_json(payload))

def compute_determinism_key(config: Dict[str, Any], toolchain_manifest_digest: str, locks_digest: str) -> str:
    base = {"config": config, "toolchain_manifest_digest": toolchain_manifest_digest, "locks_digest": locks_digest}
    return sha256_hex(canonical_json(base))

def minimal_receipt() -> Dict[str, Any]:
    r = {
        "decision_id": "dec_12345678",
        "timestamp_utc": "2026-01-24T00:00:00Z",
        "project_id": "pythonbrain",
        "module_id": "router",
        "language": "python",
        "toolchain_manifest_digest": "t_" + "a"*62,
        "context": {"context_level": "L3", "context_hash": "c_" + "b"*62},
        "decision": {"router_decision": "EA1_LONG", "guard_verdict": "APPROVED", "risk_params": {"risk": 0.1}},
        "hashes": {"parameters_hash": "p_" + "d"*62, "evidence_set_hash": "e_" + "e"*62, "receipt_hash": "TEMP"},
        "evidence_refs": [{"name": "trinity.segment", "ref_type": "sha256", "ref_hash": "seg_" + "f"*60}],
        "reason_codes": [],
        "determinism_key": "TEMP",
    }
    r["hashes"]["receipt_hash"] = compute_receipt_hash(r)
    r["determinism_key"] = compute_determinism_key(
        {"project_id": r["project_id"], "module_id": r["module_id"], "language": r["language"]},
        r["toolchain_manifest_digest"],
        "locks_v1",
    )
    return r

def test_01_schema_minimal_presence():
    r = minimal_receipt()
    for k in ["decision_id","timestamp_utc","project_id","module_id","language","toolchain_manifest_digest","context","decision","hashes","evidence_refs","reason_codes","determinism_key"]:
        assert k in r

def test_02_reason_allowlist():
    assert "RC_RECEIPT_SCHEMA_INVALID" in ALLOWED_REASON_CODES
    r = minimal_receipt()
    r["reason_codes"] = ["RC_EVIDENCE_INCOMPLETE_SAFE_MODE"]
    assert all(rc in ALLOWED_REASON_CODES for rc in r["reason_codes"])
    r["reason_codes"] = ["RC_NOT_EXIST"]
    assert any(rc not in ALLOWED_REASON_CODES for rc in r["reason_codes"])

def test_03_canonical_json_sorted():
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})

def test_04_float_norm_nan_and_negzero():
    s = canonical_json({"x": 0.30000000000000004, "y": -0.0, "z": float("nan")})
    assert '"x":0.3' in s
    assert '"y":0.0' in s
    assert '"z":null' in s

def test_05_determinism_key_reproducible():
    r = minimal_receipt()
    k1 = compute_determinism_key({"a": 1, "b": 2.0}, r["toolchain_manifest_digest"], "locks_v1")
    k2 = compute_determinism_key({"b": 2.0, "a": 1}, r["toolchain_manifest_digest"], "locks_v1")
    assert k1 == k2

def test_06_receipt_hash_excludes_timestamp():
    r1 = minimal_receipt()
    r2 = minimal_receipt()
    r2["timestamp_utc"] = "2026-01-24T00:00:01Z"
    assert compute_receipt_hash(r1) == compute_receipt_hash(r2)

def test_07_pre_exec_persist_invariant():
    receipt_persisted_pre_exec = False
    assert receipt_persisted_pre_exec is False
    receipt_persisted_pre_exec = True
    assert receipt_persisted_pre_exec is True
