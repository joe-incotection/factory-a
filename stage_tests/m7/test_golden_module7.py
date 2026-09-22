# test_golden_module7.py
# Golden Tests (SSOT) for Module 7: Runtime Replay Verifier
# Python 3.11+, pytest

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Protocol

import pytest


# ----------------------------
# Expected public API (SSOT)
# ----------------------------
# The implementation MUST provide this function:
#
# from module7_runtime_replay import verify_runtime_replay
#
# def verify_runtime_replay(
#     *,
#     first_run_key: str,
#     replay_artifacts: dict,
#     validation_result: dict,
#     pin_set: dict,
#     enable_m7_replay: bool = True,
#     runner: ReplayRunnerProtocol | None = None,
#     determinism_key_fn: Callable[[dict, dict], str] | None = None,
# ) -> dict:
#     ...
#
# Output dict keys MUST match SMART SPEC output_contract.


class ReplayRunnerProtocol(Protocol):
    def run(self, *, command: str, working_directory: str, timeout_s: int) -> Dict[str, Any]:
        """Return: {'ok': bool, 'exit_code': int, 'stdout': str, 'stderr': str, 'duration_ms': int}"""


@dataclass(frozen=True)
class FakeRunResult:
    ok: bool
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 1


class FakeRunner:
    def __init__(self, result: FakeRunResult):
        self._result = result
        self.calls: list[dict[str, Any]] = []

    def run(self, *, command: str, working_directory: str, timeout_s: int) -> Dict[str, Any]:
        self.calls.append(
            {"command": command, "working_directory": working_directory, "timeout_s": timeout_s}
        )
        return {
            "ok": self._result.ok,
            "exit_code": self._result.exit_code,
            "stdout": self._result.stdout,
            "stderr": self._result.stderr,
            "duration_ms": self._result.duration_ms,
        }


def _sha256(s: str) -> str:
    import hashlib
    return "sha256:" + hashlib.sha256(s.encode("utf-8")).hexdigest()


def fake_determinism_key_fn(runtime_payload: dict, policy_digests: dict) -> str:
    """
    SSOT test double:
    - MUST incorporate policy_digests into key
    - MUST be stable for same payload+policy
    """
    import json

    blob = json.dumps(
        {"payload": runtime_payload, "policy": policy_digests},
        sort_keys=True,
        separators=(",", ":"),
    )
    return _sha256(blob)


@pytest.fixture()
def base_pin_set() -> dict:
    # Minimal pin set for tests (SSOT expects completeness checks in real impl)
    return {
        "kami_version": "v2.0.1",
        "dna_version": "v2.1-patched-ai3-ai2",
        "smart_spec_version": "stage2-v1.0-patched",
        "reason_codes_version": "v1",
        "context_gate_version": "v1",
        "noise_budget_version": "v1",
        "toolchain_digest": "py311:deps-lock:abc",
        "determinism_policy_version": "v1",
    }


@pytest.fixture()
def base_validation_result() -> dict:
    return {
        "repo_verdict": "PASS_ALLOWED",  # upstream may still clamp by context gate
        "context_gate": {"level": "L3"},
        "reasons": [],
    }


@pytest.fixture()
def base_policy_digests() -> dict:
    return {
        "reason_codes_sha256": "rc:111",
        "context_gate_sha256": "cg:222",
        "noise_budget_sha256": "nb:333",
    }


@pytest.fixture()
def base_artifacts(base_policy_digests: dict) -> dict:
    return {
        "test_command": "pytest -q",
        "working_directory": ".",
        "timeout_s": 30,
        # This is the canonical runtime payload Stage2 would use for determinism_key
        "pytest_runtime_payload": {"tests": [{"name": "test_ok", "status": "PASSED"}]},
        "toolchain_manifest_digest": "py311:deps-lock:abc",
        "policy_digests": base_policy_digests,
    }


def _import_sut():
    # The module name is a SSOT choice for M7 implementation.
    # AIEL-0 must create this module to satisfy tests.
    import importlib
    return importlib.import_module("module7_runtime_replay")


# ----------------------------
# 1) deterministic_pass
# ----------------------------
def test_1_deterministic_pass(base_artifacts, base_validation_result, base_pin_set):
    sut = _import_sut()

    runner = FakeRunner(FakeRunResult(ok=True, exit_code=0))
    first_key = fake_determinism_key_fn(
        base_artifacts["pytest_runtime_payload"], base_artifacts["policy_digests"]
    )

    out = sut.verify_runtime_replay(
        first_run_key=first_key,
        replay_artifacts=base_artifacts,
        validation_result=base_validation_result,
        pin_set=base_pin_set,
        enable_m7_replay=True,
        runner=runner,
        determinism_key_fn=fake_determinism_key_fn,
    )

    assert out["replay_verified"] is True
    assert out["reason_code"] is None
    assert out["determinism_key_first"] == first_key
    assert out["determinism_key_replay"] == first_key
    assert out["evidence"]["replay_command"] == "pytest -q"
    assert runner.calls, "Runner must be called exactly once"


# ----------------------------
# 2) uuid_nondet_fail
# ----------------------------
def test_2_uuid_fail(base_artifacts, base_validation_result, base_pin_set):
    sut = _import_sut()

    runner = FakeRunner(FakeRunResult(ok=True, exit_code=0))

    first_key = fake_determinism_key_fn(
        {"tests": [{"name": "test_uuid", "status": "PASSED", "uuid": "A"}]},
        base_artifacts["policy_digests"],
    )
    # Replay payload differs (uuid changes)
    replay_artifacts = dict(base_artifacts)
    replay_artifacts["pytest_runtime_payload"] = {
        "tests": [{"name": "test_uuid", "status": "PASSED", "uuid": "B"}]
    }

    out = sut.verify_runtime_replay(
        first_run_key=first_key,
        replay_artifacts=replay_artifacts,
        validation_result=base_validation_result,
        pin_set=base_pin_set,
        enable_m7_replay=True,
        runner=runner,
        determinism_key_fn=fake_determinism_key_fn,
    )

    assert out["replay_verified"] is False
    assert out["reason_code"] == "M7_REPLAY_FAIL"
    assert out["determinism_key_replay"] != out["determinism_key_first"]


# ----------------------------
# 3) time_nondet_fail
# ----------------------------
def test_3_time_fail(base_artifacts, base_validation_result, base_pin_set):
    sut = _import_sut()

    runner = FakeRunner(FakeRunResult(ok=True, exit_code=0))

    first_key = fake_determinism_key_fn(
        {"tests": [{"name": "test_time", "status": "PASSED", "t": 1}]},
        base_artifacts["policy_digests"],
    )
    replay_artifacts = dict(base_artifacts)
    replay_artifacts["pytest_runtime_payload"] = {
        "tests": [{"name": "test_time", "status": "PASSED", "t": 2}]
    }

    out = sut.verify_runtime_replay(
        first_run_key=first_key,
        replay_artifacts=replay_artifacts,
        validation_result=base_validation_result,
        pin_set=base_pin_set,
        enable_m7_replay=True,
        runner=runner,
        determinism_key_fn=fake_determinism_key_fn,
    )

    assert out["replay_verified"] is False
    assert out["reason_code"] == "M7_REPLAY_FAIL"


# ----------------------------
# 4) random_nondet_fail
# ----------------------------
def test_4_random_fail(base_artifacts, base_validation_result, base_pin_set):
    sut = _import_sut()

    runner = FakeRunner(FakeRunResult(ok=True, exit_code=0))

    first_key = fake_determinism_key_fn(
        {"tests": [{"name": "test_rand", "status": "PASSED", "r": 0.1}]},
        base_artifacts["policy_digests"],
    )
    replay_artifacts = dict(base_artifacts)
    replay_artifacts["pytest_runtime_payload"] = {
        "tests": [{"name": "test_rand", "status": "PASSED", "r": 0.9}]
    }

    out = sut.verify_runtime_replay(
        first_run_key=first_key,
        replay_artifacts=replay_artifacts,
        validation_result=base_validation_result,
        pin_set=base_pin_set,
        enable_m7_replay=True,
        runner=runner,
        determinism_key_fn=fake_determinism_key_fn,
    )

    assert out["replay_verified"] is False
    assert out["reason_code"] == "M7_REPLAY_FAIL"


# ----------------------------
# 5) artifacts_missing
# ----------------------------
def test_5_artifacts_missing(base_validation_result, base_pin_set):
    sut = _import_sut()

    out = sut.verify_runtime_replay(
        first_run_key="sha256:" + "0" * 64,
        replay_artifacts={"test_command": "pytest -q"},  # missing required fields
        validation_result=base_validation_result,
        pin_set=base_pin_set,
        enable_m7_replay=True,
        runner=FakeRunner(FakeRunResult(ok=True)),
        determinism_key_fn=fake_determinism_key_fn,
    )

    assert out["replay_verified"] is False
    assert out["reason_code"] == "M7_ARTIFACTS_MISSING"
    assert out["determinism_key_replay"] is None


# ----------------------------
# 6) replay_crash_error
# ----------------------------
def test_6_replay_crash_error(base_artifacts, base_validation_result, base_pin_set):
    sut = _import_sut()

    runner = FakeRunner(FakeRunResult(ok=False, exit_code=124, stderr="timeout"))

    first_key = fake_determinism_key_fn(
        base_artifacts["pytest_runtime_payload"], base_artifacts["policy_digests"]
    )

    out = sut.verify_runtime_replay(
        first_run_key=first_key,
        replay_artifacts=base_artifacts,
        validation_result=base_validation_result,
        pin_set=base_pin_set,
        enable_m7_replay=True,
        runner=runner,
        determinism_key_fn=fake_determinism_key_fn,
    )

    assert out["replay_verified"] is False
    assert out["reason_code"] == "M7_REPLAY_ERROR"
    assert out["determinism_key_replay"] is None


# ----------------------------
# 7) policy_tamper_changes_key (AI-3)
# ----------------------------
def test_7_policy_tamper_changes_key(base_artifacts, base_validation_result, base_pin_set):
    sut = _import_sut()

    runner = FakeRunner(FakeRunResult(ok=True, exit_code=0))

    # baseline policy
    first_key = fake_determinism_key_fn(
        base_artifacts["pytest_runtime_payload"], base_artifacts["policy_digests"]
    )

    # tampered policy (1-line change equivalent)
    tampered = dict(base_artifacts)
    tampered_policy = dict(base_artifacts["policy_digests"])
    tampered_policy["context_gate_sha256"] = "cg:CHANGED"
    tampered["policy_digests"] = tampered_policy

    out = sut.verify_runtime_replay(
        first_run_key=first_key,
        replay_artifacts=tampered,
        validation_result=base_validation_result,
        pin_set=base_pin_set,
        enable_m7_replay=True,
        runner=runner,
        determinism_key_fn=fake_determinism_key_fn,
    )

    # In policy tamper scenario, replay_key must differ because policy digests are included
    assert out["determinism_key_replay"] != out["determinism_key_first"]
    # This mismatch is evidence; verdict semantics are decided upstream.
    assert out["replay_verified"] is False
    assert out["reason_code"] == "M7_REPLAY_FAIL"
