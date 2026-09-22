from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest
import yaml


# Detect if we're in integrated bundle by checking if real data_collector exists
_TESTS_DIR = Path(__file__).parent
_IN_INTEGRATED_ENV = importlib.util.find_spec("data_collector") is not None


# ---------------- LAW FILES (ONLY 2) ----------------
@pytest.fixture()
def law_files() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    root = Path(__file__).resolve().parents[1]
    gio_path = root / "GOLDEN_IO_LOCK_COMPUTE_RUNNER.yaml"
    rc_path = root / "REASON_CODES_COMPUTE_RUNNER.yaml"
    with gio_path.open("r", encoding="utf-8") as f:
        gio = yaml.safe_load(f)
    with rc_path.open("r", encoding="utf-8") as f:
        rc = yaml.safe_load(f)
    return gio, rc


def _install_stub_modules() -> None:
    # Stub data_collector with strict signature requiring Bar objects
    mod_dc = type(sys)("data_collector")

    def collect_window(symbol: str, timeframe: str, end_time_utc: str, window_bars: int, market_bars: List[Any], truth_bars: List[Any] | None = None) -> Dict[str, Any]:
        # Assert Bar objects (has to_dict)
        assert isinstance(market_bars, list)
        assert len(market_bars) > 0
        assert hasattr(market_bars[0], "to_dict")
        market_window = [b.to_dict() for b in market_bars[-window_bars:]] if window_bars > 0 else [b.to_dict() for b in market_bars]
        out: Dict[str, Any] = {
            "ok": True,
            "market_window": market_window,
            "collector_meta": {"aligned": True, "source": "stub"},
        }
        if truth_bars is not None:
            out["truth_window"] = [b.to_dict() for b in truth_bars[-window_bars:]] if window_bars > 0 else [b.to_dict() for b in truth_bars]
        return out

    mod_dc.collect_window = collect_window  # type: ignore[attr-defined]
    sys.modules["data_collector"] = mod_dc

    # Stub trinity_m1
    mod_m1 = type(sys)("trinity_m1")

    def run(payload: Dict[str, Any]) -> Dict[str, Any]:
        # Minimal required keys
        return {
            "trust_score": 0.9,
            "noise_residual": {"residual": 0.01},
            "broker_audit": {"spread_ok": True},
            "cleaned_structure_signal": {"signal_type": "NONE"},
        }

    mod_m1.run = run  # type: ignore[attr-defined]
    sys.modules["trinity_m1"] = mod_m1
    
    # CLEANUP: Remove real modules first to prevent cache pollution
    for mod_name in ["gim", "eql", "vapd", "omnigraph_full"]:
        sys.modules.pop(mod_name, None)

    # Stub gim — deterministic (no datetime.now())
    mod_gim = type(sys)("gim")
    def gim_run(config=None) -> Dict[str, Any]:
        return {
            "composite_score": 0.0,
            "is_risk_elevated": False,
            "fetch_status": "OK",
            "factor_scores": {"VIX": 0.0, "TNX": 0.0, "OIL": 0.0, "GOLD": 0.0},
            "timestamp": "1970-01-01T00:00:00+00:00",
        }
    mod_gim.run = gim_run
    sys.modules["gim"] = mod_gim

    # Stub eql — deterministic
    mod_eql = type(sys)("eql")
    def eql_run(broker_audit, execution_data, config) -> Dict[str, Any]:
        return {
            "eql_output": {
                "broker_trust": 0.9,
                "anomalies": [],
                "metadata": {
                    "reason_codes": [],
                    "timestamp": "1970-01-01T00:00:00+00:00",
                    "module": "EQL",
                    "version": "1.0",
                },
            }
        }
    mod_eql.run = eql_run
    sys.modules["eql"] = mod_eql

    # Stub vapd — deterministic
    mod_vapd = type(sys)("vapd")
    def vapd_run(cleaned_close, config) -> Dict[str, Any]:
        return {
            "vapd_output": {
                "signal_type": "NONE",
                "confidence": 0.0,
                "metadata": {
                    "reason_codes": [],
                    "timestamp": "1970-01-01T00:00:00+00:00",
                    "module": "VAPD",
                    "version": "1.0",
                    "volatility_metrics": {"current": 0.0, "regime": "LOW"}
                }
            }
        }
    mod_vapd.run = vapd_run
    sys.modules["vapd"] = mod_vapd

    # Stub omnigraph_full — deterministic
    mod_omni = type(sys)("omnigraph_full")
    def omni_evaluate(context) -> Dict[str, Any]:
        return {
            "omnigraph_advisory": {
                "evidence_complete": True,
                "scenario_id": "NONE",
                "match_score": 0.0,
                "scenario_features_hash": "sha256:0",
                "anomaly_detected": False,
                "anomaly_score": 0.0,
                "anomaly_types": [],
                "regime_state": "NORMAL",
                "regime_confidence": 1.0,
                "falsifier_verdict": "PASS",
                "veto_signal": False,
                "reason_codes": ["RC_OMNIGRAPH_SUCCESS"],
                "processing_time_ms": 0.0,
                "data_sources_count": 0,
                "timestamp_utc": "1970-01-01T00:00:00Z",
            }
        }
    mod_omni.evaluate = omni_evaluate
    sys.modules["omnigraph_full"] = mod_omni

def _make_payload(n: int = 8) -> Dict[str, Any]:
    bars = []
    for i in range(n):
        bars.append(
            {
                "ts_utc": f"2026-02-16T00:00:{i:02d}Z",
                "open": 1.0 + i * 0.001,
                "high": 1.0 + i * 0.001 + 0.0005,
                "low": 1.0 + i * 0.001 - 0.0005,
                "close": 1.0 + i * 0.001,
                "volume": 100 + i,
            }
        )
    return {
        "symbol": "EURUSD",
        "timeframe": "1m",
        "end_time_utc": "2026-02-16T00:00:07Z",
        "window_bars": 5,
        "market_bars": bars,
        "budget": 10000.0,
        "vip_config": {"mode": "SHADOW", "caps": {"max_lot": 0.01}},
    }


def _assert_schema(artifact: Dict[str, Any], gio: Dict[str, Any]) -> None:
    for k in gio["required_top_level_keys"]:
        assert k in artifact, f"missing top key: {k}"
    assert artifact["status"] in gio["allowed_status"]
    # input required
    for k in gio["input_schema"]["required_keys"]:
        assert k in artifact["input"]
    # collect_result required
    for k in gio["collect_result_schema"]["required_keys"]:
        assert k in artifact["collect_result"]
    # trinity_m1 required
    for k in gio["trinity_m1_schema"]["required_keys"]:
        assert k in artifact["trinity_m1"]
    # brain_context required
    for k in gio["brain_context_required_keys"]:
        assert k in artifact["brain_context"]
    # determinism required
    for k in gio["determinism_schema"]["required_keys"]:
        assert k in artifact["determinism"]
    assert isinstance(artifact["errors"], list)
    # pulse_context must exist in brain_context (status OK or SKIP)
    bc = artifact.get("brain_context", {})
    assert "pulse_context" in bc, "brain_context missing pulse_context"
    pc = bc["pulse_context"]
    assert pc.get("status") in ("OK", "SKIP"), f"pulse_context status invalid: {pc.get('status')}"
    assert isinstance(pc.get("reason_codes"), list), "pulse_context reason_codes must be list"


def _assert_reason_codes(artifact: Dict[str, Any], rc: Dict[str, Any]) -> None:
    allow = set(rc["allowlist"])
    assert isinstance(artifact["reason_codes"], list)
    assert all(r in allow for r in artifact["reason_codes"])


def test_01_law_files_only_two(law_files: Tuple[Dict[str, Any], Dict[str, Any]]) -> None:
    gio, rc = law_files
    assert gio["module_id"] == "compute_runner"
    assert rc["module_id"] == "compute_runner"


def test_02_happy_path_schema(law_files: Tuple[Dict[str, Any], Dict[str, Any]]) -> None:
    _install_stub_modules()
    from compute_runner import run_compute

    gio, rc = law_files
    artifact = run_compute(_make_payload())
    assert artifact["status"] == "success"
    _assert_schema(artifact, gio)
    _assert_reason_codes(artifact, rc)


def test_03_adapter_passes_bar_objects() -> None:
    _install_stub_modules()
    from compute_runner import run_compute

    artifact = run_compute(_make_payload())
    assert artifact["status"] == "success"
    # Collector_meta indicates stub ran; means signature call succeeded with Bar objects
    assert artifact["collect_result"]["collector_meta"]["source"] == "stub"


def test_04_determinism_digests_stable() -> None:
    _install_stub_modules()
    from compute_runner import run_compute

    p = _make_payload()
    a1 = run_compute(p)
    a2 = run_compute(p)
    assert a1["determinism"]["canonical_input_digest"] == a2["determinism"]["canonical_input_digest"]
    assert a1["determinism"]["canonical_output_digest"] == a2["determinism"]["canonical_output_digest"]


def test_05_fail_closed_on_bad_bars(law_files: Tuple[Dict[str, Any], Dict[str, Any]]) -> None:
    _install_stub_modules()
    from compute_runner import run_compute

    gio, rc = law_files
    p = _make_payload()
    p["market_bars"][0]["ts_utc"] = "BAD_TS"
    art = run_compute(p)
    assert art["status"] == "error"
    _assert_schema(art, gio)
    _assert_reason_codes(art, rc)
    assert len(art["errors"]) >= 1


def test_06_fail_closed_on_missing_collector() -> None:
    """Test that compute_runner fails gracefully when collector returns error."""
    _install_stub_modules()
    # Override collector to raise exception (simulate broken collector)
    mod_dc = type(sys)("data_collector")
    def collect_window(*args, **kwargs):
        raise RuntimeError("simulated collector failure")
    mod_dc.collect_window = collect_window
    sys.modules["data_collector"] = mod_dc

    from compute_runner import run_compute
    art = run_compute(_make_payload())
    assert art["status"] == "error"
    assert any(e["code"] for e in art["errors"])

def test_07_fail_closed_on_m1_missing_key() -> None:
    # Stub collector ok, but M1 returns missing keys
    mod_dc = type(sys)("data_collector")
    def collect_window(symbol: str, timeframe: str, end_time_utc: str, window_bars: int, market_bars: List[Any], truth_bars: List[Any] | None = None) -> Dict[str, Any]:
        return {"ok": True, "market_window": [], "collector_meta": {"source": "stub"}}
    mod_dc.collect_window = collect_window  # type: ignore[attr-defined]
    sys.modules["data_collector"] = mod_dc

    mod_m1 = type(sys)("trinity_m1")
    def run(payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"trust_score": 0.1}  # missing keys
    mod_m1.run = run  # type: ignore[attr-defined]
    sys.modules["trinity_m1"] = mod_m1

    try:
        from compute_runner import run_compute
        art = run_compute(_make_payload())
        assert art["status"] == "error"
        assert len(art["errors"]) >= 1
    finally:
        for mod_name in ["data_collector", "trinity_m1", 
                         "gim", "eql", "vapd", "omnigraph_full"]:
            sys.modules.pop(mod_name, None)

def test_08_pulse_context_ok_when_pulse_input_provided(law_files) -> None:
    """Happy path: pulse_input provided → pulse_context.status in (OK, SKIP)."""
    _install_stub_modules()
    # Stub ws1_the_pulse.engine
    import types
    mod_ws1_pkg = types.ModuleType("ws1_the_pulse")
    mod_ws1_eng = types.ModuleType("ws1_the_pulse.engine")
    def _ws1_update(tick_event, config):
        return {"pulse_context": {
            "current_latency_ms": 2.0,
            "p50_latency_ms": 2.0,
            "p95_latency_ms": 3.0,
            "p99_latency_ms": 4.0,
            "expected_next_tick_ms": 500.0,
            "rhythm_stability_score": 1.0,
            "rhythm_state": "STABLE",
            "broker_skew_ms": 0.0,
            "skew_direction": "SYNC",
            "sample_count": 10,
            "measurement_window_n": 10,
            "measured_at_ns": tick_event["local_arrive_ns"],
            "reason_codes": ["STABLE"],
        }}
    mod_ws1_eng.update_and_measure = _ws1_update
    sys.modules["ws1_the_pulse"] = mod_ws1_pkg
    sys.modules["ws1_the_pulse.engine"] = mod_ws1_eng

    from compute_runner import run_compute
    gio, rc = law_files
    p = _make_payload()
    p["pulse_input"] = {
        "broker_ts_ns":    1_700_000_000_000_000_000,
        "local_arrive_ns": 1_700_000_002_000_000_000,
        "local_utc_ns":    1_700_000_002_000_000_000,
    }
    art = run_compute(p)
    assert art["status"] == "success"
    pc = art["brain_context"]["pulse_context"]
    assert pc["status"] in ("OK", "SKIP")
    assert isinstance(pc["reason_codes"], list)
    _assert_schema(art, gio)
    _assert_reason_codes(art, rc)
    sys.modules.pop("ws1_the_pulse", None)
    sys.modules.pop("ws1_the_pulse.engine", None)


def test_09_pulse_context_skip_when_no_pulse_input(law_files) -> None:
    """Fail-soft: no pulse_input → pulse_context.status == SKIP, pipeline still success."""
    _install_stub_modules()
    from compute_runner import run_compute
    gio, rc = law_files
    p = _make_payload()
    # No pulse_input key
    art = run_compute(p)
    assert art["status"] == "success"
    pc = art["brain_context"]["pulse_context"]
    assert pc["status"] == "SKIP"
    assert "RC_CR_PULSE_SKIPPED" in pc["reason_codes"]
    _assert_schema(art, gio)
    _assert_reason_codes(art, rc)


def test_10_pulse_determinism_same_payload_same_digest(law_files) -> None:
    """Determinism: same payload with pulse_input → identical digests."""
    _install_stub_modules()
    import types
    mod_ws1_pkg = types.ModuleType("ws1_the_pulse")
    mod_ws1_eng = types.ModuleType("ws1_the_pulse.engine")
    call_count = {"n": 0}
    def _ws1_update(tick_event, config):
        call_count["n"] += 1
        return {"pulse_context": {
            "current_latency_ms": 2.0, "p50_latency_ms": 2.0,
            "p95_latency_ms": 3.0, "p99_latency_ms": 4.0,
            "expected_next_tick_ms": 500.0, "rhythm_stability_score": 1.0,
            "rhythm_state": "STABLE", "broker_skew_ms": 0.0,
            "skew_direction": "SYNC", "sample_count": call_count["n"],
            "measurement_window_n": 10,
            "measured_at_ns": tick_event["local_arrive_ns"],
            "reason_codes": ["STABLE"],
        }}
    mod_ws1_eng.update_and_measure = _ws1_update
    sys.modules["ws1_the_pulse"] = mod_ws1_pkg
    sys.modules["ws1_the_pulse.engine"] = mod_ws1_eng

    from compute_runner import run_compute
    p = _make_payload()
    p["pulse_input"] = {
        "broker_ts_ns":    1_700_000_000_000_000_000,
        "local_arrive_ns": 1_700_000_002_000_000_000,
        "local_utc_ns":    1_700_000_002_000_000_000,
    }
    a1 = run_compute(p)
    a2 = run_compute(p)
    assert a1["determinism"]["canonical_input_digest"] == a2["determinism"]["canonical_input_digest"]
    sys.modules.pop("ws1_the_pulse", None)
    sys.modules.pop("ws1_the_pulse.engine", None)


# =============================================================================
# Correlation matrix export tests (test_11 – test_14)
# =============================================================================

_CM_SYMBOLS = ["EURUSD", "GBPUSD"]
_CM_MATRIX  = [[1.0, 0.85], [0.85, 1.0]]


def _install_omnigraph_v2_stub(symbols: List[Any], matrix: List[Any]) -> None:
    """Stub omnigraph_hybrid_v2 to return a fixed correlation matrix."""
    mod = type(sys)("omnigraph_hybrid_v2")

    def _run(context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "symbols":            symbols,
            "correlation_matrix": matrix,
            "match_score":        0.9,
            "anomaly_score":      0.1,
            "veto_signal":        False,
            "scenario_id":        "SC_NORMAL",
            "reason_codes":       [],
        }

    mod.run = _run  # type: ignore[attr-defined]
    sys.modules["omnigraph_hybrid_v2"] = mod


def _make_payload_with_gbp(n: int = 25) -> Dict[str, Any]:
    """Payload with gbp_bars (>= 20) to trigger omnigraph computation path.

    window_bars must equal n so that market_window has n bars (>= _OMNI_MIN_BARS=20).
    Without this, the collect stub slices to only 5 bars and the engine takes
    the _omni_skip path instead of calling omnigraph_hybrid_v2.
    """
    p = _make_payload(n)
    p["window_bars"] = n  # ensure market_window >= _OMNI_MIN_BARS (20)
    gbp_bars: List[Dict[str, Any]] = []
    for i in range(n):
        gbp_bars.append({
            "ts_utc": f"2026-02-16T00:00:{i % 60:02d}Z",
            "open":   1.2 + i * 0.001,
            "high":   1.2 + i * 0.001 + 0.0005,
            "low":    1.2 + i * 0.001 - 0.0005,
            "close":  1.2 + i * 0.001,
            "volume": 100 + i,
        })
    p["gbp_bars"] = gbp_bars
    return p


def test_corr_matrix_exported(tmp_path: Path) -> None:
    """After run_compute with valid omnigraph output, correlation_matrix.json must exist."""
    _install_stub_modules()
    _install_omnigraph_v2_stub(_CM_SYMBOLS, _CM_MATRIX)

    from compute_runner.engine import _export_correlation_matrix, run_compute

    out_path = tmp_path / "correlation_matrix.json"
    artifact = run_compute(_make_payload_with_gbp())
    _export_correlation_matrix(artifact, output_path=out_path)

    assert out_path.exists(), "correlation_matrix.json must be created after valid run"
    sys.modules.pop("omnigraph_hybrid_v2", None)


def test_corr_matrix_schema(tmp_path: Path) -> None:
    """Exported JSON must have 4 required fields with correct values."""
    _install_stub_modules()
    _install_omnigraph_v2_stub(_CM_SYMBOLS, _CM_MATRIX)

    from compute_runner.engine import _export_correlation_matrix, run_compute

    out_path = tmp_path / "correlation_matrix.json"
    artifact = run_compute(_make_payload_with_gbp())
    _export_correlation_matrix(artifact, output_path=out_path)

    data = json.loads(out_path.read_text(encoding="utf-8"))
    for field in ("timestamp_utc", "symbols", "matrix", "source"):
        assert field in data, f"Missing required field: {field}"
    assert data["symbols"] == _CM_SYMBOLS,  f"symbols mismatch: {data['symbols']}"
    assert data["matrix"]  == _CM_MATRIX,   f"matrix mismatch: {data['matrix']}"
    assert data["source"]  == "omnigraph_hybrid_v2"
    # timestamp_utc must be a non-empty string
    assert isinstance(data["timestamp_utc"], str) and data["timestamp_utc"]
    sys.modules.pop("omnigraph_hybrid_v2", None)


def test_corr_matrix_atomic(tmp_path: Path) -> None:
    """After write completes, the .tmp staging file must NOT exist."""
    _install_stub_modules()
    _install_omnigraph_v2_stub(_CM_SYMBOLS, _CM_MATRIX)

    from compute_runner.engine import _export_correlation_matrix, run_compute

    out_path = tmp_path / "correlation_matrix.json"
    artifact = run_compute(_make_payload_with_gbp())
    _export_correlation_matrix(artifact, output_path=out_path)

    tmp_file = Path(str(out_path) + ".tmp")
    assert not tmp_file.exists(), ".tmp file must be removed after atomic rename"
    assert out_path.exists(),     "final file must exist after atomic write"
    sys.modules.pop("omnigraph_hybrid_v2", None)


def test_corr_matrix_fail_soft(tmp_path: Path) -> None:
    """_export_correlation_matrix must not crash when omnigraph key is absent."""
    from compute_runner.engine import _export_correlation_matrix

    out_path = tmp_path / "correlation_matrix.json"

    # Case A: brain_context present but omnigraph key missing
    artifact_no_omni: Dict[str, Any] = {
        "status": "success",
        "brain_context": {"pipeline_status": {"status": "OK"}},
    }
    _export_correlation_matrix(artifact_no_omni, output_path=out_path)
    assert not out_path.exists(), "File must NOT be created when omnigraph key absent"

    # Case B: no brain_context at all
    _export_correlation_matrix({}, output_path=out_path)
    assert not out_path.exists(), "File must NOT be created when brain_context absent"

    # Case C: omnigraph present but correlation_matrix is empty list
    artifact_empty_matrix: Dict[str, Any] = {
        "status": "success",
        "brain_context": {
            "omnigraph": {
                "symbols":            [],
                "correlation_matrix": [],
            }
        },
    }
    _export_correlation_matrix(artifact_empty_matrix, output_path=out_path)
    assert not out_path.exists(), "File must NOT be created when matrix is empty"


# =============================================================================
# Multi-symbol correlation matrix tests (test_corr_15_symbols – test_corr_atomic_write)
# =============================================================================

def test_corr_15_symbols() -> None:
    """_CORR_SYMBOLS must contain exactly 15 unique symbols."""
    from compute_runner.engine import _CORR_SYMBOLS

    assert len(_CORR_SYMBOLS) == 15, f"Expected 15 symbols, got {len(_CORR_SYMBOLS)}"
    assert len(set(_CORR_SYMBOLS)) == 15, "All symbols must be unique"


def test_corr_regime_tag() -> None:
    """_detect_regime must return valid regime tags for edge-case matrices."""
    from compute_runner.engine import _detect_regime

    # All high correlations -> CRISIS
    crisis_matrix = [[1.0, 0.9, 0.85], [0.9, 1.0, 0.88], [0.85, 0.88, 1.0]]
    assert _detect_regime(crisis_matrix, ["A", "B", "C"]) == "CRISIS"

    # Medium correlations -> TRENDING
    trending_matrix = [[1.0, 0.6, 0.55], [0.6, 1.0, 0.52], [0.55, 0.52, 1.0]]
    assert _detect_regime(trending_matrix, ["A", "B", "C"]) == "TRENDING"

    # Low correlations -> DECORRELATED
    deco_matrix = [[1.0, 0.1, 0.05], [0.1, 1.0, 0.08], [0.05, 0.08, 1.0]]
    assert _detect_regime(deco_matrix, ["A", "B", "C"]) == "DECORRELATED"

    # Empty -> UNKNOWN
    assert _detect_regime([], []) == "UNKNOWN"


def test_corr_export_fields(tmp_path: Path) -> None:
    """_export_correlation_matrix with omni_ctx must write all 11 required fields."""
    from compute_runner.engine import (
        _CORR_SYMBOLS, _synthetic_correlation, _export_correlation_matrix,
    )

    matrix = _synthetic_correlation(_CORR_SYMBOLS)
    omni_ctx: Dict[str, Any] = {
        "symbols":            _CORR_SYMBOLS,
        "matrix":             matrix,
        "source":             "multi_symbol_correlation",
        "correlation_method": "synthetic",
        "rolling_window":     64,
        "n_symbols":          len(_CORR_SYMBOLS),
        "n_bars":             0,
        "regime_tag":         "NORMAL",
        "mode":               "SHADOW",
        "staleness_s":        0.0,
    }
    out_path = tmp_path / "corr.json"
    _export_correlation_matrix({}, omni_ctx, output_path=out_path)

    assert out_path.exists(), "Output file must be created"
    data = json.loads(out_path.read_text(encoding="utf-8"))
    for field in (
        "timestamp_utc", "symbols", "matrix", "source",
        "correlation_method", "rolling_window", "n_symbols",
        "n_bars", "regime_tag", "mode", "staleness_s",
    ):
        assert field in data, f"Missing required field: {field}"
    assert data["symbols"] == _CORR_SYMBOLS
    assert data["n_symbols"] == 15
    assert data["mode"] == "SHADOW"
    assert data["correlation_method"] == "synthetic"


def test_corr_pearson_symmetric(tmp_path: Path) -> None:
    """_compute_pearson must produce symmetric matrix with diagonal=1.0."""
    from compute_runner.engine import _compute_pearson

    bars_dict: Dict[str, List[float]] = {
        "EURUSD": [1.0 + i * 0.001 for i in range(40)],
        "GBPUSD": [1.2 + i * 0.0008 for i in range(40)],
        "USDJPY": [130.0 + i * 0.01 for i in range(40)],
    }
    matrix = _compute_pearson(bars_dict)
    n = len(matrix)
    assert n == 3, f"Expected 3x3 matrix, got {n} rows"

    # Diagonal must be 1.0
    for i in range(n):
        assert matrix[i][i] == 1.0, f"Diagonal [{i}][{i}] must be 1.0"

    # Symmetric
    for i in range(n):
        for j in range(n):
            assert matrix[i][j] == matrix[j][i], (
                f"matrix[{i}][{j}]={matrix[i][j]} != matrix[{j}][{i}]={matrix[j][i]}"
            )

    # All values in [-1, 1]
    for row in matrix:
        for val in row:
            assert -1.0 <= val <= 1.0, f"Value {val} out of [-1, 1]"


def test_corr_shadow_fallback() -> None:
    """_synthetic_correlation must return a valid 15x15 symmetric matrix."""
    from compute_runner.engine import _CORR_SYMBOLS, _synthetic_correlation

    matrix = _synthetic_correlation(_CORR_SYMBOLS)
    n = len(_CORR_SYMBOLS)
    assert len(matrix) == n, f"Expected {n} rows, got {len(matrix)}"

    for i, row in enumerate(matrix):
        assert len(row) == n, f"Row {i} has {len(row)} cols, expected {n}"
        assert row[i] == 1.0, f"Diagonal [{i}][{i}] must be 1.0"
        for val in row:
            assert -1.0 <= val <= 1.0, f"Value {val} out of [-1, 1]"

    # Symmetric
    for i in range(n):
        for j in range(n):
            assert matrix[i][j] == matrix[j][i], (
                f"Not symmetric at [{i}][{j}]: {matrix[i][j]} != {matrix[j][i]}"
            )


def test_corr_atomic_write(tmp_path: Path) -> None:
    """New-format atomic write: .tmp must not exist after successful export."""
    from compute_runner.engine import (
        _CORR_SYMBOLS, _synthetic_correlation, _detect_regime,
        _export_correlation_matrix,
    )

    matrix = _synthetic_correlation(_CORR_SYMBOLS)
    regime = _detect_regime(matrix, _CORR_SYMBOLS)
    omni_ctx: Dict[str, Any] = {
        "symbols":            _CORR_SYMBOLS,
        "matrix":             matrix,
        "source":             "multi_symbol_correlation",
        "correlation_method": "synthetic",
        "rolling_window":     64,
        "n_symbols":          len(_CORR_SYMBOLS),
        "n_bars":             0,
        "regime_tag":         regime,
        "mode":               "SHADOW",
        "staleness_s":        0.0,
    }
    out_path = tmp_path / "corr_atomic.json"
    _export_correlation_matrix({}, omni_ctx, output_path=out_path)

    tmp_file = Path(str(out_path) + ".tmp")
    assert not tmp_file.exists(), ".tmp file must be removed after atomic rename"
    assert out_path.exists(), "Final file must exist after atomic write"


# =============================================================================
# EA3 wiring tests (test_ea3_receives_anomaly_score – test_ea3_live_veto_path)
# =============================================================================

# Shared capture container (reset per test)
_ea3_captured_context: Dict[str, Any] = {}


def _install_ea3_capture_stub(return_action: str = "ALLOW", veto_on_high_anomaly: bool = False) -> None:
    """Install EA3 stub that captures the received context."""
    mod = type(sys)("ea3")

    def _run(context: Dict[str, Any]) -> Dict[str, Any]:
        _ea3_captured_context.clear()
        _ea3_captured_context.update(context)
        # If veto_on_high_anomaly: return HOLD when anomaly_score >= 0.9
        if veto_on_high_anomaly and float(context.get("anomaly_score", 0.0)) >= 0.9:
            return {"action": "HOLD", "lot_modifier": 0.0, "reason_codes": ["RC_EA3_HIGH_ANOMALY"]}
        return {"action": return_action, "lot_modifier": 1.0, "reason_codes": []}

    mod.run = _run  # type: ignore[attr-defined]
    # EA3 also needs async mode methods used by run_continuous
    mod.enable_async_mode = lambda: None  # type: ignore[attr-defined]
    sys.modules["ea3"] = mod


def _install_brain_router_stub(action: str = "EXECUTE", caution_level: str = "NONE") -> None:
    """Install brain_router stub returning fixed action + caution_level."""
    mod = type(sys)("brain_router")

    def _run(context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "action":        action,
            "caution_level": caution_level,
            "reason_codes":  [],
        }

    mod.run = _run  # type: ignore[attr-defined]
    sys.modules["brain_router"] = mod


def _install_omni_v2_with_anomaly(anomaly_score: float = 0.0) -> None:
    """Install omnigraph_hybrid_v2 stub returning specific anomaly_score."""
    mod = type(sys)("omnigraph_hybrid_v2")

    def _run(context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "symbols":            ["EURUSD", "GBPUSD"],
            "correlation_matrix": [[1.0, 0.85], [0.85, 1.0]],
            "match_score":        0.5,
            "anomaly_score":      anomaly_score,
            "veto_signal":        anomaly_score >= 0.9,
            "scenario_id":        "SC_NORMAL",
            "reason_codes":       [],
        }

    mod.run = _run  # type: ignore[attr-defined]
    sys.modules["omnigraph_hybrid_v2"] = mod


def _cleanup_ea3_stubs() -> None:
    for name in ("ea3", "brain_router", "omnigraph_hybrid_v2"):
        sys.modules.pop(name, None)
    _ea3_captured_context.clear()


# ── test_ea3_receives_anomaly_score ──────────────────────────────────────────

def test_ea3_receives_anomaly_score() -> None:
    """brain_context passed to EA3 must include anomaly_score as float."""
    _install_stub_modules()
    _install_omni_v2_with_anomaly(anomaly_score=0.42)
    _install_brain_router_stub()
    _install_ea3_capture_stub()

    import compute_runner.engine as _eng
    _eng._router_state["override_count"] = 0

    from compute_runner import run_compute
    run_compute(_make_payload_with_gbp())

    assert "anomaly_score" in _ea3_captured_context, "EA3 context missing anomaly_score"
    assert isinstance(_ea3_captured_context["anomaly_score"], float), \
        "anomaly_score must be float"
    # omnigraph stub set 0.42 — verify it reached EA3
    assert abs(_ea3_captured_context["anomaly_score"] - 0.42) < 1e-6, \
        f"anomaly_score mismatch: {_ea3_captured_context['anomaly_score']}"
    _cleanup_ea3_stubs()


# ── test_ea3_receives_confidence ─────────────────────────────────────────────

def test_ea3_receives_confidence() -> None:
    """brain_context passed to EA3 must include confidence in HIGH|MEDIUM|LOW."""
    _install_stub_modules()
    _install_omni_v2_with_anomaly()
    _install_brain_router_stub()
    # EQL stub returns broker_trust=0.9 -> HIGH
    _install_ea3_capture_stub()

    import compute_runner.engine as _eng
    _eng._router_state["override_count"] = 0

    from compute_runner import run_compute
    run_compute(_make_payload_with_gbp())

    assert "confidence" in _ea3_captured_context, "EA3 context missing confidence"
    assert _ea3_captured_context["confidence"] in ("HIGH", "MEDIUM", "LOW"), \
        f"confidence invalid: {_ea3_captured_context['confidence']}"
    _cleanup_ea3_stubs()


# ── test_ea3_receives_router_action ──────────────────────────────────────────

def test_ea3_receives_router_action() -> None:
    """brain_context passed to EA3 must include router_action in EXECUTE|BLOCK."""
    _install_stub_modules()
    _install_omni_v2_with_anomaly()
    _install_brain_router_stub(action="EXECUTE")
    _install_ea3_capture_stub()

    import compute_runner.engine as _eng
    _eng._router_state["override_count"] = 0

    from compute_runner import run_compute
    run_compute(_make_payload_with_gbp())

    assert "router_action" in _ea3_captured_context, "EA3 context missing router_action"
    assert _ea3_captured_context["router_action"] in ("EXECUTE", "BLOCK"), \
        f"router_action invalid: {_ea3_captured_context['router_action']}"
    assert _ea3_captured_context["router_action"] == "EXECUTE", \
        "Expected EXECUTE from brain_router stub"
    _cleanup_ea3_stubs()


# ── test_ea3_compare_log_written ─────────────────────────────────────────────

def test_ea3_compare_log_written(tmp_path: Path) -> None:
    """After run_compute, ea3_compare_log must have a new entry with all 13 fields."""
    _install_stub_modules()
    _install_omni_v2_with_anomaly(anomaly_score=0.15)
    _install_brain_router_stub(action="BLOCK", caution_level="LOW")
    _install_ea3_capture_stub(return_action="ALLOW")

    import compute_runner.engine as _eng
    _eng._router_state["override_count"] = 0
    # Override log path to tmp for isolation
    _orig_path = _eng._EA3_COMPARE_LOG_PATH
    _eng._EA3_COMPARE_LOG_PATH = tmp_path / "ea3_compare_log.jsonl"

    try:
        from compute_runner import run_compute
        run_compute(_make_payload_with_gbp())

        log_path = _eng._EA3_COMPARE_LOG_PATH
        assert log_path.exists(), "ea3_compare_log.jsonl must be created"
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) >= 1, "At least one log entry must be written"

        entry = json.loads(lines[-1])
        required_fields = (
            "timestamp_utc", "symbol", "router_action", "ea3_action",
            "delta", "mode", "confidence", "latency_ms", "reason_codes",
            "anomaly_score", "router_caution_level", "ea3_veto_applied",
            "ea3_lot_modifier", "router_override_count",
        )
        for field in required_fields:
            assert field in entry, f"Missing log field: {field}"

        assert entry["router_action"] in ("EXECUTE", "BLOCK")
        assert entry["ea3_action"] in ("ALLOW", "HOLD", "VETO")
        assert isinstance(entry["anomaly_score"], float)
        assert isinstance(entry["latency_ms"], float)
        assert entry["confidence"] in ("HIGH", "MEDIUM", "LOW")
        assert isinstance(entry["ea3_veto_applied"], bool)
        assert isinstance(entry["delta"], bool)
        assert entry["mode"] in ("COMPARE", "LIMITED", "ACTIVE")
    finally:
        _eng._EA3_COMPARE_LOG_PATH = _orig_path
        _cleanup_ea3_stubs()


# ── test_ea3_live_veto_path ───────────────────────────────────────────────────

def test_ea3_live_veto_path(tmp_path: Path) -> None:
    """When anomaly_score=0.95, EA3 stub must return HOLD (not ALLOW)."""
    _install_stub_modules()
    _install_omni_v2_with_anomaly(anomaly_score=0.95)
    _install_brain_router_stub(action="EXECUTE")
    # EA3 stub returns HOLD when anomaly_score >= 0.9
    _install_ea3_capture_stub(return_action="ALLOW", veto_on_high_anomaly=True)

    import compute_runner.engine as _eng
    _eng._router_state["override_count"] = 0
    _orig_path = _eng._EA3_COMPARE_LOG_PATH
    _eng._EA3_COMPARE_LOG_PATH = tmp_path / "ea3_veto_log.jsonl"

    try:
        from compute_runner import run_compute
        artifact = run_compute(_make_payload_with_gbp())

        # EA3 was called with anomaly_score=0.95 -> should return HOLD
        assert "anomaly_score" in _ea3_captured_context, "EA3 context missing anomaly_score"
        assert _ea3_captured_context["anomaly_score"] >= 0.9, \
            f"Expected anomaly_score >= 0.9, got {_ea3_captured_context['anomaly_score']}"

        # brain_context must store ea3 result
        ea3_stored = artifact.get("brain_context", {}).get("ea3", {})
        assert isinstance(ea3_stored, dict)
        # EA3 stub returned HOLD for anomaly >= 0.9
        assert ea3_stored.get("action") == "HOLD", \
            f"Expected HOLD, got {ea3_stored.get('action')}"

        # Compare log must show HOLD (not ALLOW)
        log_path = _eng._EA3_COMPARE_LOG_PATH
        if log_path.exists():
            entry = json.loads(log_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            assert entry["ea3_action"] != "ALLOW", \
                f"ea3_action should not be ALLOW when anomaly_score=0.95, got {entry['ea3_action']}"
    finally:
        _eng._EA3_COMPARE_LOG_PATH = _orig_path
        _cleanup_ea3_stubs()
