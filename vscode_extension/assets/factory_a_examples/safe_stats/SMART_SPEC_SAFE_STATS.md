# SMART_SPEC_SAFE_STATS.md
Version: v1.0
Module: SAFE_STATS

## 0) Purpose (SSOT)
SAFE_STATS converts a numeric series into a **deterministic summary** (count, sum, mean, min, max).
This module is a **pure computation + audit producer**; it performs no I/O and makes no decisions.

## 1) Laws (Non-Negotiables)
1. **Schema = Law**
   MUST follow `GOLDEN_IO_LOCK_SAFE_STATS.yaml` exactly for input/output.
2. **Reason codes allowlist only**
   Error/degrade reasons MUST be chosen ONLY from `SAFE_STATS_REASON_CODES.yaml`.
3. **Determinism required**
   Same input payload MUST produce bit-stable canonical JSON (see §5).
4. **No hidden I/O**
   No network calls. No reading machine state. No wall-clock usage in core logic.

## 2) Public API (for implementation)
Implement exactly one entry function:

- `safe_stats.engine.run_safe_stats(input_payload: dict) -> dict`

### Error handling contract
On **hard fail**, the function MUST raise `SafeStatsError` (from `safe_stats.exceptions`) with:
- `reason_codes: list[str]` (allowlist only)
- `message: str` (human readable; NOT used for policy)
The caller (AIEL-T / pipeline runner) is responsible for capturing errors into evidence.

This module has no soft-degrade path: input is either valid (NORMAL) or hard-fails.

## 3) Input Contract
Source of truth: `GOLDEN_IO_LOCK_SAFE_STATS.yaml` -> `input_contract`.

Key requirements (summary):
- required top fields: `values`, `meta`
- `values` MUST be a non-empty array of finite numbers (min 1 item)
- `meta` MUST contain `run_id`

## 4) Output Contract
Source of truth: `GOLDEN_IO_LOCK_SAFE_STATS.yaml` -> `output_contract`.

Key requirements (summary):
Top required fields:
- `summary` (count, sum, mean, min, max)
- `metadata` (audit_quality)

## 5) Determinism & Canonicalization
Canonical JSON rules (from `GOLDEN_IO_LOCK_SAFE_STATS.yaml`):
- sort_keys = true
- float precision = 6 decimals (round at canonicalization boundary)
- NaN / Infinity not allowed

Hashing:
- sha256 over canonical JSON UTF-8 bytes
- used by AIEL-T evidence & Gate C receipt

Forbidden:
- `time.time()`, `datetime.now()`, random seeds, non-deterministic iteration order.

## 6) Invariants (additional, testable)
Source of truth: `INVARIANTS_SAFE_STATS.yaml`.

Implementation MUST satisfy all invariants and the golden tests.

## 7) Golden Tests
Source of truth: `test_golden_safe_stats.py`.

Requirement:
- MUST pass 7/7 tests in a human-run environment (AIEL-T).
- AI must not claim runtime results.

## 8) Files in the module pack
- `GOLDEN_IO_LOCK_SAFE_STATS.yaml` (I/O law)
- `SAFE_STATS_REASON_CODES.yaml` (allowlist)
- `INVARIANTS_SAFE_STATS.yaml` (extra invariants)
- `test_golden_safe_stats.py` (golden tests)
- KAMI / DNA bridges: reuse project-level shared files (not module-specific for this small module)
