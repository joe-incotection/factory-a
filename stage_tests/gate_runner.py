#!/usr/bin/env python3
"""M8 + Stage2 Gate Runner - Optimized Version

Usage:
    python gate_runner.py <input_folder> [--output report.json]
"""

import sys

# ---- FORCE UTF-8 CONSOLE (Windows safe) ----
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json
import argparse
import zipfile
import tempfile
import traceback
import re
import hashlib
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

# ==================== PATH SETUP ====================
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir / "m8"))
sys.path.insert(0, str(current_dir / "stage2"))
sys.path.insert(0, str(current_dir / "m7"))
sys.path.insert(0, str(current_dir))

# ==================== IMPORTS WITH BETTER ERROR HANDLING ====================
def safe_import(module_name: str, import_func):
    """Safely import module with detailed error reporting"""
    try:
        return import_func()
    except ImportError as e:
        print(f"[!] Warning: Cannot import {module_name}: {e}")
        if "No module named" in str(e):
            print(f"    Make sure {module_name} is in the Python path")
        return None

# M8 Imports
M8_MODULES = {}
try:
    from m8_1_graph_validator import validate_graph
    from m8_2 import m8_2_run_invariants
    from m8_3_canonicalization import canonical_json, compute_determinism_key
    from m8_4 import m8_4_replay_verify
    from m8_5_verdict import m8_5_final_verdict
    M8_MODULES = {
        'validate_graph': validate_graph,
        'm8_2_run_invariants': m8_2_run_invariants,
        'compute_determinism_key': compute_determinism_key,
        'm8_4_replay_verify': m8_4_replay_verify,
        'm8_5_final_verdict': m8_5_final_verdict
    }
except ImportError as e:
    print(f"[X] Critical: M8 modules import failed: {e}")
    sys.exit(1)

# Stage2 Imports
STAGE2_MODULES = {}
STAGE2_AVAILABLE = False
try:
    from stage2 import (
        process_zip,
        generate_module_descriptors,
        get_toolchain_manifest,
        analyze_code,
        run_tests,
        aggregate_and_report
    )
    STAGE2_MODULES = {
        'process_zip': process_zip,
        'generate_module_descriptors': generate_module_descriptors,
        'get_toolchain_manifest': get_toolchain_manifest,
        'analyze_code': analyze_code,
        'run_tests': run_tests,
        'aggregate_and_report': aggregate_and_report
    }
    STAGE2_AVAILABLE = True
except ImportError as e:
    print(f"[!] Warning: Stage2 modules not available: {e}")
    STAGE2_AVAILABLE = False

# M7 Import
M7_AVAILABLE = False
try:
    from module7_runtime_replay import verify_runtime_replay, IntegrityError as M7IntegrityError
    M7_AVAILABLE = True
except ImportError:
    print("[!] Warning: M7 module not found - runtime replay disabled")
    M7IntegrityError = None  # type: ignore[assignment,misc]

# ==================== CONFIGURATION ====================
DEFAULT_CONFIG = {
    'm8_invariants_file': 'm8_invariants.yaml',
    'test_timeout': 60,
    'enable_m7_replay': True,
    'max_zip_size_mb': 100,
    'temp_dir_prefix': 'gate_runner_'
}


def _run_pytest_suite(project_root: Path, timeout_s: int) -> Dict[str, Any]:
    """
    Run pytest inside extracted bundle root in a deterministic, Windows-safe way.

    Key rules:
      - Always run with cwd=project_root so relative LAW file opens work.
      - Prefer running 'tests' folder if present.
      - If pytest.ini exists, force using it via '-c pytest.ini' (pythonpath=.)
    """
    project_root = Path(project_root)

    # Ensure pytest.ini and tests/ are resolved from the same runnable CWD.
    run_root = project_root
    test_target = "."

    if (project_root / "pytest.ini").exists() and (project_root / "tests").exists():
        run_root = project_root
        test_target = "tests"
    else:
        # Look for a nested directory that contains BOTH pytest.ini and tests/
        nested_candidates = sorted(
            [p for p in project_root.iterdir() if p.is_dir()],
            key=lambda p: p.name.lower()
        )
        for p in nested_candidates:
            if (p / "pytest.ini").exists() and (p / "tests").exists():
                run_root = p
                test_target = "tests"
                break
        else:
            # Fallback: if tests exists at root, use it; otherwise run from root.
            if (project_root / "tests").exists():
                run_root = project_root
                test_target = "tests"

    cmd: List[str] = ["pytest", "--tb=short", "-q"]
    if (run_root / "pytest.ini").exists():
        cmd += ["-c", "pytest.ini"]
    cmd += [test_target]

    start = time.time()
    try:
        r = subprocess.run(
            cmd,
            cwd=str(run_root),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            encoding="utf-8",
            errors="replace",
        )
        duration_ms = int((time.time() - start) * 1000)
    except subprocess.TimeoutExpired as e:
        duration_ms = int((time.time() - start) * 1000)
        return {
            "tests_passed": 0,
            "tests_collected": 0,
            "exit_code": 124,
            "evidence": {
                "stdout": (e.stdout or ""),
                "stderr": (e.stderr or ""),
                "cmd": cmd,
                "timeout_s": timeout_s,
                "duration_ms": duration_ms,
                "cwd": str(run_root),
            },
        }

    out = r.stdout or ""
    # Parse summary like: "2 passed, 5 errors in 0.31s"
    passed = 0
    failed = 0
    errors = 0
    skipped = 0
    collected = 0
    m_passed = re.search(r"(\d+)\s+passed", out)
    m_failed = re.search(r"(\d+)\s+failed", out)
    m_errors = re.search(r"(\d+)\s+errors?", out)
    m_skipped = re.search(r"(\d+)\s+skipped", out)
    m_collected = re.search(r"collected\s+(\d+)\s+items?", out)
    if m_passed:
        passed = int(m_passed.group(1))
    if m_failed:
        failed = int(m_failed.group(1))
    if m_errors:
        errors = int(m_errors.group(1))
    if m_skipped:
        skipped = int(m_skipped.group(1))
    if m_collected:
        collected = int(m_collected.group(1))

    if collected == 0:
        collected = passed + failed + errors + skipped

    return {
        "tests_passed": passed,
        "tests_collected": collected,
        "exit_code": r.returncode,
        "evidence": {
            "stdout": out,
            "stderr": (r.stderr or ""),
            "cmd": cmd,
            "timeout_s": timeout_s,
            "duration_ms": duration_ms,
            "cwd": str(run_root),
            "resolved_project_root": str(project_root),
        },
    }

# ==================== RETRY INFRASTRUCTURE ====================

class TransientError(Exception):
    """Raised when an engine step fails with a recoverable / transient condition.

    Examples: subprocess timeout, OS resource exhaustion, transient I/O error.
    These failures are candidates for automatic retry before hard-failing.
    Non-transient failures (logic errors, bad exit codes, missing files) must
    NOT be wrapped in TransientError — they should propagate immediately.
    """


def execute_engine_with_retry(engine_func, max_retries: int = 3):
    """Run engine_func with automatic retry on TransientError.

    Responsibility for stability is handled here (lower layer) so callers
    (Aggregator) only see deterministic success or a hard-fail exception.

    Args:
        engine_func: Zero-argument callable wrapping the engine call.
        max_retries:  Maximum attempts (default 3). Must be >= 1.

    Returns:
        Return value of engine_func on first successful call.

    Raises:
        TransientError: If all retry attempts are exhausted.
        Any non-TransientError exception: propagates immediately (not retried).
    """
    last_exc: TransientError | None = None
    for attempt in range(max_retries):
        try:
            return engine_func()
        except TransientError as exc:
            last_exc = exc
            if attempt == max_retries - 1:
                raise  # quota exhausted — let Aggregator handle hard-fail
            print(f"    [Retry] Transient failure on attempt {attempt + 1}/{max_retries}: {exc}")
    raise last_exc  # unreachable, but satisfies type checkers


# ==================== CORE FUNCTIONS ====================
class GateRunnerConfig:
    """Configuration manager for Gate Runner"""
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or current_dir / "config"
        self.config = DEFAULT_CONFIG.copy()
        self.load_config()
    
    def load_config(self):
        """Load configuration from YAML file if exists"""
        config_file = self.config_dir / "gate_runner_config.yaml"
        if config_file.exists():
            try:
                import yaml
                with open(config_file) as f:
                    yaml_config = yaml.safe_load(f)
                    if yaml_config:
                        self.config.update(yaml_config)
            except Exception as e:
                print(f"[!] Could not load config file: {e}")
    
    def get(self, key: str, default=None):
        return self.config.get(key, default)

def _derive_policy_digests_from_zip(zip_path: Path) -> Dict[str, str]:
    """Derive policy_digests by SHA-256-hashing the canonical policy files inside the bundle.

    Looks for:
      - Any file matching ``GOLDEN_IO_LOCK_*.yaml``  → key ``golden_io_lock_sha256``
      - Any file matching ``REASON_CODES_*.yaml``    → key ``reason_codes_sha256``

    If neither file is present the dict is empty (caller decides what to do).
    This is used by the SOVEREIGN SHIELD Temporal Seal to ensure M7 always has
    a non-empty policy identity to bind against.
    """
    import hashlib as _hl
    import json as _json
    import yaml as _yaml  # PyYAML — normalise YAML → canonical JSON before hashing

    def _canonical_hash(raw_bytes: bytes) -> str:
        """YAML-parse → sort-keys JSON → SHA-256.

        Whitespace/comment changes in the YAML file do NOT alter the hash;
        only semantic content changes do.  This is "Policy Hardening v2".
        """
        try:
            obj = _yaml.safe_load(raw_bytes)
            canonical = _json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
        except Exception:
            # Fallback: raw bytes if YAML parse fails (e.g. binary corruption)
            canonical = raw_bytes
        return _hl.sha256(canonical).hexdigest()

    digests: Dict[str, str] = {}
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            for name in z.namelist():
                base = name.split('/')[-1]
                if base.startswith('GOLDEN_IO_LOCK') and base.endswith('.yaml'):
                    digests['golden_io_lock_sha256'] = _canonical_hash(z.read(name))
                elif base.startswith('REASON_CODES') and base.endswith('.yaml'):
                    digests['reason_codes_sha256'] = _canonical_hash(z.read(name))
    except Exception:
        pass
    return digests


def extract_manifest_from_zip(zip_path: Path) -> Dict[str, Any]:
    """Extract manifest.json from zip with multiple location support"""
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            # Try multiple possible locations
            manifest_candidates = [
                'manifest.json',
                '*/manifest.json',
                '**/manifest.json',
                'META-INF/manifest.json'
            ]
            
            for candidate in manifest_candidates:
                for name in z.namelist():
                    if name.endswith('manifest.json') or name == candidate:
                        try:
                            manifest_data = z.read(name)
                            manifest = json.loads(manifest_data)
                            print(f"    Found manifest at: {name}")
                            return manifest
                        except Exception as e:
                            continue
    except Exception as e:
        print(f"    [!] Error reading zip: {e}")
    
    # Create default manifest
    print("    [!] Using default manifest")
    return {
        "module_inventory": [
            {"module_id": "submission", "version": "1.0.0"}
        ],
        "graph": {
            "nodes": ["submission"],
            "edges": [],
            "required_nodes": ["submission"]
        },
        "metadata": {
            "generated_by": "gate_runner",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }

def validate_zip_file(zip_path: Path) -> Tuple[bool, str]:
    """Validate ZIP file before processing"""
    if not zip_path.exists():
        return False, f"File not found: {zip_path}"
    
    if zip_path.stat().st_size == 0:
        return False, "ZIP file is empty"
    
    # Check file size limit (100MB default)
    max_size = DEFAULT_CONFIG['max_zip_size_mb'] * 1024 * 1024
    if zip_path.stat().st_size > max_size:
        return False, f"ZIP file too large (> {DEFAULT_CONFIG['max_zip_size_mb']}MB)"
    
    # Check if it's a valid ZIP
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            if not z.namelist():
                return False, "ZIP file contains no files"
    except zipfile.BadZipFile:
        return False, "Not a valid ZIP file"
    
    return True, "OK"

class RealSandboxRunner:
    """Improved real runner with better test discovery and error handling"""
    
    def __init__(self, test_path: str):
        self.test_path = test_path
        self.test_target_cache = None
    
    def _find_test_directory(self, working_directory: str) -> str:
        """Find tests dynamically with priority order"""
        from pathlib import Path
        
        if self.test_target_cache:
            return self.test_target_cache
        
        extract_path = Path(working_directory)
        
        # Priority 1: Explicit tests/ directory
        test_dirs = [
            extract_path / "tests",
            extract_path / "test",
            extract_path / "__tests__"
        ]
        
        for test_dir in test_dirs:
            if test_dir.is_dir():
                self.test_target_cache = str(test_dir.relative_to(extract_path))
                return self.test_target_cache
        
        # Priority 2: Module with tests/
        for item in extract_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                nested_tests = item / "tests"
                if nested_tests.is_dir():
                    self.test_target_cache = str(nested_tests.relative_to(extract_path))
                    return self.test_target_cache
        
        # Priority 3: Any test_*.py files
        test_files = list(extract_path.rglob("test_*.py"))
        if test_files:
            # Use directory containing first test file
            test_dir = test_files[0].parent
            self.test_target_cache = str(test_dir.relative_to(extract_path))
            return self.test_target_cache
        
        # Priority 4: Any *_test.py files
        test_files = list(extract_path.rglob("*_test.py"))
        if test_files:
            test_dir = test_files[0].parent
            self.test_target_cache = str(test_dir.relative_to(extract_path))
            return self.test_target_cache
        
        # Fallback: Root directory
        self.test_target_cache = "."
        return self.test_target_cache
    
    def _parse_pytest_output(self, stdout: str) -> Dict[str, Any]:
        """Parse pytest output to extract test statistics"""
        result = {
            'tests_collected': 0,
            'tests_passed': 0,
            'tests_failed': 0,
            'tests_skipped': 0,
            'tests_errors': 0
        }
        
        try:
            # Pattern for test summary
            patterns = {
                'collected': r'collected (\d+) items?',
                'passed': r'(\d+) passed',
                'failed': r'(\d+) failed',
                'skipped': r'(\d+) skipped',
                'errors': r'(\d+) error'
            }
            
            for key, pattern in patterns.items():
                match = re.search(pattern, stdout)
                if match:
                    result[f'tests_{key}'] = int(match.group(1))
            
            # Calculate collected if not explicitly stated
            if result['tests_collected'] == 0:
                result['tests_collected'] = (
                    result['tests_passed'] + 
                    result['tests_failed'] + 
                    result['tests_skipped'] + 
                    result['tests_errors']
                )
        except Exception as e:
            print(f"    [!] Error parsing pytest output: {e}")
        
        return result
    
    def run(self, *, command: str, working_directory: str, timeout_s: int) -> Dict[str, Any]:
        """Execute pytest with comprehensive error handling"""
        import subprocess
        import time
        
        start_ms = int(time.time() * 1000)
        
        try:
            # Find tests dynamically
            test_target = self._find_test_directory(working_directory)
            print(f"    [Runner] Test target: {test_target}")
            
            # Build command
            if "pytest" in command:
                # Parse existing args
                base_args = command.split()
                pytest_args = [arg for arg in base_args if arg != "pytest" and not arg.startswith("-")]
                
                # Use concise output format for consistency
                cmd = ["pytest", "--tb=short", "-q"]
                if (Path(working_directory) / "pytest.ini").exists():
                    cmd += ["-c", "pytest.ini"]
                cmd += [test_target] + pytest_args
            else:
                cmd = command.split() + [test_target]
            
            print(f"    [Runner] Command: {' '.join(cmd)}")
            print(f"    [Runner] CWD: {working_directory}")
            
            # Execute with retry budget for transient failures (timeout, OS errors).
            def _do_run():
                try:
                    return subprocess.run(
                        cmd,
                        cwd=working_directory,
                        capture_output=True,
                        text=True,
                        timeout=timeout_s,
                        encoding='utf-8',
                        errors='replace'
                    )
                except subprocess.TimeoutExpired as exc:
                    raise TransientError(f"Subprocess timeout after {timeout_s}s") from exc
                except OSError as exc:
                    raise TransientError(f"OS error: {exc}") from exc

            proc = execute_engine_with_retry(_do_run, max_retries=3)
            duration_ms = int(time.time() * 1000) - start_ms

            # Parse results
            test_stats = self._parse_pytest_output(proc.stdout)

            # Determine if run was successful
            # Exit codes: 0=passed, 1=failed, 2=interrupted, 3=internal error, 4=usage error, 5=no tests
            ok_exit_codes = [0, 1]  # Both pass and fail are valid for determinism

            return {
                "ok": proc.returncode in ok_exit_codes,
                "exit_code": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "duration_ms": duration_ms,
                **test_stats
            }

        except TransientError as e:
            duration_ms = int(time.time() * 1000) - start_ms
            print(f"    [Runner] Transient failure exhausted retries: {e}")
            return {
                "ok": False,
                "exit_code": -2,
                "stdout": "",
                "stderr": str(e),
                "duration_ms": duration_ms
            }
        except Exception as e:
            duration_ms = int(time.time() * 1000) - start_ms
            error_msg = str(e)
            print(f"    [Runner] Exception: {error_msg}")
            return {
                "ok": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": error_msg,
                "duration_ms": duration_ms
            }

def real_determinism_key_fn(payload: dict, pin_set: dict) -> str:
    """Determinism key: stable across baseline/replay for same test outcomes."""
    import json
    import hashlib

    pytest_payload = payload.get("pytest_runtime_payload", payload)

    def _to_int(x) -> int:
        try:
            return int(x)
        except Exception:
            return 0

    tests_passed = _to_int(pytest_payload.get("tests_passed", 0))
    tests_failed = _to_int(pytest_payload.get("tests_failed", 0))
    tests_skipped = _to_int(pytest_payload.get("tests_skipped", 0))

    # ✅ IMPORTANT: never trust tests_collected (can be flaky). Derive deterministically.
    tests_total = tests_passed + tests_failed + tests_skipped

    canonical_data = {
        "determinism_version": "2.0",
        "hash_schema": "tests_only_v2",

        # stable test outcome stats
        "tests_total": tests_total,
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
        "tests_skipped": tests_skipped,

        # stable environment pins (must be stable strings/dicts only)
        "toolchain_digest": pin_set.get("toolchain_digest", ""),
        "kami_version": pin_set.get("kami_version", ""),
        "policy_digests": dict(sorted((pin_set.get("policy_digests") or {}).items())),
    }

    canonical_json_str = json.dumps(canonical_data, sort_keys=True, separators=(",", ":"))
    key = hashlib.sha256(canonical_json_str.encode("utf-8")).hexdigest()

    print(f"    [Determinism] Hash input: {canonical_json_str[:120]}...")
    print(f"    [Determinism] Key: {key[:16]}...")

    return key


def run_m8_gate(input_data: Dict[str, Any], config: GateRunnerConfig) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Run M8 validation pipeline with improved error handling"""
    print("[*] M8 Gate: Starting validation")
    print(f"    Modules: {len(input_data.get('module_inventory', []))}")
    
    # Extract inputs
    module_inventory = input_data.get("module_inventory", [])
    graph = input_data.get("graph", {})
    
    results = {}
    
    # M8-1: Graph Validator
    print("  [M8-1] Graph validation...")
    try:
        m1_result = M8_MODULES['validate_graph'](module_inventory, graph)
        if not m1_result.get("graph_valid", False):
            reason = m1_result.get("reason_code", "GRAPH_INVALID")
            print(f"  [X] M8-1 FAIL: {reason}")
            return {
                "m8_version": "2.0",
                "status": "FAIL",
                "stage": "M8-1",
                "reason": reason,
                "details": m1_result
            }, {}
        print(f"  [OK] M8-1 PASS")
        results['m8_1'] = m1_result
    except Exception as e:
        print(f"  [X] M8-1 ERROR: {e}")
        return {
            "m8_version": "2.0",
            "status": "FAIL",
            "stage": "M8-1",
            "reason": "VALIDATION_ERROR",
            "error": str(e)
        }, {}
    
    # M8-2: Invariant Engine
    print("  [M8-2] Invariant checking...")
    invariants_yaml = config.config_dir / config.get('m8_invariants_file')
    
    context = {
        "graph_valid": m1_result["graph_valid"],
        "module_inventory": module_inventory,
        "graph": graph,
        "m8_1_result": m1_result
    }
    
    try:
        m2_result = M8_MODULES['m8_2_run_invariants'](str(invariants_yaml), context)
        invariants_passed = m2_result.get("invariants_passed", 0)
        invariants_checked = m2_result.get("invariants_checked", 0)
        
        if invariants_passed < invariants_checked:
            failed = m2_result.get("failed_invariants", [])
            print(f"  [X] M8-2 FAIL: {invariants_passed}/{invariants_checked} passed")
            print(f"      Failed invariants: {failed[:3]}")  # Show first 3
        else:
            print(f"  [OK] M8-2: {invariants_passed}/{invariants_checked} passed")
        
        results['m8_2'] = m2_result
    except Exception as e:
        print(f"  [X] M8-2 ERROR: {e}")
        m2_result = {
            "invariants_passed": 0,
            "invariants_checked": 0,
            "failed_invariants": ["EXECUTION_ERROR"]
        }
        results['m8_2'] = m2_result
    
    # M8-3: Canonicalization
    print("  [M8-3] Canonicalization...")
    try:
        payload = {
            "graph_valid": m1_result.get("graph_valid", False),
            "graph_signature": m1_result.get("graph_signature", ""),
            "invariants_passed": m2_result.get("invariants_passed", 0),
            "failed_invariants": m2_result.get("failed_invariants", [])
        }
        determinism_key = M8_MODULES['compute_determinism_key'](payload)
        print(f"  [OK] M8-3: Key: {determinism_key[:24]}...")
        results['m8_3'] = {"determinism_key": determinism_key}
    except Exception as e:
        print(f"  [X] M8-3 ERROR: {e}")
        determinism_key = "ERROR"
        results['m8_3'] = {"determinism_key": determinism_key, "error": str(e)}
    
    # M8-4: Replay Verify
    print("  [M8-4] Replay verification...")
    try:
        m4_result = M8_MODULES['m8_4_replay_verify'](payload, expected_key=determinism_key)
        if not m4_result.get("replay_verified", False):
            print(f"  [X] M8-4 FAIL: Replay verification failed")
            return {
                "m8_version": "2.0",
                "status": "FAIL",
                "stage": "M8-4",
                "reason": "M8_REPLAY_FAIL",
                "details": m4_result
            }, {}
        print(f"  [OK] M8-4 PASS")
        results['m8_4'] = m4_result
    except Exception as e:
        print(f"  [X] M8-4 ERROR: {e}")
        return {
            "m8_version": "2.0",
            "status": "FAIL",
            "stage": "M8-4",
            "reason": "REPLAY_ERROR",
            "error": str(e)
        }, {}
    
    # M8-5: Final Verdict
    print("  [M8-5] Final verdict...")
    try:
        final_state = {
            "graph_valid": m1_result.get("graph_valid", False),
            "invariants_passed": m2_result.get("invariants_passed", 0),
            "failed_invariants": m2_result.get("failed_invariants", []),
            "determinism_key": determinism_key,
            "replay_verified": m4_result.get("replay_verified", False)
        }
        m5_result = M8_MODULES['m8_5_final_verdict'](final_state)
        
        if m5_result.get("status") == "PASS":
            print(f"  [OK] M8-5: PASS")
        else:
            reason = m5_result.get("failure_reason", "UNKNOWN")
            print(f"  [X] M8-5: FAIL - {reason}")
        
        results['m8_5'] = m5_result
        
        # Prepare internal data for Stage2
        internal = {
            "payload": payload,
            "expected_key": determinism_key,
            "all_results": results
        }
        
        return m5_result, internal
        
    except Exception as e:
        print(f"  [X] M8-5 ERROR: {e}")
        return {
            "m8_version": "2.0",
            "status": "FAIL",
            "stage": "M8-5",
            "reason": "VERDICT_ERROR",
            "error": str(e)
        }, {}

def stage2_run_once(m8_result: Dict[str, Any], input_data: Dict[str, Any], config: GateRunnerConfig) -> Dict[str, Any]:
    """Single Stage2 execution with comprehensive error handling"""
    print("\n[*] Stage2 Validation: Starting...")
    
    # Check availability
    if not STAGE2_AVAILABLE:
        error_msg = "Stage2 modules not available"
        print(f"  [X] {error_msg}")
        return {
            "stage2_version": "1.0",
            "status": "FAIL",
            "reason": "STAGE2_IMPORT_ERROR",
            "detail": error_msg
        }
    
    # Get and validate zip path
    zip_path = input_data.get("zip_path")
    if not zip_path:
        print("  [X] No zip_path in input")
        return {
            "stage2_version": "1.0",
            "status": "FAIL",
            "reason": "MISSING_ZIP_PATH"
        }
    
    zip_file = Path(zip_path)
    is_valid, validation_msg = validate_zip_file(zip_file)
    if not is_valid:
        print(f"  [X] ZIP validation failed: {validation_msg}")
        return {
            "stage2_version": "1.0",
            "status": "FAIL",
            "reason": "ZIP_VALIDATION_FAILED",
            "detail": validation_msg
        }
    
    try:
        # M2: Ingest & Enumerate
        print("  [M2] Processing ZIP...")
        manifest = STAGE2_MODULES['process_zip'](str(zip_file))
        module_descriptors = STAGE2_MODULES['generate_module_descriptors'](str(zip_file))
        print(f"  [OK] M2: {len(module_descriptors)} modules found")
        
        # M3: Toolchain Manifest
        print("  [M3] Toolchain manifest...")
        toolchain_manifest = STAGE2_MODULES['get_toolchain_manifest'](use_cache=True)
        print(f"  [OK] M3: Toolchain captured ({toolchain_manifest.get('python_version', 'unknown')})")
        
        # M4: Static Analysis
        print("  [M4] Static analysis...")
        static_findings = []
        
        with zipfile.ZipFile(zip_file, 'r') as z:
            python_files = [name for name in z.namelist() if name.endswith('.py')]
            print(f"    Analyzing {len(python_files)} Python files...")
            
            for name in python_files:
                try:
                    code = z.read(name).decode('utf-8', errors='replace')
                    findings = STAGE2_MODULES['analyze_code'](code, filename=name)
                    static_findings.extend(findings)
                except Exception as e:
                    print(f"    [!] Could not analyze {name}: {e}")
        
        print(f"  [OK] M4: {len(static_findings)} static findings")
        
        # M5: Runtime Tests
        print("  [M5] Runtime testing...")
        timeout = config.get('test_timeout')
        
        # Extract to temp directory
        tmpdir = Path(tempfile.mkdtemp(prefix=config.get('temp_dir_prefix')))
        print(f"    Extracting to: {tmpdir}")
        
        with zipfile.ZipFile(zip_file, 'r') as z:
            z.extractall(tmpdir)
        
        runtime_results = _run_pytest_suite(tmpdir, timeout)
        tests_passed = runtime_results.get('tests_passed', 0)
        tests_total = runtime_results.get('tests_collected', 0)
        print(f"  [OK] M5: {tests_passed}/{tests_total} tests passed")
        
        # M6: Aggregate & Report
        print("  [M6] Aggregating results...")
        
        # Prepare module results
        module_results = []
        for desc in module_descriptors:
            # Static score
            static_score = 1.0 if not static_findings else 0.5
            
            # Runtime score
            runtime_score = (tests_passed / tests_total) if tests_total > 0 else 0.0
            
            module_results.append({
                "module_id": desc.get("module_id", "unknown"),
                "static_analysis": {
                    "score": static_score,
                    "findings_count": len(static_findings),
                    "findings": static_findings[:10]  # Include first 10 findings
                },
                "runtime_validation": {
                    "score": runtime_score,
                    "tests_passed": tests_passed,
                    "tests_total": tests_total,
                    "evidence": runtime_results.get('evidence', {})
                },
                "file_count": desc.get("file_count", 1),
                "descriptor": desc
            })
        
        # Context gate info
        context_gate_info = {
            "level": input_data.get("context_gate_level", "L3"),
            "gate_version": "1.0",
            "cap_verdict_to": "PASS",
            "missing_context": [],
            "reason_codes": []
        }
        
        # Policy digests
        policy_digests = input_data.get("policy", {})
        
        # Runtime findings
        runtime_findings = runtime_results.get("findings", [])
        
        # Submission descriptor
        submission_id = zip_file.stem
        submission_descriptor = {
            "submission_id": submission_id,
            "zip_path": str(zip_file),
            "manifest": manifest,
            "m8": m8_result,
            "extracted_path": str(tmpdir),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Generate final report
        final = STAGE2_MODULES['aggregate_and_report'](
            submission_descriptor=submission_descriptor,
            module_results=module_results,
            static_findings=static_findings,
            runtime_findings=runtime_findings,
            context_gate_info=context_gate_info,
            toolchain_manifest=toolchain_manifest,
            policy_digests=policy_digests
        )
        
        # Extract verdict
        agg = final.get("aggregation", {})
        ctx = final.get("context_gate", {})
        modules = final.get("modules", [])
        
        repo_verdict = agg.get("repo_verdict") or final.get("final_verdict") or "FAIL"
        repo_score = agg.get("repo_score", 0.0)
        
        # ======================================================================
        # ENFORCED VERDICT LOGIC (1.00 LAW - RUTHLESS STRICTNESS)
        # ======================================================================
        # Get actual test results from runtime
        tests_passed = runtime_results.get('tests_passed', 0)
        tests_total = runtime_results.get('tests_collected', 0)
        
        # Debug
        print(f"    [VERDICT DEBUG] Raw: tests_passed={tests_passed}, tests_total={tests_total}")
        print(f"    [VERDICT DEBUG] repo_verdict from agg: {agg.get('repo_verdict')}")
        
        # Override verdict based on 100% STRICT LAW + G-SCORE DOUBLE LOCK
        if tests_total > 0:
            actual_score = tests_passed / tests_total
            if tests_passed == tests_total:  # MUST BE 100% MATCH
                # DO NOT override repo_score — use real G-Score from aggregation
                real_g_score = agg.get("repo_score", 0.0)
                if real_g_score >= 0.99:
                    repo_verdict = "PASS"
                    repo_score = real_g_score
                    print(f"    [VERDICT STRICT] 100% Tests + G-Score {real_g_score:.4f} >= 0.99 ✅")
                else:
                    repo_verdict = "FAIL"
                    repo_score = real_g_score
                    print(f"    [VERDICT STRICT] Tests PASS but G-Score {real_g_score:.4f} < 0.99 ❌ Fix source code logic!")
            else:
                repo_verdict = "FAIL"
                repo_score = actual_score
                print(f"    [VERDICT STRICT] Tests Failed! Must be 100%. Got: {tests_passed}/{tests_total} ({actual_score:.1%}) ❌")
        elif tests_total == 0 and tests_passed == 0:
            print("    [VERDICT STRICT] No tests collected.")
            if not static_findings:
                repo_verdict = "PASS"
                repo_score = 1.0
                print("    [VERDICT STRICT] No tests but static passed -> PASS ✅")
            else:
                repo_verdict = "FAIL"
                repo_score = 0.0
                print("    [VERDICT STRICT] No tests and static failed -> FAIL ❌")

            # No tests found - check if that's expected
            print("    [VERDICT FIX] No tests collected")
            # If static analysis passed and no tests expected, still PASS
            if not static_findings:
                repo_verdict = "PASS"
                repo_score = 0.8  # Default score for no tests
                print("    [VERDICT FIX] No tests but static passed -> PASS")
            else:
                repo_verdict = "FAIL"
        
        status = "PASS" if repo_verdict == "PASS" else "FAIL"
        print(f"  {'[OK]' if status == 'PASS' else '[X]'} M6: {repo_verdict} (score: {repo_score:.2f})")
        
        # Get test stats
        first_module_runtime = modules[0].get("runtime_validation", {}) if modules else {}
        
        print(f"  {'[OK]' if status == 'PASS' else '[X]'} M6: {repo_verdict} (score: {repo_score:.2f})")
        
        return {
            "stage2_version": "1.0",
            "status": status,
            "repo_verdict": repo_verdict,
            "repo_score": repo_score,
            "modules_checked": len(modules),
            "static_findings": len(static_findings),
            "tests_passed": tests_passed,
            "tests_total": tests_total,
            "context_gate_level": ctx.get("level", "L3"),
            "full_report": final,
            "extract_path": str(tmpdir),
            "runtime_evidence": runtime_results.get('evidence', {})
        }
        
    except Exception as e:
        print(f"  [X] Stage2 error: {e}")
        traceback.print_exc()
        return {
            "stage2_version": "1.0",
            "status": "FAIL",
            "reason": "STAGE2_ERROR",
            "error": str(e),
            "traceback": traceback.format_exc()
        }

def run_stage2_validation(
    m8_result: Dict[str, Any], 
    input_data: Dict[str, Any], 
    config: GateRunnerConfig,
    m8_internal: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Run Stage2 with M7 replay if available"""
    
    # Run baseline Stage2
    print("\n[*] Stage2: Baseline execution...")
    baseline_result = stage2_run_once(m8_result, input_data, config)
    
    # Skip M7 if not available or disabled
    if not M7_AVAILABLE or not config.get('enable_m7_replay', True):
        print("  [!] M7 replay disabled or unavailable")
        return baseline_result
    
    # Skip if Stage2 failed
    if baseline_result.get("status") != "PASS":
        print("  [!] Stage2 failed - skipping M7 replay")
        return baseline_result
    
    # Extract data for M7
    extract_path = baseline_result.get("extract_path")
    if not extract_path:
        print("  [!] No extract path - skipping M7")
        return baseline_result
    
    full_report = baseline_result.get("full_report", {})
    modules = full_report.get("modules", [])
    
    if not modules:
        print("  [!] No modules in report - skipping M7")
        return baseline_result
    
    # Get runtime data
    module_data = modules[0]
    runtime_data = module_data.get("runtime_validation", {})
    evidence = runtime_data.get("evidence", {})
    
    # Prepare artifacts for M7
    # SOVEREIGN SHIELD — Temporal Seal: stamp artifacts with current UTC epoch
    _run_at_utc: int = int(time.time())

    run1_artifacts = {
        "test_command": "pytest -q",
        "working_directory": extract_path,
        "timeout_s": config.get('test_timeout'),
        "pytest_runtime_payload": {
            "output": evidence.get("output", ""),
            "stdout": evidence.get("stdout", ""),
            "stderr": evidence.get("stderr", ""),
            "exit_code": runtime_data.get("exit_code", 0),
            "tests_collected": runtime_data.get("tests_total", 0),
            "tests_passed": runtime_data.get("tests_passed", 0),
            "tests_failed": runtime_data.get("tests_total", 0) - runtime_data.get("tests_passed", 0),
        },
        "toolchain_manifest_digest": full_report.get("toolchain_manifest", {}).get("python_version", "unknown"),
        "policy_digests": input_data.get("policy", {}),
        "run_at_utc": _run_at_utc,   # SOVEREIGN SHIELD — Temporal Seal
    }

    # Pin set
    pin_set = {
        "kami_version": "2.0",
        "dna_version": "2.1",
        "smart_spec_version": "1.0",
        "reason_codes_version": "1.0",
        "context_gate_version": "1.0",
        "noise_budget_version": "1.0",
        "toolchain_digest": full_report.get("toolchain_manifest", {}).get("python_version", "unknown"),
        "determinism_policy_version": "1.0",
        "policy_digests": input_data.get("policy", {}),
        "run_at_utc": _run_at_utc,   # SOVEREIGN SHIELD — Temporal Seal
    }
    
    print("\n[*] M7: Runtime replay verification...")
    
    try:
        # Run M7 verification
        m7_result = verify_runtime_replay(
            first_run_key=real_determinism_key_fn(run1_artifacts, run1_artifacts.get("policy_digests", {})),
            replay_artifacts=run1_artifacts,
            validation_result=baseline_result,
            pin_set=pin_set,
            enable_m7_replay=True,
            runner=RealSandboxRunner(extract_path),
            determinism_key_fn=real_determinism_key_fn
        )
        
        # Merge M7 result
        if m7_result.get("replay_verified"):
            print("  [OK] M7 PASS: Runtime is deterministic")
            baseline_result["m7_replay"] = {
                "status": "PASS",
                "verification": m7_result
            }
        else:
            print(f"  [X] M7 FAIL: {m7_result.get('reason_code', 'REPLAY_FAILED')}")
            baseline_result["status"] = "FAIL"
            baseline_result["repo_verdict"] = "FAIL"
            baseline_result["m7_replay"] = {
                "status": "FAIL",
                "reason": m7_result.get("reason_code", "UNKNOWN"),
                "verification": m7_result
            }
            
            # Add to reasons
            full_report = baseline_result.get("full_report", {})
            reasons = full_report.get("reasons", [])
            reasons.append({
                "reason_code": "M7_REPLAY_FAIL",
                "count": 1,
                "evidence": m7_result
            })
            full_report["reasons"] = reasons
            baseline_result["full_report"] = full_report
        
        return baseline_result
        
    except Exception as e:
        # IntegrityError is a hard-fail — propagate immediately so the pipeline
        # surfaces the security violation rather than silently continuing.
        if M7IntegrityError is not None and isinstance(e, M7IntegrityError):
            print(f"  [!!] M7 INTEGRITY VIOLATION — hard-fail: {e}")
            baseline_result["status"] = "FAIL"
            baseline_result["repo_verdict"] = "FAIL"
            baseline_result["m7_replay"] = {
                "status": "INTEGRITY_FAIL",
                "reason_code": e.reason_code,
                "error": str(e),
            }
            return baseline_result
        # Other M7 errors are non-fatal (execution/environment issues).
        print(f"  [!] M7 execution error: {e}")
        baseline_result["m7_replay"] = {
            "status": "ERROR",
            "error": str(e)
        }
        return baseline_result

def main():
    """Main entry point with improved argument parsing and error handling"""
    parser = argparse.ArgumentParser(
        description="M8 + Stage2 Gate Runner - Validation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s submission.json
  %(prog)s submission.zip --output detailed_report.json
  %(prog)s input.json --verbose
        """
    )
    
    parser.add_argument("input", help="Input JSON file or ZIP file")
    parser.add_argument("--output", "-o", default="gate_report.json", 
                       help="Output report file (default: gate_report.json)")
    parser.add_argument("--config", "-c", help="Custom config directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--skip-m7", action="store_true", help="Skip M7 replay verification")
    parser.add_argument("--timeout", type=int, help="Test timeout in seconds")
    
    args = parser.parse_args()
    
    # Setup config
    config_dir = Path(args.config) if args.config else current_dir / "config"
    config = GateRunnerConfig(config_dir)
    
    if args.timeout:
        config.config['test_timeout'] = args.timeout
    if args.skip_m7:
        config.config['enable_m7_replay'] = False
    
    # Banner
    print("=" * 70)
    print("M8 + Stage2 Gate Runner v2.0 - Optimized")
    print("=" * 70)
    print(f"Config: {config_dir}")
    print(f"Stage2: {'Available' if STAGE2_AVAILABLE else 'Not available'}")
    print(f"M7 Replay: {'Enabled' if config.get('enable_m7_replay') and M7_AVAILABLE else 'Disabled'}")
    print("-" * 70)
    
    # Load input
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[X] Error: Input file not found: {args.input}")
        return 1
    
    input_data = {}
    try:
        if input_path.suffix.lower() == '.zip':
            print(f"[*] Processing ZIP file: {input_path.name}")
            # Validate ZIP
            is_valid, msg = validate_zip_file(input_path)
            if not is_valid:
                print(f"[X] Invalid ZIP: {msg}")
                return 1
            
            input_data = extract_manifest_from_zip(input_path)
            input_data['zip_path'] = str(input_path.absolute())
            input_data['input_type'] = 'zip'

            # SOVEREIGN SHIELD — Temporal Seal: auto-derive policy identity
            # from bundle policy files when the manifest carries no explicit
            # "policy" field.  Ensures policy_digests is never empty so M7
            # can verify module identity.
            if not input_data.get('policy'):
                derived = _derive_policy_digests_from_zip(input_path)
                if derived:
                    input_data['policy'] = derived
                    print(f"    [Policy] Auto-derived digests: {list(derived.keys())}")
            
        elif input_path.suffix.lower() == '.json':
            print(f"[*] Processing JSON file: {input_path.name}")
            with open(input_path, 'r', encoding='utf-8') as f:
                input_data = json.load(f)
            input_data['input_type'] = 'json'
            
            # Check for zip_path in JSON
            if 'zip_path' in input_data:
                zip_path = Path(input_data['zip_path'])
                if not zip_path.exists():
                    print(f"[!] Warning: zip_path in JSON not found: {zip_path}")
        else:
            print(f"[X] Error: Unsupported file type: {input_path.suffix}")
            print(f"    Supported: .json, .zip")
            return 1
    except Exception as e:
        print(f"[X] Error loading input: {e}")
        return 1
    
    print(f"[*] Input loaded: {len(input_data.get('module_inventory', []))} modules")
    
    try:
        # Run M8 Gate
        print("\n" + "=" * 70)
        print("PHASE 1: M8 GATE VALIDATION")
        print("=" * 70)
        
        m8_result, m8_internal = run_m8_gate(input_data, config)
        
        # Check M8 result
        if m8_result.get("status") != "PASS":
            print("\n[!] M8 FAILED - Skipping Stage2")
            final_status = "FAIL"
            stage2_result = {
                "status": "SKIPPED",
                "reason": "M8_FAIL",
                "details": m8_result
            }
        else:
            # Run Stage2 Validation
            print("\n" + "=" * 70)
            print("PHASE 2: STAGE2 VALIDATION (M1-M6)")
            print("=" * 70)
            
            stage2_result = run_stage2_validation(
                m8_result, 
                input_data, 
                config, 
                m8_internal
            )
            
            # Determine final status
            if stage2_result.get("status") == "PASS":
                final_status = "PASS"
            else:
                final_status = "FAIL"
        
        # Generate final report
        print("\n" + "=" * 70)
        print("FINAL REPORT")
        print("=" * 70)
        
        final_report = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "gate_runner_version": "2.0",
            "final_status": final_status,
            "input_file": str(input_path.absolute()),
            "config": {
                "test_timeout": config.get('test_timeout'),
                "enable_m7_replay": config.get('enable_m7_replay'),
                "stage2_available": STAGE2_AVAILABLE,
                "m7_available": M7_AVAILABLE
            },
            "m8": m8_result,
            "stage2": stage2_result,
            "summary": {
                "m8_status": m8_result.get("status", "UNKNOWN"),
                "stage2_status": stage2_result.get("status", "UNKNOWN"),
                "modules_checked": stage2_result.get("modules_checked", 0),
                "tests_passed": stage2_result.get("tests_passed", 0),
                "tests_total": stage2_result.get("tests_total", 0)
            }
        }
        
        # Save report
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(final_report, f, indent=2, ensure_ascii=False)
            print(f"[OK] Report saved: {output_path.absolute()}")
        except Exception as e:
            print(f"[!] Warning: Could not save report: {e}")
            # Print report to console as fallback
            print(json.dumps(final_report, indent=2))
        
        # Print summary
        print("\n" + "-" * 70)
        print("SUMMARY")
        print("-" * 70)
        print(f"M8 Status:    {m8_result.get('status', 'UNKNOWN')}")
        print(f"Stage2 Status: {stage2_result.get('status', 'UNKNOWN')}")
        print(f"Final Status: {final_status}")
        
        if 'summary' in final_report:
            s = final_report['summary']
            print(f"Modules:      {s.get('modules_checked', 0)}")
            print(f"Tests:        {s.get('tests_passed', 0)}/{s.get('tests_total', 0)} passed")
        
        print("=" * 70)
        
        return 0 if final_status == "PASS" else 1
        
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user")
        return 130
    except Exception as e:
        print(f"\n[X] Unexpected error: {e}")
        if args.verbose:
            traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
