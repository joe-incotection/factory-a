"""test_m7_integrity.py — Anti-Tamper Replay tests (BLOCK-02)

Verifies that M7 computes and stores replay_artifacts_hash in evidence,
and that this hash changes when the artifacts bundle is tampered.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

# Path setup: add sandbox m7 dir so module7_runtime_replay resolves from sandbox
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "m7"))

import pytest
import module7_runtime_replay as m7


# ── Test doubles ──────────────────────────────────────────────────────────────

def _fake_dk_fn(runtime_payload: dict, policy_digests: dict) -> str:
    """Minimal test double for determinism_key_fn (2-arg SSOT signature)."""
    blob = json.dumps(
        {"payload": runtime_payload, "policy": policy_digests},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return "sha256:" + hashlib.sha256(blob).hexdigest()


class _OkRunner:
    def run(self, *, command: str, working_directory: str, timeout_s: int) -> dict:
        return {"ok": True, "exit_code": 0, "stdout": "", "stderr": "", "duration_ms": 5}


def _make_pin_set() -> dict:
    return {
        "kami_version": "v2.0.1",
        "dna_version": "v2.1",
        "smart_spec_version": "v1.0",
        "reason_codes_version": "v1",
        "context_gate_version": "v1",
        "noise_budget_version": "v1",
        "toolchain_digest": "py311:abc",
        "determinism_policy_version": "v1",
    }


def _make_artifacts(runtime_payload: dict | None = None) -> dict:
    if runtime_payload is None:
        runtime_payload = {"tests": [{"name": "test_ok", "status": "PASSED"}]}
    return {
        "test_command": "pytest -q",
        "working_directory": ".",
        "timeout_s": 30,
        "pytest_runtime_payload": runtime_payload,
        "toolchain_manifest_digest": "py311:abc",
        "policy_digests": {
            "reason_codes_sha256": "rc:111",
            "context_gate_sha256": "cg:222",
            "noise_budget_sha256": "nb:333",
        },
    }


def _run(artifacts: dict) -> dict:
    runtime_payload = artifacts["pytest_runtime_payload"]
    policy_digests = artifacts["policy_digests"]
    first_key = _fake_dk_fn(runtime_payload, policy_digests)
    return m7.verify_runtime_replay(
        first_run_key=first_key,
        replay_artifacts=artifacts,
        validation_result={},
        pin_set=_make_pin_set(),
        enable_m7_replay=True,
        runner=_OkRunner(),
        determinism_key_fn=_fake_dk_fn,
    )


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_artifacts_hash_present_in_evidence():
    """evidence must contain replay_artifacts_hash (BLOCK-02 anti-tamper field)."""
    out = _run(_make_artifacts())
    assert out["replay_verified"] is True, f"Expected verified: {out}"
    ev = out["evidence"]
    assert "replay_artifacts_hash" in ev, "evidence missing replay_artifacts_hash"
    assert isinstance(ev["replay_artifacts_hash"], str)
    assert len(ev["replay_artifacts_hash"]) == 64, "expected SHA256 hex (64 chars)"


def test_artifacts_hash_is_sha256_of_bundle():
    """replay_artifacts_hash must equal SHA256(canonical JSON of artifacts dict)."""
    artifacts = _make_artifacts()
    expected = hashlib.sha256(
        json.dumps(artifacts, sort_keys=True, default=str).encode()
    ).hexdigest()
    out = _run(artifacts)
    assert out["evidence"]["replay_artifacts_hash"] == expected


def test_artifacts_hash_changes_when_bundle_tampered():
    """Different artifacts bundles must produce different replay_artifacts_hash."""
    artifacts_a = _make_artifacts({"tests": [{"name": "test_a", "status": "PASSED"}]})
    artifacts_b = _make_artifacts({"tests": [{"name": "test_b", "status": "PASSED"}]})
    out_a = _run(artifacts_a)
    out_b = _run(artifacts_b)
    assert (
        out_a["evidence"]["replay_artifacts_hash"]
        != out_b["evidence"]["replay_artifacts_hash"]
    ), "artifacts_hash must differ when artifacts bundle content differs"


def test_artifacts_hash_stable_for_same_bundle():
    """Same artifacts bundle must always produce identical replay_artifacts_hash."""
    artifacts = _make_artifacts()
    out1 = _run(artifacts)
    out2 = _run(artifacts)
    assert (
        out1["evidence"]["replay_artifacts_hash"]
        == out2["evidence"]["replay_artifacts_hash"]
    ), "artifacts_hash must be deterministic for identical inputs"


def test_replay_verified_true_on_clean_path():
    """Full clean-path: replay_verified=True, reason_code=None, artifacts_hash set."""
    out = _run(_make_artifacts())
    assert out["replay_verified"] is True
    assert out["reason_code"] is None
    assert out["evidence"]["replay_artifacts_hash"] is not None
