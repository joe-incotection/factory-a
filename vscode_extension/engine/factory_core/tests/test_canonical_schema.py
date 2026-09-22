from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PYDANTIC_DIR = ROOT / "pydantic_layer"


@pytest.mark.order(1)
def test_01_import_generator():
    mod = importlib.import_module("pydantic_layer.generate_canonical_schema")
    assert hasattr(mod, "main")


@pytest.mark.order(2)
def test_02_generate_schema_file(tmp_path):
    # run generator and ensure file is created
    mod = importlib.import_module("pydantic_layer.generate_canonical_schema")
    mod.main()
    out = PYDANTIC_DIR / "canonical_schema.py"
    assert out.exists()
    txt = out.read_text(encoding="utf-8")
    assert "AUTO-GENERATED" in txt
    assert "class Envelope" in txt


@pytest.mark.order(3)
def test_03_import_schema():
    importlib.invalidate_caches()
    mod = importlib.import_module("pydantic_layer.canonical_schema")
    assert hasattr(mod, "Envelope")


@pytest.mark.order(4)
def test_04_validate_happy_path():
    mod = importlib.import_module("pydantic_layer.canonical_schema")
    Envelope = getattr(mod, "Envelope")
    obj = {
        "meta": {
            "envelope_version": "v1.0",
            "message_id": "m1",
            "determinism_key": "d1",
            "producer_module": "vip_policy_gate",
            "produced_at_utc": "2026-03-08T00:00:00Z"
        },
        "payload": {
            "evidence": {"evidence_complete": True, "trust_score": 0.9},
            "decision": {"router_action": "EXECUTE", "decision_hash": "sha256:abc", "context_hash_seed": "seed"}
        },
        "reason_codes": ["VIP_POLICY_ATTACHED"]
    }
    env = Envelope.model_validate(obj)
    assert env.meta.envelope_version == "v1.0"


@pytest.mark.order(5)
def test_05_reject_extra_keys():
    mod = importlib.import_module("pydantic_layer.canonical_schema")
    Envelope = getattr(mod, "Envelope")
    obj = {
        "meta": {
            "envelope_version": "v1.0",
            "message_id": "m1",
            "determinism_key": "d1",
            "producer_module": "vip_policy_gate",
            "produced_at_utc": "2026-03-08T00:00:00Z",
            "extra": "nope"
        },
        "payload": {},
        "reason_codes": []
    }
    with pytest.raises(Exception):
        Envelope.model_validate(obj)


@pytest.mark.order(6)
def test_06_reject_wrong_type():
    mod = importlib.import_module("pydantic_layer.canonical_schema")
    Envelope = getattr(mod, "Envelope")
    obj = {
        "meta": {
            "envelope_version": "v1.0",
            "message_id": "m1",
            "determinism_key": "d1",
            "producer_module": "vip_policy_gate",
            "produced_at_utc": "2026-03-08T00:00:00Z"
        },
        "payload": {"evidence": {"trust_score": "bad"}},
        "reason_codes": []
    }
    with pytest.raises(Exception):
        Envelope.model_validate(obj)


@pytest.mark.order(7)
def test_07_reason_codes_list_strings():
    mod = importlib.import_module("pydantic_layer.canonical_schema")
    Envelope = getattr(mod, "Envelope")
    obj = {
        "meta": {
            "envelope_version": "v1.0",
            "message_id": "m1",
            "determinism_key": "d1",
            "producer_module": "vip_policy_gate",
            "produced_at_utc": "2026-03-08T00:00:00Z"
        },
        "payload": {},
        "reason_codes": [1, 2]  # invalid
    }
    with pytest.raises(Exception):
        Envelope.model_validate(obj)
