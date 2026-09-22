"""generate_canonical_schema.py

Generates pydantic_layer/canonical_schema.py from:
  - CANONICAL_ENVELOPE_v1.yaml
  - CANONICAL_FIELDS_CORE_v1.yaml

Contract:
- Do NOT hand edit canonical_schema.py
- Re-run this generator when canonical YAML changes

Usage:
  python -m pydantic_layer.generate_canonical_schema

Notes:
- This is a lean generator. It enforces envelope sections + core typed blocks.
- Project-specific extension fields should be placed under payload.extensions.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict

try:
    import yaml  # type: ignore
except Exception as e:  # pragma: no cover
    raise RuntimeError("PyYAML is required to run this generator: pip install pyyaml") from e


ROOT = Path(__file__).resolve().parents[1]  # pack root
ENVELOPE_YAML = ROOT / "CANONICAL_ENVELOPE_v1.yaml"
FIELDS_YAML = ROOT / "CANONICAL_FIELDS_CORE_v1.yaml"
OUT = Path(__file__).resolve().parent / "canonical_schema.py"


def _read_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main() -> None:
    env = _read_yaml(ENVELOPE_YAML)
    fields = _read_yaml(FIELDS_YAML)

    # Minimal determinism key for generator output
    determinism_key = _sha256_text(f"{env.get('version')}|{fields.get('version')}")

    header = f'''"""canonical_schema.py (AUTO-GENERATED)

Source of truth:
  - {ENVELOPE_YAML.name}
  - {FIELDS_YAML.name}

generator_determinism_key: {determinism_key}

DO NOT EDIT MANUALLY.
"""\n
from __future__ import annotations\n
from typing import Any, Dict, List, Optional\n
from pydantic import BaseModel, Field, ConfigDict\n
'''

    # For now, emit a stable, opinionated model that matches the current v1 pack
    body = '''
class Meta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    envelope_version: str
    message_id: str
    determinism_key: str
    producer_module: str
    produced_at_utc: str


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_complete: Optional[bool] = None
    veto_signal: Optional[bool] = None
    noise_residual: Optional[List[float]] = None
    trust_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    detected_patterns: Optional[List[str]] = None


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    router_action: Optional[str] = Field(default=None, description="EXECUTE|HALT|BLOCK|SAFE_MODE|REDUCE_RISK")
    decision_hash: Optional[str] = None
    context_hash_seed: Optional[str] = None


class RiskState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_drawdown: Optional[float] = None
    exposure: Optional[float] = None
    kill_switch: Optional[bool] = None
    trust_critical_state: Optional[bool] = None
    hard_broker_safety_limits: Optional[bool] = None


class Stamps(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vip_stamps: Optional[List[str]] = None


class Features(BaseModel):
    model_config = ConfigDict(extra="forbid")
    features_12: Optional[Dict[str, Any]] = None


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context: Optional[Dict[str, Any]] = None
    evidence: Optional[Evidence] = None
    features: Optional[Features] = None
    decision: Optional[Decision] = None
    risk_state: Optional[RiskState] = None
    stamps: Optional[Stamps] = None
    extensions: Optional[Dict[str, Any]] = None


class Envelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meta: Meta
    payload: Payload
    reason_codes: List[str]
'''

    OUT.write_text(header + body.lstrip(), encoding="utf-8")


if __name__ == "__main__":
    main()
