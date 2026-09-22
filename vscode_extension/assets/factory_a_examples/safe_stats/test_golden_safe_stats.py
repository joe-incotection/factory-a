"""
Golden tests for SAFE_STATS

Law sources:
- GOLDEN_IO_LOCK_SAFE_STATS.yaml (I/O contract + canonicalization)
- SAFE_STATS_REASON_CODES.yaml (reason codes allowlist)
- SMART_SPEC_SAFE_STATS.md (public API contract)

NOTE:
- Tests are designed to be run by humans (AIEL-T).
- AI must not claim runtime results.
"""

from __future__ import annotations

import hashlib
import json
import statistics
from typing import Any, Dict

import pytest
import yaml


def _load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
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


def make_input(n: int = 5) -> Dict[str, Any]:
    # deterministic synthetic series
    values = [float(i) for i in range(1, n + 1)]  # 1.0 .. n
    return {
        "values": values,
        "meta": {"run_id": "RUN_TEST_0001"},
    }


def assert_required_fields(contract: dict, payload: dict) -> None:
    for k in contract["required"]:
        assert k in payload, f"missing required field: {k}"


@pytest.fixture(scope="module")
def laws() -> dict:
    gio = _load_yaml(".factory-a/GOLDEN_IO_LOCK_SAFE_STATS.yaml")
    rc = _load_yaml(".factory-a/SAFE_STATS_REASON_CODES.yaml")
    return {"gio": gio, "rc": rc}


def test_01_public_api_exists() -> None:
    # Law: public entry point must exist
    import safe_stats.engine as engine  # type: ignore

    assert hasattr(engine, "run_safe_stats"), "engine.run_safe_stats() must exist"


def test_02_happy_path_schema(laws: dict) -> None:
    import safe_stats.engine as engine  # type: ignore

    out = engine.run_safe_stats(make_input(5))

    gio = laws["gio"]
    assert_required_fields(gio["output_contract"], out)
    assert_required_fields(gio["output_contract"]["fields"]["summary"], out["summary"])
    assert_required_fields(gio["output_contract"]["fields"]["metadata"], out["metadata"])
    assert out["metadata"]["audit_quality"] == "NORMAL"


def test_03_summary_values_and_bounds() -> None:
    import safe_stats.engine as engine  # type: ignore

    out = engine.run_safe_stats(make_input(5))  # values 1..5
    s = out["summary"]

    assert s["count"] == 5
    assert float(s["sum"]) == 15.0
    assert float(s["min"]) == 1.0
    assert float(s["max"]) == 5.0
    assert float(s["min"]) <= float(s["mean"]) <= float(s["max"])
    assert float(s["mean"]) == 3.0


def test_04_reason_codes_allowlist_on_error(laws: dict) -> None:
    """
    Hard-fail behavior: missing required field should raise SafeStatsError
    with allowlisted reason_codes.
    """
    import safe_stats.engine as engine  # type: ignore
    from safe_stats.exceptions import SafeStatsError  # type: ignore

    bad = make_input(5)
    bad.pop("values", None)

    with pytest.raises(SafeStatsError) as ei:
        engine.run_safe_stats(bad)

    err = ei.value
    assert isinstance(err.reason_codes, list) and len(err.reason_codes) >= 1
    allow = set(laws["rc"]["codes"])
    for c in err.reason_codes:
        assert c in allow, f"reason code not in allowlist: {c}"


def test_05_empty_values_rejected() -> None:
    import safe_stats.engine as engine  # type: ignore
    from safe_stats.exceptions import SafeStatsError  # type: ignore

    bad = {"values": [], "meta": {"run_id": "RUN_TEST_0002"}}
    with pytest.raises(SafeStatsError):
        engine.run_safe_stats(bad)


def test_06_determinism_same_input_same_hash(laws: dict) -> None:
    import safe_stats.engine as engine  # type: ignore

    inp = make_input(5)
    out1 = engine.run_safe_stats(inp)
    out2 = engine.run_safe_stats(inp)

    prec = laws["gio"]["canonicalization"]["json"]["float_precision_decimals"]
    cj1 = canonical_json(out1, float_precision_decimals=prec)
    cj2 = canonical_json(out2, float_precision_decimals=prec)

    assert sha256_hex(cj1) == sha256_hex(cj2)


def test_07_canonical_json_no_nan(laws: dict) -> None:
    prec = laws["gio"]["canonicalization"]["json"]["float_precision_decimals"]
    obj = {"x": 1.23456789, "y": [1.0, 2.0]}
    s = canonical_json(obj, float_precision_decimals=prec)
    assert "NaN" not in s and "Infinity" not in s


def test_08_mean_is_true_mean_oracle() -> None:
    """Invariant-with-teeth: 'mean' MUST equal the arithmetic mean (oracle).

    Derived from the semantic of the output contract, checked against an
    independent oracle (statistics.fmean) over ASYMMETRIC inputs where
    mean != median. A fixed symmetric vector (e.g. 1..5) cannot expose a
    median-disguised-as-mean bug; these inputs can.
    """
    import safe_stats.engine as engine  # type: ignore

    asymmetric_series = [
        [1.0, 2.0, 6.0],          # mean 3.0  vs median 2.0
        [0.0, 0.0, 0.0, 10.0],    # mean 2.5  vs median 0.0
        [5.0, 5.0, 5.0, 5.0, 30.0],  # mean 10.0 vs median 5.0
    ]
    for values in asymmetric_series:
        out = engine.run_safe_stats({"values": values, "meta": {"run_id": "RUN_PROP"}})
        oracle_mean = round(statistics.fmean(values), 6)
        assert abs(float(out["summary"]["mean"]) - oracle_mean) <= 1e-6, (
            f"mean mismatch for {values}: got {out['summary']['mean']}, "
            f"oracle {oracle_mean}"
        )
