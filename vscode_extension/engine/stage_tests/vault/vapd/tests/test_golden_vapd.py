"""
Golden Tests (7/7) — VAPD v1.0 (with Survival Codes)
LAW: signature, output schema, allowlist reason codes, determinism.
"""
from __future__ import annotations

import json
import math
from typing import Any, Dict, List
import importlib
import pytest

ALLOWED_REASON_CODES = {
    # Core VAPD codes
    'VAPD_SIGNAL_WEAK',
    'VAPD_VOLATILITY_TOO_HIGH',
    # Survival codes (Drift Alarm Law S3)
    'VAPD_VOLATILITY_SPIKE',
    'VAPD_ANOMALY_DETECTED',
    'VAPD_REGIME_FLIP',
    'VAPD_EVIDENCE_INCOMPLETE'
}

def _round6(x: float) -> float:
    y = round(float(x), 6)
    return 0.0 if y == 0.0 else y

def _canon(obj: Any) -> Any:
    if obj is None or isinstance(obj, (bool, int, str)):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj):
            return None
        if math.isinf(obj):
            return "INF" if obj > 0 else "-INF"
        return _round6(obj)
    if isinstance(obj, list):
        return [_canon(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _canon(obj[k]) for k in sorted(obj.keys())}
    return str(obj)

def canonical_json(obj: Any) -> str:
    return json.dumps(_canon(obj), sort_keys=True, ensure_ascii=False, separators=(",", ":"))

def _close() -> List[float]:
    return [1.0, 1.02, 1.01, 1.05, 1.03]

def _cfg() -> Dict[str, Any]:
    return {"threshold": 0.5}


import pytest as _pytest

@_pytest.fixture(autouse=True)
def _flush_vapd_stub():
    """Flush any stub vapd loaded by other modules (e.g. compute_runner) before each test."""
    for _k in list(__import__("sys").modules.keys()):
        if _k == "vapd" or _k.startswith("vapd."):
            __import__("sys").modules.pop(_k, None)
    yield
    for _k in list(__import__("sys").modules.keys()):
        if _k == "vapd" or _k.startswith("vapd."):
            __import__("sys").modules.pop(_k, None)


def test_01_import_and_signature():
    m = importlib.import_module("vapd")
    assert hasattr(m, "run") and callable(m.run)

def test_02_output_schema():
    import vapd
    out = vapd.run(_close(), _cfg())
    assert "vapd_output" in out
    v = out["vapd_output"]
    assert set(v.keys()) == {"signal_type","confidence","metadata"}
    assert v["signal_type"] in ["BUY","SELL","NONE"]
    assert 0.0 <= float(v["confidence"]) <= 1.0
    assert isinstance(v["metadata"].get("reason_codes", []), list)

def test_03_reason_allowlist():
    import vapd
    v = vapd.run(_close(), _cfg())["vapd_output"]
    for c in v["metadata"].get("reason_codes", []):
        assert c in ALLOWED_REASON_CODES

def test_04_determinism():
    import vapd
    a = vapd.run(_close(), _cfg())
    b = vapd.run(_close(), _cfg())
    assert canonical_json(a) == canonical_json(b)

def test_05_no_raw_or_truth_required():
    # ensure signature does not require a dict with raw/truth/noise
    import inspect, vapd
    params = list(inspect.signature(vapd.run).parameters.keys())
    assert params[:2] == ["cleaned_close","config"]

def test_06_float_normalization_6dp():
    s = canonical_json({"x": 1.23456789})
    assert "1.234568" in s

def test_07_missing_close_raises():
    import vapd
    with pytest.raises(Exception):
        vapd.run([], _cfg())
