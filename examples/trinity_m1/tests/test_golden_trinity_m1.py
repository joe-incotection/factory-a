"""
Golden tests for TRINITY_M1

Law sources:
- GOLDEN_IO_LOCK_TRINITY_M1.yaml (I/O contract + canonicalization)
- TRINITY_M1_REASON_CODES.yaml (reason codes allowlist)
- SMART_SPEC_TRINITY_M1.md (public API contract)

NOTE:
- Tests are designed to be run by humans (AIEL-T).
- AI must not claim runtime results.
"""

from __future__ import annotations

import os

import hashlib
import json
from typing import Any, Dict, List

import pytest
import yaml


def _load_yaml(path: str) -> dict:
    base = os.path.join(os.path.dirname(__file__), "..")
    full_path = os.path.normpath(os.path.join(base, path))
    with open(full_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def canonical_json(obj: Any, *, float_precision_decimals: int = 6) -> str:
    """
    Canonicalize JSON per law:
    - sort_keys=True
    - float rounding to N decimals
    - no NaN/Infinity
    """
    def _norm(x: Any) -> Any:
        if isinstance(x, float):
            if x != x or x in (float("inf"), float("-inf")):
                raise ValueError("NaN/Infinity not allowed in canonical_json")
            return round(x, float_precision_decimals)
        if isinstance(x, list):
            return [_norm(i) for i in x]
        if isinstance(x, dict):
            return {k: _norm(v) for k, v in x.items()}
        return x

    normed = _norm(obj)
    return json.dumps(normed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def make_input(n: int = 256) -> Dict[str, Any]:
    # deterministic synthetic bars
    bars = []
    base = 1700000000  # fixed epoch seconds (not wall-clock)
    for i in range(n):
        ts = base + i * 60
        # ISO8601 UTC
        ts_utc = f"2023-11-14T00:{i%60:02d}:00Z"
        o = 100.0 + i * 0.01
        c = o + 0.005
        h = max(o, c) + 0.002
        l = min(o, c) - 0.002
        v = 1000.0 + i
        bars.append({"ts_utc": ts_utc, "o": o, "h": h, "l": l, "c": c, "v": v})

    return {
        "symbol": "EURUSD",
        "timeframe": "1m",
        "bars": bars,
        "meta": {"source": "MT5", "run_id": "RUN_TEST_0001"},
    }


def assert_required_fields(contract: dict, payload: dict) -> None:
    for k in contract["required"]:
        assert k in payload, f"missing required field: {k}"


def assert_types(contract_fields: dict, payload: dict) -> None:
    # Minimal type checks according to the lock (only where it is explicit)
    for key, spec in contract_fields.items():
        if key not in payload:
            continue
        t = spec.get("type")
        if t == "string":
            assert isinstance(payload[key], str)
        elif t == "number":
            assert isinstance(payload[key], (int, float))
        elif t == "object":
            assert isinstance(payload[key], dict)
        elif t == "array":
            assert isinstance(payload[key], list)


@pytest.fixture(scope="module")
def laws() -> dict:
    gio = _load_yaml("GOLDEN_IO_LOCK_TRINITY_M1.yaml")
    rc = _load_yaml("TRINITY_M1_REASON_CODES.yaml")
    return {"gio": gio, "rc": rc}



import pytest as _pytest

@_pytest.fixture(autouse=True)
def _flush_trinity_m1_stub():
    """Flush any stub trinity_m1 loaded by other modules (e.g. compute_runner) before each test."""
    for _k in list(__import__("sys").modules.keys()):
        if _k == "trinity_m1" or _k.startswith("trinity_m1."):
            __import__("sys").modules.pop(_k, None)
    yield
    for _k in list(__import__("sys").modules.keys()):
        if _k == "trinity_m1" or _k.startswith("trinity_m1."):
            __import__("sys").modules.pop(_k, None)


def test_01_public_api_exists() -> None:
    # Law: public entry point must exist
    import trinity_m1.engine as engine  # type: ignore

    assert hasattr(engine, "run_trinity_m1"), "engine.run_trinity_m1() must exist"


def test_02_happy_path_schema(laws: dict) -> None:
    import trinity_m1.engine as engine  # type: ignore

    inp = make_input(256)
    out = engine.run_trinity_m1(inp)

    gio = laws["gio"]
    assert_required_fields(gio["output_contract"], out)
    assert_types(gio["output_contract"]["fields"], out)

    # nested required checks (broker_audit + metadata)
    broker = out["broker_audit"]
    assert_required_fields(gio["output_contract"]["fields"]["broker_audit"], broker)
    meta = out["metadata"]
    assert_required_fields(gio["output_contract"]["fields"]["metadata"], meta)


def test_03_broker_audit_ranges(laws: dict) -> None:
    import trinity_m1.engine as engine  # type: ignore

    out = engine.run_trinity_m1(make_input(256))
    broker = out["broker_audit"]

    assert 0.0 <= float(broker["trust_score"]) <= 1.0
    assert broker["trust_state"] in ["TRUSTED", "WATCH", "UNTRUSTED"]

    evlog = broker["evidence_log"]
    assert isinstance(evlog, list) and len(evlog) >= 1

    # evidence_log record contract (minimal)
    rec0 = evlog[0]
    for k in ["timestamp_utc", "pattern_name", "confidence_0_1", "evidence_strength", "raw_refs"]:
        assert k in rec0


def test_04_reason_codes_allowlist_on_error(laws: dict) -> None:
    """
    Hard-fail behavior: invalid input should raise TrinityM1Error with allowlisted reason_codes.
    """
    import trinity_m1.engine as engine  # type: ignore
    from trinity_m1.exceptions import TrinityM1Error  # type: ignore

    bad = make_input(256)
    bad.pop("symbol", None)

    with pytest.raises(TrinityM1Error) as ei:
        engine.run_trinity_m1(bad)

    err = ei.value
    assert isinstance(err.reason_codes, list) and len(err.reason_codes) >= 1
    allow = set(laws["rc"]["codes"])
    for c in err.reason_codes:
        assert c in allow, f"reason code not in allowlist: {c}"


def test_05_input_bars_min_items_enforced() -> None:
    import trinity_m1.engine as engine  # type: ignore
    from trinity_m1.exceptions import TrinityM1Error  # type: ignore

    bad = make_input(10)
    with pytest.raises(TrinityM1Error):
        engine.run_trinity_m1(bad)


def test_06_determinism_same_input_same_hash(laws: dict) -> None:
    import trinity_m1.engine as engine  # type: ignore

    inp = make_input(256)
    out1 = engine.run_trinity_m1(inp)
    out2 = engine.run_trinity_m1(inp)

    gio = laws["gio"]
    cj1 = canonical_json(out1, float_precision_decimals=gio["canonicalization"]["json"]["float_precision_decimals"])
    cj2 = canonical_json(out2, float_precision_decimals=gio["canonicalization"]["json"]["float_precision_decimals"])

    assert sha256_hex(cj1) == sha256_hex(cj2)


def test_07_canonical_json_no_nan(laws: dict) -> None:
    gio = laws["gio"]
    obj = {"x": 1.23456789, "y": [1.0, 2.0]}
    s = canonical_json(obj, float_precision_decimals=gio["canonicalization"]["json"]["float_precision_decimals"])
    assert "NaN" not in s and "Infinity" not in s
