"""test_aggregator_strict_mode.py — Aggregator Hard-Fail Logic tests (BLOCK-02)

Verifies that aggregate_and_report raises CriticalSystemError with
reason_code RC_ENGINE_SCORE_MISSING when static_analysis or runtime_validation
is missing from any module result (no silent 0.0 default).
"""
from __future__ import annotations

import pathlib
import sys

# Path setup: add sandbox stage2 dir
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "stage2"))

import pytest
from aggregate_and_report import CriticalSystemError, aggregate_and_report


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(module_results: list) -> dict:
    return aggregate_and_report(
        submission_descriptor={"submission_id": "strict-mode-test"},
        module_results=module_results,
        static_findings=[],
        runtime_findings=[],
        context_gate_info={"level": "L3"},
        toolchain_manifest={"python_version": "3.11", "platform": "test"},
        policy_digests={"policy_a": "abc123"},
    )


def _full_module(static_score: float = 1.0, runtime_score: float = 1.0) -> dict:
    return {
        "module_id": "m_test",
        "static_analysis": {"score": static_score},
        "runtime_validation": {"score": runtime_score},
        "file_count": 5,
        "root_path": "/m_test",
        "language": "python",
    }


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_missing_static_analysis_raises_critical():
    """Missing static_analysis → CriticalSystemError(RC_ENGINE_SCORE_MISSING)."""
    module = _full_module()
    del module["static_analysis"]
    with pytest.raises(CriticalSystemError) as exc_info:
        _run([module])
    assert exc_info.value.reason_code == "RC_ENGINE_SCORE_MISSING"


def test_missing_runtime_validation_raises_critical():
    """Missing runtime_validation → CriticalSystemError(RC_ENGINE_SCORE_MISSING)."""
    module = _full_module()
    del module["runtime_validation"]
    with pytest.raises(CriticalSystemError) as exc_info:
        _run([module])
    assert exc_info.value.reason_code == "RC_ENGINE_SCORE_MISSING"


def test_static_analysis_none_raises_critical():
    """static_analysis=None → CriticalSystemError (must not silently default to 0.0)."""
    module = _full_module()
    module["static_analysis"] = None
    with pytest.raises(CriticalSystemError) as exc_info:
        _run([module])
    assert exc_info.value.reason_code == "RC_ENGINE_SCORE_MISSING"


def test_runtime_validation_none_raises_critical():
    """runtime_validation=None → CriticalSystemError (must not silently default to 0.0)."""
    module = _full_module()
    module["runtime_validation"] = None
    with pytest.raises(CriticalSystemError) as exc_info:
        _run([module])
    assert exc_info.value.reason_code == "RC_ENGINE_SCORE_MISSING"


def test_both_engines_present_no_error():
    """Both engines present → no exception, final_verdict returned."""
    result = _run([_full_module(static_score=1.0, runtime_score=1.0)])
    assert "final_verdict" in result
    assert result["final_verdict"] in ("PASS", "REVIEW", "FAIL")


def test_second_module_missing_engine_still_raises():
    """Missing engine in ANY module raises CriticalSystemError, not just first."""
    modules = [
        _full_module(static_score=1.0, runtime_score=1.0),  # valid
        {   # invalid: no runtime_validation
            "module_id": "m_bad",
            "static_analysis": {"score": 0.9},
            "file_count": 3,
            "root_path": "/m_bad",
            "language": "python",
        },
    ]
    with pytest.raises(CriticalSystemError) as exc_info:
        _run(modules)
    assert exc_info.value.reason_code == "RC_ENGINE_SCORE_MISSING"
