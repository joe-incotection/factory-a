# WF-1_FACTORY_BUILD_RULES_v1

## STEP 0 (MANDATORY)
Before writing/accepting any GOLDEN_IO_LOCK:
- Cross-check every referenced field against CANONICAL_FIELDS_CORE_v1.yaml
- If missing: add to CANONICAL_FIELDS_CORE first (with justification + version bump), then proceed

## Gate 0 (SSA) — Canonical Compliance
BLOCK if:
- any GOLDEN_IO_LOCK field not in CANONICAL_FIELDS_CORE (or declared extension)
- any module reason code not in REASON_CODES_MASTER
- any output has extra keys beyond GOLDEN_IO_LOCK

## Gate 1 — Authority Boundary
BLOCK if authority overlaps (VIP stamp-only, Router sole decider, Guard terminal, Executor only execute).

## Gate 2 — Group Wiring Discipline
Integrate by groups (A–F). Fail => fix group-local only.
