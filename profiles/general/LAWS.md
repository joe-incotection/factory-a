# SMART_SPEC Laws block — profile: GENERAL (default, for real-world apps)
Paste into a module SMART_SPEC §1 Laws:

1. Schema = Law — follow GOLDEN_IO_LOCK exactly.
2. Reason codes allowlist only — from the module's REASON_CODES yaml.
3. Test determinism — golden tests MUST be deterministic and replayable
   (same inputs -> same test outcome). The CODE MAY use network/time/random
   where the spec allows; isolate it behind seams so tests stay deterministic
   (inject clock/rng, mock I/O).
4. No silent pass — no PASS without evidence.

NOTE: GENERAL does NOT forbid network/time/randomness in the code — most real
software needs them. It only requires the TESTS to be deterministic.
