# DNA_SYSTEM_GUIDE_pythonbrain2026_trinity_m1_v2_1.md
Version: v2.1 (module-scoped)
Applies to: TRINITY_M1 only

## 1) Objective
TRINITY_M1 converts raw bar stream into **clean, audited features** with:
- deterministic transforms (Fourier/Kalman/Jacobian)
- evidence-first outputs (evidence_log[] MUST exist on successful emit)
- explicit degrade vs hard-fail behavior

## 2) Non-Negotiables
- **Schema = Law**: follow `GOLDEN_IO_LOCK_TRINITY_M1.yaml` exactly.
- **Reason codes allowlist only**: use `TRINITY_M1_REASON_CODES.yaml`.
- **Determinism**: same input → bit-stable canonical json → same hashes.
- **No hidden I/O**: no network calls; no reading local machine state.

## 3) Minimal Code Layout
Recommended (you can rename files, but keep responsibilities):
- `engine.py` — single entry `run_trinity_m1(input_payload) -> output_payload`
- `fourier.py` — spectral features (pure functions)
- `kalman.py` — state update (pure-ish; state only from inputs)
- `jacobian.py` — residual / coupling helpers (pure functions)
- `models.py` — pydantic models (optional) or typed dict contracts
- `exceptions.py` — typed exceptions mapped to reason codes
- `audit.py` — build broker_audit + evidence_log records

## 4) Evidence Logging (When it is used)
Evidence logging is **output data**, not runtime logging.
It is emitted:
- on every successful run (min 1 record) OR
- at least one record per detected pattern (per module spec)

If no pattern is detected, emit a single record:
- pattern_name = "NONE"
- confidence_0_1 = 0.0
- evidence_strength = 0.0
- raw_refs.segment_hash set from input

## 5) Fail / Degrade
- **Hard fail**: do not emit to Router/EQL (return error object for caller) + log reason_codes.
- **Soft degrade**: still emit output, but set `metadata.audit_quality="DEGRADED"` and include reason_codes like `TRINITY_M1_AUDIT_DEGRADED`.

## 6) Determinism Notes
- floating ops: round only at canonicalization boundary (not inside math)
- canonical json: sort keys + float precision 6
- avoid `time.time()` and random seeds in core

## 7) What AIEL-T should capture
AIEL-T evidence should include at minimum:
- toolchain manifest (python version, deps)
- golden test command + results
- canonical output hash of TRINITY_M1 output (post-canonicalization)
