# M8_REPLAY_GATE_CHECKLIST_v1.2b — Gate A + Gate B + Gate C (Unified)
Version: v1.2b  
Scope: **Gates layer** (Code execution) — used after **AIEL-T** + **Integration** and before **PASS → Golden Lib**  
Flow placement (current): `Code → AIEL-T → Integration → Gates(M8/M7/Stage2) → PASS`

---

## What this file is (and what it is NOT)
- **This is a checklist + hard-lock contract** for replayability and audit authority.
- **This is NOT** the full M8 master spec, and **NOT** the Stage2 (M1–M6) authority spec.
- Use it to implement **M8 gate logic** and **tests** that must be true for every module run.

---

## Inputs / Outputs (minimal)
### Inputs (from execution context)
- `window_payload` (the exact window used in the run)
- `trinity_m1_output` (evidence producer output; or equivalent sensor output)
- `router_decision` (final decision/action)
- `parameter_snapshot` (all runtime/manual params used in this run)
- `toolchain_manifest` (env + versions; required by Stage2/M7)

### Outputs (artifacts emitted by Gates)
- `evidence_log` (append-only): includes canonical payload + hashes
- `decision_receipt` (one-per decision): deterministic, allowlist-only
- `replay_report` (PASS/FAIL with reason codes)

---

# 🔒 Gate A — Evidence Presence & Shape (Noise must exist)
**Goal:** Kill “silent failure” by requiring mandatory evidence fields.

## A.1 Mandatory outputs from Trinity Module 1 (EVIDENCE_ONLY)
- [ ] `cleaned_signal` (len == window_size)
- [ ] `noise_residual` (len == window_size) ✅ **MUST KEEP**
- [ ] `broker_audit.trust_score`, `broker_audit.trust_state`
- [ ] `evidence_ref.segment_hash` (or `segment_hash` at top-level if normalized)

## A.2 Hard locks (Fail fast)
Gate A FAIL if any is true:
- [ ] `noise_residual == null`
- [ ] `len(noise_residual) == 0`
- [ ] `len(noise_residual) != window_size`
- [ ] `truth_*` fields leak into `cleaned_signal` / `noise_residual` (see Gate A.3)

**Action on FAIL:** `HARD_FAIL_BLOCK`  
**Reason code:** `RC_NOISE_RESIDUAL_MISSING` or `RC_WINDOW_MISMATCH`

## A.3 Truth contamination (must be isolated)
- [ ] Truth fields (future/ground-truth) **MUST NOT** be used to compute:
  - `cleaned_signal`
  - `noise_residual`
  - `segment_hash`
- [ ] Truth is allowed only for:
  - compare/audit dashboards
  - post-run evaluation reports

**Action on FAIL:** `HARD_FAIL_BLOCK`  
**Reason code:** `RC_TRUTH_CONTAMINATION`

---

# 🔒 Gate B — Canonical Segment Hash (Rehash must match 100%)
**Goal:** Ensure the evidence is reproducible bit-for-bit (within canonical rules).

## B.1 Canonical Hash Payload (LOCK BEFORE TESTS)
- [ ] `segment_hash` MUST be computed from **Canonical Residual Segment v1** only (no guessing).
- [ ] MUST persist `(segment_hash, canonical_payload)` in `evidence_log` **every cycle** (or every decision).

## B.2 Canonical Residual Segment v1 (Minimal + deterministic)
**Include**
- [ ] `symbol`, `timeframe`, `window_size`
- [ ] `timestamps_utc[]` (same length as window)
- [ ] `noise_residual.residual_close[]` *(or the primary residual vector defined in schema)*
- [ ] optional: `broker_audit.trust_score`, `broker_audit.trust_state` *(only if locked as numeric/string rules; otherwise exclude)*

**Exclude**
- [ ] all truth data (anything that can leak “future”)
- [ ] non-deterministic runtime fields (timestamps “now”, random seeds, UUID unless deterministic)

**Canonicalization rules**
- [ ] JSON `sort_keys=true`
- [ ] fixed float rounding (e.g. 6 decimals) **everywhere**
- [ ] NaN/null normalization: choose **one rule** and lock it (e.g. NaN → null)
- [ ] arrays must preserve order; no set/dict ordering

## B.3 Replay test (hard requirement)
- [ ] `rehash(canonical_payload) == segment_hash` must hold 100%  
- [ ] Run twice in the same environment: must match 100%  
- [ ] Optional cross-env check: if toolchain manifest is identical, must still match 100%

**Action on FAIL:** `HARD_FAIL_BLOCK`  
**Reason code:** `RC_REPLAY_HASH_MISMATCH` *(or the locked code used in your ReasonCodes set)*

---

# 🔒 Gate C — Decision Receipt (Audit-grade, allowlist-only)
**Goal:** Every decision must carry a deterministic “receipt” that links:
decision → reasons → parameter snapshot → evidence set → replay hint.

## C.1 Where Gate C sits in the flow
Gate C is evaluated inside **Gates** stage **after** a decision exists and **before** PASS:
`Code run → produces router_decision → M8 builds decision_receipt → Gate C validates receipt → (then) M7 replay verify`

In the pipeline wording:
`Code → AIEL-T → Integration → Gates(M8: A+B+C) → M7 replay → Stage2 authority → PASS`

*(You can swap M7/Stage2 order as long as receipts + hashes are already emitted before replay.)*

## C.2 Mandatory Decision Receipt fields (Spare I/O v1)
Receipt must include these 8 fields (read-only / additive-safe):
- [ ] `correlation_id`
- [ ] `context_hash`
- [ ] `decision_id`
- [ ] `decision` = `EXECUTE|HOLD|CANCEL` (allowlist only)
- [ ] `reason_codes[]` (allowlist only; no free-text)
- [ ] `parameters_hash` (hash of the exact parameter snapshot used)
- [ ] `evidence_set_hash` (hash linking the evidence set, e.g. segment_hash + related evidence refs)
- [ ] `replay_hint` (e.g. `{toolchain_manifest_digest, determinism_key}` or a stable pointer)

## C.3 Receipt determinism rules
- [ ] `decision_id` must be deterministic (e.g. hash of `(correlation_id + context_hash + evidence_set_hash + decision + reason_codes + parameters_hash)`).
- [ ] `reason_codes[]` must be sorted in a canonical order.
- [ ] unknown fields must be ignored safely (additive-only rule).

## C.4 Hard locks
Gate C FAIL if any is true:
- [ ] `decision` not in allowlist
- [ ] any `reason_code` not in allowlist
- [ ] missing `parameters_hash` OR missing `evidence_set_hash`
- [ ] `parameters_hash` does not match the persisted `parameter_snapshot`
- [ ] `evidence_set_hash` does not match persisted evidence refs (at minimum includes `segment_hash`)
- [ ] `decision_receipt` differs between replay runs when inputs+toolchain are identical

**Action on FAIL:** `HARD_FAIL_BLOCK`  
**Reason codes (examples):** `RC_REASON_CODE_UNKNOWN`, `RC_DECISION_RECEIPT_INVALID`, `RC_PARAM_HASH_MISMATCH`

---

# ✅ Parameter Governance (must be locked before scaling)
This is the minimal governance needed so “runtime knobs” don’t destroy determinism.

## 10-Line Checklist (LOCK)
1. **Lock Principle:** ห้าม auto-tune real-time (log → lab → human approve → spec เท่านั้น)  
2. **Param Schema (mandatory):** ทุก param ต้องมี `param_id, owner_module, range, default, change_mode(LAB_ONLY|RUNTIME_MANUAL|LOCKED)`  
3. **Owners Only (4 groups):** อนุญาต param เฉพาะ Router / Risk / Execution / Sensors; โมดูลอื่น = LOCKED  
4. **Decision Must Carry Hash:** ทุก decision/event ต้องมี `parameters_hash` (hash ของ param snapshot ที่ใช้จริง)  
5. **Spare I/O Exists (optional):** เตรียม “ช่อง read-only” 8 fields ใน struct/schema (ยังไม่ต้องใช้งาน)  
6. **Spare I/O 8 Fields:** `correlation_id, context_hash, decision_id, decision(EXECUTE|HOLD|CANCEL), reason_codes[], parameters_hash, evidence_set_hash, replay_hint`  
7. **No Free-Text:** `decision` และ `reason_codes` ต้องเป็น allowlist เท่านั้น  
8. **Additive-Only Rule:** เพิ่ม field ได้ แต่ห้าม breaking change Golden I/O (unknown fields ต้อง ignore-safe)  
9. **Snapshot Timing (not implemented yet):** ตอนนี้แค่ “มีที่อยู่” ให้พร้อม; 3-anchor/mini_snapshot ทำทีหลัง  
10. **Minimum Done Definition:** ถ้า code compile + schema มี fields + param metadata ถูกบังคับใช้ = “DONE”  

---

## Implementation notes (for Claude / implementers)
- Implement Gate A/B/C as **separate functions** but **one gate result object**:
  - `gate_result = {status, action, reason_codes[], evidence_refs, hashes, receipt}`
- Make Gate failures **hard fail** (no degraded mode).
- Keep all emitted artifacts **append-only** to support audit and replay.

---

## PASS / FAIL summary
PASS only when:
- Gate A: mandatory evidence exists, correct shape, no truth contamination
- Gate B: canonical payload persisted + hash reproducible 100%
- Gate C: decision receipt complete + allowlist-only + hashes match snapshots + receipt replayable

FAIL when:
- evidence missing/empty/len mismatch
- hash mismatch or canonicalization drift
- decision receipt invalid or not reproducible
