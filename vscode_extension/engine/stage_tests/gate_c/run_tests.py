#!/usr/bin/env python3
"""
Standalone Test Runner for Gate C
No pytest required - runs tests directly
"""
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import golden tests
from test_golden_gateC import (
    test_01_schema_minimal_presence,
    test_02_reason_allowlist,
    test_03_canonical_json_sorted,
    test_04_float_norm_nan_and_negzero,
    test_05_determinism_key_reproducible,
    test_06_receipt_hash_excludes_timestamp,
    test_07_pre_exec_persist_invariant
)


def run_tests():
    """Run all golden tests"""
    print("\n" + "="*60)
    print("Gate C - Golden Tests Validation")
    print("="*60 + "\n")
    
    tests = [
        ("01. Schema Minimal Presence", test_01_schema_minimal_presence),
        ("02. Reason Allowlist", test_02_reason_allowlist),
        ("03. Canonical JSON Sorted", test_03_canonical_json_sorted),
        ("04. Float Norm NaN and NegZero", test_04_float_norm_nan_and_negzero),
        ("05. Determinism Key Reproducible", test_05_determinism_key_reproducible),
        ("06. Receipt Hash Excludes Timestamp", test_06_receipt_hash_excludes_timestamp),
        ("07. Pre-Exec Persist Invariant", test_07_pre_exec_persist_invariant)
    ]
    
    passed = 0
    failed = 0
    errors = []
    
    for name, test_func in tests:
        try:
            test_func()
            print(f"✅ {name}: PASS")
            passed += 1
        except AssertionError as e:
            print(f"❌ {name}: FAIL")
            print(f"   {str(e)}")
            failed += 1
            errors.append((name, str(e)))
        except Exception as e:
            print(f"❌ {name}: ERROR")
            print(f"   {str(e)}")
            failed += 1
            errors.append((name, f"ERROR: {str(e)}"))
    
    print("\n" + "="*60)
    print(f"Results: {passed}/{len(tests)} PASS, {failed}/{len(tests)} FAIL")
    print("="*60)
    
    if errors:
        print("\nFailed Tests:")
        for name, error in errors:
            print(f"  - {name}: {error}")
    
    return failed == 0


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
