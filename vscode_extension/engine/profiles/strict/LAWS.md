# SMART_SPEC Laws block — profile: STRICT (pure-logic / high-assurance)
Paste into a module SMART_SPEC §1 Laws:

1. Schema = Law — follow GOLDEN_IO_LOCK exactly.
2. Reason codes allowlist only — from the module's REASON_CODES yaml.
3. Determinism required (HARD_FAIL) — core logic MUST NOT read wall clock,
   network, randomness, or machine state. Same input -> bit-stable canonical
   JSON. Forbidden: time.time(), datetime.now(), random, env inspection.
4. No silent pass — no PASS without evidence.

Use STRICT for pure computation / safety-critical modules (e.g. the SAFE_STATS
example). Use GENERAL for app code that legitimately needs I/O.
