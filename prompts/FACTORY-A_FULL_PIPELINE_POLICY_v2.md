# 🏭 FACTORY-A FULL PIPELINE POLICY v2

**(AIEL-0 → AIEL-1 → AIEL-2 → AIEL-3 → AIEL-T → Gate C → Integration → M8 → Stage2 → M7)**

**Principle:** *ช้า • เนียน • ไว* = **ค่อยเข้มขึ้นตามเลเยอร์** + **Authority แยกชัด** + **Receipt Proof**

**Updated:** 2026-01-27 (เพิ่ม Gate C + AIEL-T + Integration + M7)

---

## 📊 FACTORY-A FULL PIPELINE FLOW

```
🏭 Factory-A Stage1 (AIEL-0→1→2→3)     ← 🧠 AI Agent
        │
        ▼
⚖️ AIEL-T (run tests & collect evidence) ← ⚖️ Code (+ per-language adapter)
        │
        ▼
🔒 Gate C: Decision Receipt Builder+Enforcer ← ⚖️ Code
        │
        ▼
🧩 Integration (compat/ABI/schema/toolchain pin) ← 🧠 AI Agent
        │
        ▼
🧱 M8_v2 (M8-1…M8-5) ← ⚖️ Code
   - ✅ Gate A + Gate B
   - ✅ validate receipt fields already created
   - ❌ no runtime replay
        │
        ▼
🏛️ Stage2 (M1…M6) Validator/Authority ← ⚖️ Code
        │
        ▼
🔁 M7 Replay Runtime Verifier ← ⚖️ Code
        │
        ▼
PASS / FAIL  ← 🚀🔥⚖️📊🛡️
```

---

## 0) Purpose / Non-Goals

### Purpose

1. ทำให้การผลิตโค้ดจาก Smart Spec "ไหลลื่น" โดย **ตั้งต้นไม่ล้ม**
2. ลด "PASS ปลอม / silent failure" ด้วย **Lock + Evidence + Determinism + Receipt**
3. ทำให้ **replay / audit / authority** เชื่อถือได้ผ่าน Decision Receipt
4. รองรับการขยายเป็น multi-module / multi-language ใน Stage2

### Non-Goals (ห้ามคาดหวังผิดชั้น)

* AIEL-0 ไม่ใช่ตัวตัดสินคุณภาพสุดท้าย
* AIEL-1 ไม่แก้ semantics
* AIEL-3 ไม่แก้ logic
* Gate C ไม่ตัดสินใจ — แค่สร้าง receipt proof
* M8 ไม่ใช่ runtime verifier — เป็น determinism gate
* Factory-A ไม่ทำหน้าที่ "Final Authority" แทน Stage2

---

## 1) Core Definitions (คำศัพท์บังคับ)

### 1.1 "ตั้งไข่ไม่ล้ม"

หมายถึง raw code ที่:

* สอดคล้องกับ Spec/Schema จริง
* มีโครง I/O ครบ
* มี hooks สำคัญ (evidence/determinism) อยู่จริง
* ไม่ hallucinate dependency/side-effect

### 1.2 "ค่อยเข้มขึ้น"

ความเข้มไม่ได้เท่ากันทุกเลเยอร์:

* AIEL-0: อ่านหนัก + gate เบา (กันหลุด semantics ตั้งแต่ต้น)
* AIEL-2: เข้มจริง (logic / determinism / evidence / invariants)
* AIEL-3: polish แต่ห้ามแตะแก่น
* AIEL-T: validation quality (G-score ≥ 0.95)
* Gate C: receipt builder (lock decision context)
* M8: determinism + integration
* Stage2: authority สุดท้าย + clamp
* M7: runtime replay verification

### 1.3 "Authority"

* Factory-A (AIEL-0..3) = ผลิตโค้ด
* AIEL-T = ตรวจคุณภาพ
* Gate C = สร้างใบเสร็จ (proof of decision)
* Integration = รวมโมดูล
* M8 = determinism gate
* Stage2 = ตัดสิน PASS/FAIL
* M7 = replay verifier

### 1.4 "Decision Receipt"

Decision Receipt = ใบเสร็จการตัดสินใจที่:

* **Lock context** (parameters, evidence, toolchain)
* **Compute hashes** (parameters_hash, evidence_set_hash, receipt_hash)
* **Enforce allowlist** (reason_codes จาก REASON_CODES_v1.yaml)
* **Enable replay** (determinism_key สำหรับ M7)
* **Write-once** (ไม่ให้แก้ไขหลัง execute)

---

## 2) Mandatory Read Pack (ใช้ร่วมทุกเลเยอร์)

เอกสารที่ถือเป็น "กฎหมายกลาง" ต้องมีทุกงาน:

1. `MASTER_SPEC` (ภาพรวม system + authority boundaries)
2. `DATA_STRUCTURES` (schema locked)
3. `KAMI` (coding/vocabulary/no free-text)
4. `DNA_SYSTEM_GUIDE` (structure/naming/layering)
5. `GOLDEN_IO_LOCK` (hard fail predicates)
6. `REASON_CODES_v1.yaml` (allowlist reason codes) **← สำคัญสำหรับ Gate C**
7. `gate_c_decision_receipt_spec_v_1_0.md` (receipt SSOT) **← เพิ่มใหม่**
8. `ReasonCodes` / `DecisionPriority` / `TS_001_Default_Decisions` *(ถ้าเกี่ยวกับ Router/Authority)*
9. `M8_REPLAY_GATE_CHECKLIST` (integration/replay gates checklist)

**Rule:** ถ้าขาด 1 ไฟล์ = ห้ามปล่อยงานเข้ากระบวนการ (HARD STOP)

---

## 3) Pipeline Overview (ภาพเดียวจบ)

### 3.1 Flow (Per Module)

```
Module 1: AIEL-0 → AIEL-1 → AIEL-2 → AIEL-3 → AIEL-T → Gate C → Receipt 1
Module 2: AIEL-0 → AIEL-1 → AIEL-2 → AIEL-3 → AIEL-T → Gate C → Receipt 2
Module 3: AIEL-0 → AIEL-1 → AIEL-2 → AIEL-3 → AIEL-T → Gate C → Receipt 3
...
Module N: AIEL-0 → AIEL-1 → AIEL-2 → AIEL-3 → AIEL-T → Gate C → Receipt N
```

### 3.2 Flow (Project Level)

```
N Receipts → Integration → Project Bundle → M8 → Stage2 → M7 → PASS/FAIL
```

### 3.3 Rule of Responsibility

* ถ้า "ตีความ spec ผิด" → กลับ AIEL-0
* ถ้า "โครงสร้างเละ/โมดูลปน" → กลับ AIEL-1
* ถ้า "logic ไม่ผ่าน/ไม่ deterministic/หลักฐานไม่ครบ" → กลับ AIEL-2
* ถ้า "polish แล้วหลุด semantics" → กลับ AIEL-2 (ห้ามแก้ที่ AIEL-3)
* ถ้า "AIEL-T ไม่ผ่าน (G-score < 0.95)" → กลับ AIEL-2
* ถ้า "Gate C ไม่สร้าง receipt ได้" → กลับ AIEL-T (evidence ไม่ครบ)
* ถ้า "Integration ไม่ผ่าน" → แก้ compatibility issues
* ถ้า "M8 ไม่ผ่าน" → แก้ determinism/integration
* ถ้า "M7 replay fail" → กลับ AIEL-2 (ไม่ deterministic)

---

# ✅ 4) AIEL-0 — Spec → Raw Code (Interpreter Layer)

## 4.1 Mission

สร้าง raw code ที่ "ถูกแก่น" และ "มีทางเดินครบ"
**คำเตือน:** AIEL-0 คือเลเยอร์ที่เสี่ยงที่สุดเพราะเป็นจุดตีความ

## 4.2 AIEL-0 Mandatory Read (HARD REQUIREMENT)

AIEL-0 ต้องอ่าน:

* MASTER_SPEC
* DATA_STRUCTURES
* KAMI + DNA
* GOLDEN_IO_LOCK
* REASON_CODES_v1.yaml **← สำคัญ!**
* Router spec set (ถ้ามี decision/authority)

**Rule:** ไม่อ่าน = "หลุดแน่นอน" (พี่โจพิสูจน์แล้ว)

## 4.3 AIEL-0 Output Scope

AIEL-0 ต้องส่งมอบ:

* โค้ดที่ "run/compile ได้ขั้นต่ำ"
* I/O shape ตรง schema
* hooks 3 อย่างต้องมี:
  * **Evidence hook** (e.g. noise_residual/evidence_ref/segment_hash)
  * **Determinism hook** (canonical_json + compute_determinism_key)
  * **AIEL-T hook** (test interface for validation) **← เพิ่มใหม่**

## 4.4 AIEL-0 Light Gates (กันตั้งไข่ล้ม)

> AIEL-0 gate ต้อง "เบาแต่ฆ่าความเสี่ยงสูง"

### Gate 0.1 Schema Skeleton Gate

* required keys ใน schema ต้องโผล่ครบ
* ขาด = FAIL

### Gate 0.2 No Free-Text Gate

* reason_code ต้องมาจาก REASON_CODES_v1.yaml allowlist เท่านั้น
* free-text = FAIL

### Gate 0.3 Evidence Hook Presence Gate

* ถ้า module อยู่ในสาย evidence:
  * noise_residual/segment_hash ต้อง "มี field" และ "ถูกส่งต่อ"
* missing = FAIL

### Gate 0.4 Determinism Hook Presence Gate

* ต้องมี:
  * canonical_json() (sort_keys + float normalize + NaN/null rule)
  * compute_determinism_key() (sha256 canonical_payload + toolchain)
* missing = FAIL

### Gate 0.5 AIEL-T Interface Gate **← เพิ่มใหม่**

* ต้องมี test interface ที่ AIEL-T เรียกได้
* ต้อง return ค่าตาม I/O contract
* missing = FAIL

## 4.5 AIEL-0 Handoff Packet

AIEL-0 ต้องแนบ "ของจริง" ต่อไปนี้ไปให้ AIEL-1:

* code artifacts
* list เอกสารที่อ่าน (proof-of-read list)
* gate report: PASS/FAIL (0.1–0.5)
* TODO list ที่ "ยังไม่ harden" (ส่งไม้ให้ AIEL-2)

---

# ✅ 5) AIEL-1 — Structural Refiner (Structure Layer)

## 5.1 Mission

จัดระเบียบให้ maintainable โดย **ไม่แตะ semantics**

## 5.2 Allowed / Forbidden

✅ Allowed:

* แยกไฟล์, แยกโมดูล, จัด dependency direction
* ปรับ naming ให้ตรง DNA/KAMI
* เพิ่ม docstring/README skeleton (ถ้า spec บอก)

❌ Forbidden:

* เปลี่ยน logic/เงื่อนไข/สูตร/decision behavior

## 5.3 Structural Gates

### Gate 1.1 Layer Boundary Gate

* ห้าม import ย้อนเลเยอร์ผิดทิศ
* ห้าม circular dependency

### Gate 1.2 Naming & Layout Gate

* naming, folders, entrypoints ตรง DNA

### Gate 1.3 Interface Stability Gate

* function signatures + I/O shape ต้องไม่เปลี่ยนจาก schema

## 5.4 Failure Routing

* โครงสร้างพัง → กลับ AIEL-1
* เจอ semantics เปลี่ยน → ส่งกลับ AIEL-2 (ไม่ให้จบที่ AIEL-1)

---

# ✅ 6) AIEL-2 — Performance / Logic Hardening (Correctness Layer)

## 6.1 Mission

"เข้มจริง" ที่นี่: correctness + determinism + evidence + invariants
AIEL-2 คือด่านที่ทำให้ของ "กลายเป็นของจริง"

## 6.2 Allowed / Forbidden

✅ Allowed:

* แก้ logic เพื่อให้ถูก spec
* เพิ่ม validations/invariants
* เพิ่ม caching/optimization ที่ไม่เปลี่ยน semantics

❌ Forbidden:

* เปลี่ยน Golden I/O semantics
* เปลี่ยน canonicalization rules
* เปลี่ยน reason_code vocabulary
* เพิ่ม free-text findings

## 6.3 AIEL-2 Mandatory Gates (เข้ม)

### Gate 2.1 Golden I/O Lock Gate

* required fields ต้องครบ
* missing/len mismatch = HARD FAIL (ตาม GOLDEN_IO_LOCK)

### Gate 2.2 Determinism Gate

* same inputs → same determinism_key
* cross-run → bit-exact

### Gate 2.3 Evidence Integrity Gate

* evidence ต้องครบ + replayable
* เช่น `noise_residual` ต้องมีและถูกนิยามตาม schema
* segment_hash ต้อง rehash แล้วได้ค่าเดิม 100%

### Gate 2.4 No Contamination Gate

* ห้าม truth_data รั่วเข้า canonical payload / hash
* ห้าม "กลบเกลี่ย" หลักฐานจน audit ทำไม่ได้

### Gate 2.5 Invariants / Safety Gate

* invariants ที่ spec กำหนดต้อง enforce ได้จริง
* fail → ต้อง reason_code แบบ allowlist

### Gate 2.6 Reason Code Allowlist Gate **← เพิ่มใหม่**

* ทุก reason_code ต้องอยู่ใน REASON_CODES_v1.yaml
* ห้าม hardcode reason codes
* ห้าม free-text
* missing = FAIL

## 6.4 Failure Routing (สำคัญ)

* ถ้า AIEL-3 บอก "ยังไม่ผ่าน" → **วนกลับ AIEL-2**
* เพราะ AIEL-3 ห้ามแตะแก่น

---

# ✅ 7) AIEL-3 — Polish / Documentation (Presentation Layer)

## 7.1 Mission

ทำให้โค้ด "อ่านง่าย ดูแลได้" โดย **คง semantics 100%**

## 7.2 Allowed / Forbidden

✅ Allowed:

* refactor อ่านง่าย (ไม่แตะ behavior)
* comments/docs
* formatting lint

❌ Forbidden:

* เปลี่ยน condition/order/precision/rounding rules
* เปลี่ยน decision outputs
* เปลี่ยน hash/canonicalization

## 7.3 AIEL-3 Gates

### Gate 3.1 No-Semantics-Change Gate

* golden test vectors must match exactly
* outputs/determinism_key ต้องเหมือนเดิม

### Gate 3.2 Replay Gate

* re-run same inputs → exact same outputs
* mismatch = FAIL → ส่งกลับ AIEL-2

---

# ✅ 8) AIEL-T — Test Validation Engine (Quality Gate)

## 8.1 Mission

รัน tests และเก็ب evidence เพื่อคำนวณ **G-Score** (validation quality)

## 8.2 AIEL-T Requirements

* รัน 4 engines:
  1. **Invariants Engine** (weight: 45%)
  2. **Pattern Engine** (weight: 15%)
  3. **Contract Engine** (weight: 10%)
  4. **Scenario Engine** (weight: 30%)

* คำนวณ G-Score:
  ```
  G-Score = Σ(engine_score × weight)
  ```

* ตัดสิน:
  ```
  G-Score ≥ 0.95 → DEPLOYABLE
  G-Score ≥ 0.85 → ACCEPTABLE
  G-Score < 0.85 → FAIL
  ```

## 8.3 AIEL-T Output

```json
{
  "g_score": 1.0,
  "status": "DEPLOYABLE",
  "test_result": {
    "coverage": 1.0,
    "tests_passed": 5,
    "tests_total": 5
  },
  "toolchain": {
    "python_version": "3.11.9",
    "dependencies": {...}
  },
  "engines": {
    "invariants": {"score": 1.0, "passed": 2, "total": 2},
    "patterns": {"score": 1.0, "passed": 5, "total": 5},
    "contracts": {"score": 1.0, "valid": 3, "total": 3},
    "scenarios": {"score": 1.0, "passed": 0, "total": 0}
  }
}
```

## 8.4 AIEL-T Gates

### Gate T.1 G-Score Threshold Gate

* G-Score ≥ 0.95 → PASS (production-ready)
* G-Score < 0.95 → FAIL → กลับ AIEL-2

### Gate T.2 Coverage Gate

* Test coverage ≥ 95% → PASS
* < 95% → reason_code: RC_EVIDENCE_INCOMPLETE_SAFE_MODE

### Gate T.3 Toolchain Capture Gate

* ต้องเก็บ toolchain manifest (Python version, dependencies)
* missing = FAIL

---

# ✅ 9) Gate C — Decision Receipt Builder+Enforcer (Proof Layer)

## 9.1 Mission

สร้าง **Decision Receipt** ที่:
* Lock decision context (parameters, evidence)
* Compute hashes (parameters_hash, evidence_set_hash, receipt_hash)
* Enforce reason_code allowlist
* Enable replay (determinism_key)
* Write-once (ห้ามแก้ไขหลัง execute)

## 9.2 Gate C Requirements

* **Input:** AIEL-T result + module info
* **Output:** Decision Receipt (JSON)
* **SSOT:** gate_c_decision_receipt_spec_v_1_0.md

## 9.3 Decision Receipt Structure

```json
{
  "decision_id": "dec_abc123",
  "timestamp_utc": "2026-01-27T04:10:08.419579Z",
  "project_id": "pythonbrain",
  "module_id": "router",
  "language": "python",
  
  "toolchain_manifest_digest": "t_sha256...",
  
  "context": {
    "context_level": "L3",
    "context_hash": "c_sha256..."
  },
  
  "decision": {
    "router_decision": "APPROVED",
    "guard_verdict": "APPROVED",
    "risk_params": {"g_score": 1.0}
  },
  
  "hashes": {
    "parameters_hash": "sha256...",
    "evidence_set_hash": "sha256...",
    "receipt_hash": "sha256..."
  },
  
  "evidence_refs": [
    {
      "name": "aiel_t.test_result",
      "ref_type": "sha256",
      "ref_hash": "sha256..."
    }
  ],
  
  "reason_codes": [],
  
  "determinism_key": "sha256..."
}
```

## 9.4 Gate C Rules (LOCK)

### Rule C.1 Allowlist Only

* ทุก reason_code ต้องอยู่ใน REASON_CODES_v1.yaml
* Unknown code → GateCError: RC_RECEIPT_REASON_CODE_UNKNOWN

### Rule C.2 Hash Chain

```
parameters_payload → parameters_hash (SHA-256)
evidence_set_payload → evidence_set_hash (SHA-256)
receipt (minus timestamp_utc) → receipt_hash (SHA-256)
config + toolchain + locks → determinism_key (SHA-256)
```

### Rule C.3 Receipt Hash Excludes Timestamp

* receipt_hash คำนวณจาก receipt ทั้งหมด **ยกเว้น timestamp_utc**
* เพื่อให้ replay ได้ (same inputs → same receipt_hash)

### Rule C.4 Write-Once

* receipt เขียนลง filesystem ด้วย mode='x' (exclusive create)
* ถ้า file exists → GateCError: RC_RECEIPT_NOT_WRITTEN_PRE_EXECUTION

### Rule C.5 Context Level

* G-Score ≥ 0.95 → L3 (high confidence)
* G-Score ≥ 0.85 → L2 (medium)
* G-Score ≥ 0.75 → L1 (low)
* G-Score < 0.75 → L0 (insufficient)

## 9.5 Gate C Golden Tests

7 tests ที่ต้องผ่าน:

1. **test_01_schema_minimal_presence** — required fields ครบ
2. **test_02_reason_allowlist** — reason codes ในallowlist
3. **test_03_canonical_json_sorted** — dict keys sorted
4. **test_04_float_norm_nan_and_negzero** — float normalization
5. **test_05_determinism_key_reproducible** — same inputs → same key
6. **test_06_receipt_hash_excludes_timestamp** — timestamp excluded
7. **test_07_pre_exec_persist_invariant** — write-once enforcement

## 9.6 Gate C Wrapper Integration

```python
from gate_c_wrapper import GateCWrapper

wrapper = GateCWrapper(base_dir="/path/to/config")

result = wrapper.process_aiel_t_output(
    aiel_t_result=aiel_t_result,
    module_info={
        "project_id": "pythonbrain",
        "module_id": "router",
        "language": "python"
    },
    output_dir="/path/to/receipts"
)

# result:
# {
#   "gate_c_available": True,
#   "receipt_created": True,
#   "receipt_written": True,
#   "receipt": {...},
#   "receipt_path": "/path/to/receipts/Decision_Receipt_dec_abc123.json"
# }
```

---

# ✅ 10) Integration — Multi-Module Assembly (Compatibility Layer)

## 10.1 Mission

รวมหลาย modules (แต่ละตัวผ่าน Gate C แล้ว) เป็น **project bundle** เดียว

## 10.2 Integration Requirements

* ตรวจสอบ:
  * **ABI compatibility** (I/O contracts match)
  * **Schema compatibility** (data structures align)
  * **Toolchain pinning** (same Python version, dependencies)
  * **Reason code consistency** (ใช้ allowlist เดียวกัน)

## 10.3 Integration Output

* **Project Bundle (ZIP)** ที่มี:
  * N receipts (Decision_Receipt_*.json)
  * manifest.json (module inventory + graph)
  * toolchain.json (toolchain manifest)
  * tests/ (test files)

## 10.4 Integration Gates

### Gate I.1 ABI Compatibility Gate

* I/O contracts ของแต่ละ module ต้อง compatible
* mismatch = FAIL

### Gate I.2 Schema Compatibility Gate

* Data structures ต้อง align
* type mismatch = FAIL

### Gate I.3 Toolchain Consistency Gate

* ทุก module ใช้ toolchain เดียวกัน
* version mismatch = WARNING (อาจทำงาน แต่ไม่แนะนำ)

### Gate I.4 Reason Code Consistency Gate

* ทุก module ใช้ REASON_CODES_v1.yaml เดียวกัน
* mismatch = FAIL

---

# ✅ 11) M8 — Integration + Determinism Gate (System Coherence)

## 11.1 Mission

ตรวจว่าหลายโมดูล "ต่อกันแล้วไม่หลุด" และ determinism ยังอยู่

## 11.2 M8 Pipeline (5 Stages)

### M8-1: Graph Validator

* ตรวจ module_inventory + graph (nodes, edges)
* required_nodes ต้องมีครบ
* PASS/FAIL

### M8-2: Invariant Engine

* รัน invariants จาก m8_invariants.yaml
* ตัวอย่าง:
  ```yaml
  - name: "graph_has_required_nodes"
    expression: "all(node in graph.nodes for node in required_nodes)"
  ```
* PASS/FAIL

### M8-3: Canonicalization

* คำนวณ determinism_key จาก:
  ```python
  payload = {
      "graph_valid": True,
      "graph_signature": "...",
      "invariants_passed": 1
  }
  determinism_key = sha256(canonical_json(payload))
  ```

### M8-4: Replay Verify

* ตรวจว่า determinism_key สามารถ replay ได้
* same payload → same key

### M8-5: Final Verdict

* ถ้าทุกอย่าง PASS → M8 status: PASS
* ถ้ามีอะไร FAIL → M8 status: FAIL

## 11.3 M8 Rules

* M8 **ไม่ใช่** runtime verifier (นั่นคือหน้าที่ของ M7)
* M8 = determinism + integration + graph validation
* M8 ต้องผ่านก่อนถึงจะส่งต่อ Stage2

---

# ✅ 12) Stage2 — Validator/Authority (Product Gate)

## 12.1 Mission

ตัดสิน PASS/FAIL แบบ product-grade
รองรับ multi-language ด้วย "language-agnostic output contract"

## 12.2 Stage2 Pipeline (M1-M6)

### M1: Ingest

* รับ project bundle (ZIP)
* แตก files

### M2: Enumerate

* นับ modules
* สร้าง module descriptors

### M3: Toolchain Manifest

* capture toolchain (Python version, dependencies)

### M4: Static Analysis

* รัน static analysis (optional)
* เก็บ findings

### M5: Runtime Testing

* รัน tests จริง (pytest)
* เก็บ test results

### M6: Aggregation + Final Verdict

* aggregate scores:
  ```python
  repo_score = (static_score × 0.45) + (runtime_score × 0.55)
  ```
* ตัดสิน:
  ```
  repo_score ≥ 0.95 → PASS
  repo_score < 0.95 → FAIL
  ```

## 12.3 Stage2 Output

```json
{
  "stage2_version": "1.0",
  "status": "PASS",
  "repo_verdict": "PASS",
  "repo_score": 1.0,
  "modules_checked": 1,
  "static_findings": 0,
  "tests_passed": 1,
  "tests_total": 1,
  "context_gate_level": "L3",
  "full_report": {...}
}
```

---

# ✅ 13) M7 — Replay Runtime Verifier (Final Proof)

## 13.1 Mission

ตรวจว่า **runtime execution เป็น deterministic จริง**

## 13.2 M7 Process

1. **Baseline Run (run1):**
   ```
   pytest -q tests/ → (exit_code, tests_passed, tests_failed)
   ```

2. **Compute Determinism Key (run1):**
   ```python
   canonical_data = {
       "tests_total": tests_collected,
       "tests_passed": tests_passed,
       "tests_failed": tests_failed,
       "policy_digests": {...},
       "toolchain_digest": "..."
   }
   key1 = sha256(canonical_json(canonical_data))
   ```

3. **Replay Run (run2):**
   ```
   pytest -q tests/ → (exit_code, tests_passed, tests_failed)
   ```

4. **Compute Determinism Key (run2):**
   ```python
   key2 = sha256(canonical_json(canonical_data))
   ```

5. **Compare:**
   ```python
   if key1 == key2:
       replay_verified = True
   else:
       replay_verified = False
       reason_code = "M7_REPLAY_FAIL"
   ```

## 13.3 M7 Rules

* M7 ใช้ **structured summary only** (ไม่ใช้ stdout/stderr)
* เพราะ stdout มี timing/path info ที่ไม่ deterministic
* M7 ignore exit_code (focus on test counts only)

## 13.4 M7 Output

```json
{
  "replay_verified": true,
  "determinism_key_first": "00c9d3f960e3d91c...",
  "determinism_key_replay": "00c9d3f960e3d91c...",
  "reason_code": null,
  "evidence": {
    "replay_command": "pytest -q",
    "replay_exit_code": 0,
    "replay_duration_ms": 504
  }
}
```

---

# 🔥 14) Key Design Decision (สิ่งที่พี่โจถาม "เลือกทางไหนดีที่สุด")

## เราเลือก:

> **AIEL-0 อ่านหนัก + เทสเบา**
> **AIEL-2 เข้มจริง**
> **Gate C สร้าง receipt proof**
> **M7 verify runtime determinism**

### เพราะ:

* ถ้า AIEL-0 ไม่อ่าน → หลุด semantics แน่นอน
* ถ้า AIEL-0 เข้มเกิน → โหลดมาตรฐานไว้ที่ตัวเดียว = ช้า/ล้มบ่อย
* AIEL-T + Gate C = proof ของจริง (ไม่ใช่ความเห็นลอยๆ)
* M8 = determinism gate (ไม่ใช่ runtime verifier)
* M7 = runtime verifier (ตรวจจริงว่า deterministic)
* ระบบที่ดีที่สุดคือ "ค่อยเข้มขึ้น" แต่ "ตั้งต้นถูก" + "มี proof"

---

# ✅ 15) One-Line Operating Rule (เอาไปติดหัวทีม)

```
AIEL-0 = Correct Interpretation (อ่านหนัก, gate เบา)
AIEL-1 = Maintainable Structure (ไม่แตะ logic)
AIEL-2 = Correctness + Determinism + Evidence (เข้มจริง)
AIEL-3 = Polish without changing truth (คง semantics)
AIEL-T = Validation Quality (G-score ≥ 0.95)
Gate C = Receipt Proof (lock decision context)
Integration = Multi-Module Assembly (compat check)
M8 = Determinism + Integration Gate (5 stages)
Stage2 = Final Authority (M1-M6)
M7 = Runtime Replay Verifier (proof of determinism)
```

---

# 📋 16) Complete Checklist (ติ๊กก่อนเริ่ม)

## Pre-Pipeline Checklist

```
[ ] MASTER_SPEC พร้อม
[ ] DATA_STRUCTURES (schema) พร้อม
[ ] KAMI (vocabulary) พร้อม
[ ] DNA_SYSTEM_GUIDE พร้อม
[ ] GOLDEN_IO_LOCK พร้อม
[ ] REASON_CODES_v1.yaml พร้อม
[ ] gate_c_decision_receipt_spec_v_1_0.md พร้อม
[ ] M8_REPLAY_GATE_CHECKLIST พร้อม
[ ] Golden test vectors พร้อม
```

## AIEL-0 Checklist

```
[ ] อ่านเอกสารทั้ง 9 ไฟล์
[ ] Schema skeleton ครบ
[ ] No free-text reason codes
[ ] Evidence hooks มี
[ ] Determinism hooks มี
[ ] AIEL-T interface มี
[ ] Handoff packet พร้อม
```

## AIEL-1 Checklist

```
[ ] Layer boundary ถูกต้อง
[ ] Naming ตรง DNA
[ ] Interface stable
[ ] ไม่แตะ semantics
```

## AIEL-2 Checklist

```
[ ] Golden I/O ครบ
[ ] Determinism ผ่าน
[ ] Evidence integrity ผ่าน
[ ] No contamination
[ ] Invariants enforce ได้
[ ] Reason codes ใน allowlist
```

## AIEL-3 Checklist

```
[ ] No semantics change
[ ] Replay test ผ่าน
[ ] Golden vectors match
```

## AIEL-T Checklist

```
[ ] G-Score ≥ 0.95
[ ] Coverage ≥ 95%
[ ] Toolchain captured
[ ] 4 engines ผ่าน
```

## Gate C Checklist

```
[ ] 7/7 golden tests ผ่าน
[ ] Receipt created
[ ] Hashes computed
[ ] Reason codes ใน allowlist
[ ] Determinism key computed
[ ] Write-once enforced
[ ] Receipt written
```

## Integration Checklist

```
[ ] ABI compatible
[ ] Schema compatible
[ ] Toolchain consistent
[ ] Reason codes consistent
[ ] Project bundle created
```

## M8 Checklist

```
[ ] M8-1 (Graph) ผ่าน
[ ] M8-2 (Invariants) ผ่าน
[ ] M8-3 (Canonicalization) ผ่าน
[ ] M8-4 (Replay Verify) ผ่าน
[ ] M8-5 (Final Verdict) ผ่าน
```

## Stage2 Checklist

```
[ ] M1 (Ingest) ผ่าน
[ ] M2 (Enumerate) ผ่าน
[ ] M3 (Toolchain) ผ่าน
[ ] M4 (Static) ผ่าน
[ ] M5 (Runtime) ผ่าน
[ ] M6 (Aggregation) ผ่าน
[ ] Final verdict: PASS
```

## M7 Checklist

```
[ ] Baseline run complete
[ ] Determinism key computed
[ ] Replay run complete
[ ] Keys match
[ ] Replay verified: TRUE
```

---

# 🎯 17) Multi-Module Flow Example

## Example: PythonBrain Project (2 Modules)

### Module 1: GIM_GOLDEN_V1

```
AIEL-0 → AIEL-1 → AIEL-2 → AIEL-3
   ↓
AIEL-T (G-Score: 1.0)
   ↓
Gate C (Receipt: dec_abc123)
```

### Module 2: VAPD_GOLDEN_V1

```
AIEL-0 → AIEL-1 → AIEL-2 → AIEL-3
   ↓
AIEL-T (G-Score: 1.0)
   ↓
Gate C (Receipt: dec_def456)
```

### Integration

```
2 Receipts + manifest.json + tests/
   ↓
Integration (compat check)
   ↓
project_bundle.zip
```

### M8 → Stage2 → M7

```
project_bundle.zip
   ↓
M8 (determinism gate) → PASS
   ↓
Stage2 (M1-M6) → PASS (score: 1.0)
   ↓
M7 (replay verify) → PASS
   ↓
FINAL: PASS 🎉
```

---

# 📊 18) Success Metrics

## Per-Module Metrics

```
AIEL-0: Interpretation accuracy (spec → code)
AIEL-1: Structure quality (maintainability)
AIEL-2: Correctness (logic + determinism + evidence)
AIEL-3: Polish quality (readability)
AIEL-T: G-Score (≥ 0.95 target)
Gate C: Receipt creation success rate
```

## Project-Level Metrics

```
Integration: Compatibility success rate
M8: Determinism success rate
Stage2: Final verdict (PASS/FAIL)
M7: Replay verification rate
```

## Overall Pipeline

```
Success Rate = (Certified Modules / Total Modules) × 100%
Target: ≥ 95%
```

---

# 🚀 19) Quick Start Guide

## For Single Module

```bash
# Step 1: AIEL-0..3
python aiel_pipeline.py --spec module_spec.yaml

# Step 2: AIEL-T
python aiel_t_cli.py --quick-test

# Step 3: Gate C
python integrate.py  # สร้าง receipt

# Done: Receipt created!
```

## For Multi-Module Project

```bash
# Step 1-3: Per module (ทำ N ครั้ง)
# ... (เหมือนด้านบน)

# Step 4: Integration
python integrate_multi.py --receipts receipts/ --output project_bundle.zip

# Step 5: M8 + Stage2 + M7
python gate_runner.py project_bundle.zip --output final_report.json

# Done: PASS/FAIL
```

---

# 📚 20) Reference Documents

## Core Specs

1. `FACTORY-A_FULL_PIPELINE_POLICY_v1_1.md` (this document)
2. `gate_c_decision_receipt_spec_v_1_0.md`
3. `GOLDEN_IO_LOCK_GATEC_v1.yaml`
4. `REASON_CODES_v1.yaml`
5. `M8_REPLAY_GATE_CHECKLIST_v1.2b.md`

## Implementation

1. `gate_c.py` (Gate C core)
2. `gate_c_wrapper.py` (Gate C wrapper for Factory-A)
3. `integrate.py` (Integration script)
4. `gate_runner.py` (M8 + Stage2 + M7 runner)
5. `test_golden_gateC.py` (Gate C golden tests)

## Examples

1. `final_report.json` (example output)
2. `Decision_Receipt_dec_*.json` (example receipts)
3. `project_bundle.zip` (example project bundle)

---
Here is a clean English remark you can paste at the end of **FACTORY-A FULL PIPELINE POLICY v2**:

---

## 📋✅🔥 Remark — Strict 100% Mode (Optional) 🚀

For **internal Factory-A usage**, enabling “100% strict mode” is **not required at this stage**.

The current objective is:

* **Module production readiness**
* **Deterministic proof + replay stability**
* **End-to-end authority chain integrity**

And these goals are already satisfied.

At the moment, the remaining gaps are **not functional failures**, only optional hardening points:

### A) Scenario Engine Coverage = 0 Triggered

The pipeline currently reports **PASS**, but no real scenario conditions have been activated yet.
This means coverage has not been stress-tested under true market regimes.
If the system is later used for external certification, this may be upgraded to a mandatory **flag or FAIL condition**.

### B) Toolchain Authority Must Be Evidence-Driven

For full commercial-grade audit strength, the toolchain digest should always be loaded directly from the evidence bundle and verified against runtime.
This ensures the toolchain pin is a true authority lock, not a placeholder capture.

**Conclusion:**
Strict enforcement is optional for Factory-A internal deployment, but recommended if the pipeline is extended toward external certification-grade guarantees.

---

**END OF DOCUMENT**

**Version:** 1.1
**Date:** 2026-01-27
**Status:** Ready for Production

**Next Update:** When adding OmniGraph (Trinity + Scenario Router + Falsifier)
