"""
Golden execution law for TRINITY_M1_ADAPTER.
S3 must implement code that passes 7/7 tests.
"""

from __future__ import annotations

import json
from copy import deepcopy

import pytest

from trinity_m1_adapter.engine import run_trinity_m1_adapter
from trinity_m1_adapter.exceptions import TrinityM1AdapterError


def _sample_trinity_m1_output() -> dict:
    return {
        "cleaned_structure_signal": {
            "signal_label": "LEAD",
            "cleaned_close": [1.0, 1.1, 1.2],
            "trend_component": [0.1, 0.2, 0.3],
            "cycle_component": [0.0, 0.0, 0.1],
            "kalman_state_last": {"x": 1.2},
        },
        "noise_residual": {"value": 0.123456},
        "spectral_signature": {"dominant_freq": 0.25},
        "broker_audit": {
            "trust_score": 0.91,
            "trust_state": "TRUSTED",
            "evidence_log": [
                {
                    "timestamp_utc": "2026-03-01T00:00:00Z",
                    "pattern_name": "NONE",
                    "confidence_0_1": 0.0,
                    "evidence_strength": 0.0,
                    "raw_refs": {
                        "segment_hash": "sha256:seg001",
                        "residual_indices": [0, 1, 2],
                    },
                    "eid": "EID_001",
                    "source": "trinity_m1",
                    "data_hash": "sha256:data001",
                }
            ],
        },
        "metadata": {
            "audit_quality": "NORMAL",
            "processing_time_ms": 1.0,
            "context": {
                "oil_price": 75.3,
                "yield_10y": 4.25,
                "fx_correlation": 0.82,
            },
        },
    }


def _canonical_json(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def test_01_happy_path_maps_required_fields():
    out = run_trinity_m1_adapter(_sample_trinity_m1_output())

    assert out["adapter_version"] == "v1.0"
    assert out["source_module"] == "trinity_m1"
    assert out["mapping_status"] == "OK"
    assert out["mapped_context"]["trinity_signal"] == "LEAD"
    assert out["mapped_context"]["noise_residual"]["value"] == 0.123456
    assert out["candidate_features"]["oil_price"] == 75.3
    assert out["candidate_features"]["yield_10y"] == 4.25
    assert out["candidate_features"]["fx_correlation"] == 0.82


def test_02_partial_path_optional_fields_missing_becomes_partial():
    payload = _sample_trinity_m1_output()
    payload["metadata"] = {"audit_quality": "NORMAL", "processing_time_ms": 1.0}

    out = run_trinity_m1_adapter(payload)

    assert out["mapping_status"] == "PARTIAL"
    assert out["candidate_features"]["oil_price"] is None
    assert out["candidate_features"]["yield_10y"] is None
    assert out["candidate_features"]["fx_correlation"] is None
    assert out["missing_fields"] == [
        "candidate_features.fx_correlation",
        "candidate_features.oil_price",
        "candidate_features.yield_10y",
    ]


def test_03_missing_required_field_blocks():
    payload = _sample_trinity_m1_output()
    del payload["noise_residual"]

    with pytest.raises(TrinityM1AdapterError) as exc:
        run_trinity_m1_adapter(payload)

    assert "TRINITY_M1_ADAPTER_REQUIRED_FIELD_MISSING" in exc.value.reason_codes


def test_04_invalid_input_shape_blocks():
    with pytest.raises(TrinityM1AdapterError) as exc:
        run_trinity_m1_adapter(["not", "a", "dict"])  # type: ignore[arg-type]

    assert "TRINITY_M1_ADAPTER_INVALID_INPUT_SHAPE" in exc.value.reason_codes


def test_05_evidence_refs_are_deterministically_sorted():
    payload = _sample_trinity_m1_output()
    payload["broker_audit"]["evidence_log"] = [
        {
            "timestamp_utc": "2026-03-01T00:00:00Z",
            "pattern_name": "NONE",
            "confidence_0_1": 0.0,
            "evidence_strength": 0.0,
            "raw_refs": {"segment_hash": "sha256:b", "residual_indices": [1]},
            "eid": "B",
            "source": "z_source",
            "data_hash": "sha256:b",
        },
        {
            "timestamp_utc": "2026-03-01T00:00:00Z",
            "pattern_name": "NONE",
            "confidence_0_1": 0.0,
            "evidence_strength": 0.0,
            "raw_refs": {"segment_hash": "sha256:a", "residual_indices": [0]},
            "eid": "A",
            "source": "a_source",
            "data_hash": "sha256:a",
        },
    ]

    out = run_trinity_m1_adapter(payload)

    assert out["evidence_refs"] == [
        {"eid": "A", "source": "a_source", "data_hash": "sha256:a"},
        {"eid": "B", "source": "z_source", "data_hash": "sha256:b"},
    ]


def test_06_same_input_same_output_deterministic():
    payload = _sample_trinity_m1_output()

    out1 = run_trinity_m1_adapter(deepcopy(payload))
    out2 = run_trinity_m1_adapter(deepcopy(payload))

    assert _canonical_json(out1) == _canonical_json(out2)


def test_07_no_scoring_or_routing_fields_emitted():
    out = run_trinity_m1_adapter(_sample_trinity_m1_output())

    forbidden = {
        "scenario_id",
        "scenario_version",
        "match_score",
        "gap_score",
        "veto",
        "decision",
        "router_action",
    }
    assert forbidden.isdisjoint(out.keys())
