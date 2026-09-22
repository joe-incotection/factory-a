# SMART_SPEC_TRINITY_M1.md
Version: v1.0
Module: TRINITY_M1

## 0) Purpose (SSOT)
TRINITY_M1 converts a raw OHLCV bar stream into **clean, audited features** for downstream modules.
This module is a **feature generator + audit producer**; it does not make trade decisions.

## 1) Laws (Non‑Negotiables)
1. **Schema = Law**  
   MUST follow `GOLDEN_IO_LOCK_TRINITY_M1.yaml` exactly for input/output.
2. **Reason codes allowlist only**  
   Error/degrade reasons MUST be chosen ONLY from `TRINITY_M1_REASON_CODES.yaml`.
3. **Determinism required**  
   Same input payload MUST produce bit‑stable canonical JSON (see §5).
4. **No hidden I/O**  
   No network calls. No reading machine state. No wall‑clock usage in core logic.

## 2) Public API (for implementation)
Implement exactly one entry function:

- `trinity_m1.engine.run_trinity_m1(input_payload: dict) -> dict`

### Error handling contract
On **hard fail**, the function MUST raise `TrinityM1Error` (from `trinity_m1.exceptions`) with:
- `reason_codes: list[str]` (allowlist only)
- `message: str` (human readable; NOT used for policy)
The caller (AIEL‑T / pipeline runner) is responsible for capturing errors into evidence.

On **soft degrade**, the function MUST return a normal output payload, but:
- `metadata.audit_quality` MUST be `"DEGRADED"`
- include a degrade reason code such as `TRINITY_M1_AUDIT_DEGRADED` (if present in allowlist)

## 3) Input Contract
Source of truth: `GOLDEN_IO_LOCK_TRINITY_M1.yaml` → `input_contract`.

Key requirements (summary):
- required top fields: `symbol`, `timeframe`, `bars`, `meta`
- `bars` MUST contain at least 256 items
- each bar MUST contain: `ts_utc`, `o`, `h`, `l`, `c`, `v`

## 4) Output Contract
Source of truth: `GOLDEN_IO_LOCK_TRINITY_M1.yaml` → `output_contract`.

Key requirements (summary):
Top required fields:
- `cleaned_structure_signal`
- `noise_residual`
- `spectral_signature`
- `broker_audit`
- `metadata`

### Evidence logging (DATA, not runtime logging)
`broker_audit.evidence_log[]` MUST exist on every successful run:
- MUST contain at least 1 record
- If no pattern detected, MUST emit one record with:
  - `pattern_name = "NONE"`
  - `confidence_0_1 = 0.0`
  - `evidence_strength = 0.0`

## 5) Determinism & Canonicalization
Canonical JSON rules (from `GOLDEN_IO_LOCK_TRINITY_M1.yaml` + KAMI bridge):
- sort_keys = true
- float precision = 6 decimals (round at canonicalization boundary)
- NaN not allowed

Hashing:
- sha256 over canonical JSON UTF‑8 bytes
- used by AIEL‑T evidence & Gate C receipt

Forbidden:
- `time.time()`, `datetime.now()`, random seeds, non‑deterministic iteration order.

## 6) Invariants (additional, testable)
Source of truth: `INVARIANTS_TRINITY_M1.yaml`.

Implementation MUST satisfy all invariants and the golden tests.

## 7) Golden Tests
Source of truth: `tests/trinity_m1/test_golden_trinity_m1.py`.

Requirement:
- MUST pass 7/7 tests in a human‑run environment.

## 8) Files in the module pack
- `GOLDEN_IO_LOCK_TRINITY_M1.yaml` (I/O law)
- `TRINITY_M1_REASON_CODES.yaml` (allowlist)
- `INVARIANTS_TRINITY_M1.yaml` (extra invariants)
- `kami_complete_pythonbrain2026_trinity_m1_bridge.yaml` (style/determinism/test policy)
- `DNA_SYSTEM_GUIDE_pythonbrain2026_trinity_m1_v2_1.md` (implementation constraints)
- `tests/trinity_m1/test_golden_trinity_m1.py` (golden tests)
