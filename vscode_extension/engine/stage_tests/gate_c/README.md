# Gate C - Decision Receipt Validator

## ✅ Test Results: 7/7 PASS

```
✅ 01. Schema Minimal Presence: PASS
✅ 02. Reason Allowlist: PASS
✅ 03. Canonical JSON Sorted: PASS
✅ 04. Float Norm NaN and NegZero: PASS
✅ 05. Determinism Key Reproducible: PASS
✅ 06. Receipt Hash Excludes Timestamp: PASS
✅ 07. Pre-Exec Persist Invariant: PASS
```

---

## 📁 Structure

```
gate_c_test/
├── __init__.py                  # Module init
├── gate_c.py                    # Gate C validator (GPT)
├── canonical_json.py            # Canonical JSON helpers (GPT)
├── gate_c_wrapper.py            # Wrapper (GPT)
├── test_golden_gateC.py         # Golden tests (You)
├── run_tests.py                 # Test runner (Claude)
└── README.md                    # This file
```

---

## 🧪 How to Test

### 1. Run Golden Tests (Standalone)
```bash
python run_tests.py
```

### 2. Run Golden Tests (pytest)
```bash
pytest test_golden_gateC.py -v
```

### 3. Integration Test
```python
from gate_c import validate_receipt
from test_golden_gateC import minimal_receipt

receipt = minimal_receipt()
result = validate_receipt(receipt)
print(result)
```

---

## 📦 Integration with Pipeline

### Position in Pipeline:
```
AIEL-T → Gate C → Integration → M8 → Stage2 → M7
         ^^^^^^
         ตรง นี้!
```

### Usage:
```python
# After AIEL-T
from gate_c import validate_receipt

# Validate decision receipt
result = validate_receipt(decision_receipt)

if result['status'] == 'PASS':
    # Continue to Integration
    pass
else:
    # Stop pipeline
    reason_codes = result['reason_codes']
    print(f"Gate C FAIL: {reason_codes}")
```

---

## 🔧 API

### validate_receipt(receipt: dict) -> dict

**Input:**
```json
{
  "decision_id": "dec_12345678",
  "timestamp_utc": "2026-01-24T00:00:00Z",
  "project_id": "pythonbrain",
  "module_id": "router",
  "language": "python",
  "toolchain_manifest_digest": "t_aaa...",
  "context": {...},
  "decision": {...},
  "hashes": {...},
  "evidence_refs": [...],
  "reason_codes": [],
  "determinism_key": "..."
}
```

**Output:**
```json
{
  "status": "PASS|FAIL",
  "reason_codes": ["RC_*"],
  "receipt_hash": "sha256...",
  "validated_at": "2026-01-25T..."
}
```

---

## ✅ Validation Rules

1. **Schema**: ตรวจ required fields ครบ
2. **Reason Codes**: ต้องอยู่ใน ALLOWED_REASON_CODES
3. **Canonical JSON**: sort_keys, float 6 decimals
4. **Determinism Key**: reproducible (same input → same key)
5. **Receipt Hash**: excludes timestamp
6. **Pre-Exec Persist**: receipt ต้องเขียนก่อน execute

---

## 🚀 Status

- ✅ Code Complete (GPT)
- ✅ Tests Pass (7/7)
- ✅ Ready for Integration
- ⏳ Pending: Integration with Factory A

---

## 📝 Next Steps

1. ✅ Validate with golden tests (DONE)
2. ⏳ Integrate with AIEL-T output
3. ⏳ Add to Factory A pipeline
4. ⏳ Test end-to-end flow

---

**Gate C v1.0**  
*Decision Receipt Validation*  
*Tested: 2026-01-25*
