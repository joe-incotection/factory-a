#!/usr/bin/env python3
"""
Gate C Runner - Production Grade
=================================

Usage:
    python gate_c_runner.py MODULE.zip

Features:
- Extract and validate module structure
- Import module dynamically
- Run module with mock data
- Build decision receipt from output
- Validate with Gate C
- Generate detailed report

Supports:
- GIM_Golden.zip
- BrainRouter_Golden.zip
- VAPD_Golden.zip
- Any module with backend/config structure
"""
import sys
import os
import json
import argparse
import csv
import zipfile
import shutil
import importlib.util
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from unittest.mock import patch, MagicMock

# Import Gate C
from gate_c import GateC, GateCError
from canonical_json import canonical_json
from gate_c import sha256_hex


class GateCRunner:
    """Production Gate C Runner"""
    
    def __init__(self, work_dir: str = "/tmp/gate_c_runner"):
        """
        Initialize runner
        
        Args:
            work_dir: Working directory for extraction
        """
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
        self.extract_dir = None
        self.module_name = None
        self.module = None
        self.gate_c = GateC()
        
        self.report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stages": [],
            "status": "UNKNOWN"
        }
    
    def run(self, module_zip_path: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {"module_zip": module_zip_path, "status": "FAIL", "error": "", "receipt": None, "receipt_path": "", "report_path": ""}
        """
        Run complete Gate C validation flow
        
        Args:
            module_zip_path: Path to module zip file
            
        Returns:
            Validation report
        """
        print("\n" + "="*60)
        print("Gate C Runner - Production")
        print("="*60)
        print(f"Module: {module_zip_path}")
        print(f"Timestamp: {self.report['timestamp']}")
        
        try:
            # Stage 1: Extract
            print("\n[Stage 1/6] Extracting module...")
            self._extract_module(module_zip_path)
            self._log_stage("Extract", "PASS")
            
            # Stage 2: Validate structure
            print("[Stage 2/6] Validating structure...")
            self._validate_structure()
            self._log_stage("Structure", "PASS")
            
            # Stage 3: Run module
            print("[Stage 3/6] Running module...")
            module_output = self._run_module()
            self._log_stage("Module Run", "PASS", module_output)
            
            # Stage 4: Build receipt
            print("[Stage 4/6] Building decision receipt...")
            # Clean module output for JSON serialization
            clean_output = self._clean_for_json(module_output)
            receipt = self._build_receipt(clean_output, module_output)
            result["receipt"] = receipt
            self._log_stage("Build Receipt", "PASS", {
                "decision_id": receipt['decision_id'],
                "receipt_hash": receipt['hashes']['receipt_hash'][:16] + "..."
            })
            
            # Stage 5: Validate with Gate C
            print("[Stage 5/6] Validating with Gate C...")
            self._validate_receipt(receipt)
            self._log_stage("Gate C Validation", "PASS")
            
            # Stage 6: Replay + Write-once
            print("[Stage 6/6] Replay + Write-once...")
            self._replay_and_persist(receipt, clean_output, module_output)
            self._log_stage("Replay + Write-once", "PASS")
            
            # Success
            self.report["status"] = "PASS"
            self.report["receipt"] = receipt
            
            print("\n" + "="*60)
            print("✅ Gate C Validation: PASS")
            print("="*60)
            
            return self.report
            
        except Exception as e:
            print(f"\n❌ Gate C Validation: FAIL")
            print(f"Error: {e}")
            result["error"] = str(e)
            
            self.report["status"] = "FAIL"
            self.report["error"] = str(e)
            
            if hasattr(e, 'reason_code'):
                self.report["reason_code"] = e.reason_code
            
            return self.report
        
        finally:
            self._save_report()
    
    def _extract_module(self, module_zip_path: str):
        """Extract module zip"""
        if not Path(module_zip_path).exists():
            raise FileNotFoundError(f"Module zip not found: {module_zip_path}")
        
        self.module_name = Path(module_zip_path).stem
        self.extract_dir = self.work_dir / self.module_name
        
        # Clean previous extraction
        if self.extract_dir.exists():
            shutil.rmtree(self.extract_dir)
        
        # Extract
        with zipfile.ZipFile(module_zip_path, 'r') as zf:
            zf.extractall(self.extract_dir)
        
        print(f"  ✅ Extracted to: {self.extract_dir}")
        
        # Add to Python path
        sys.path.insert(0, str(self.extract_dir))
    
    def _validate_structure(self):
        """Validate module structure"""
        required = ['backend', 'config']
        missing = []
        
        for item in required:
            if not (self.extract_dir / item).exists():
                missing.append(item)
        
        if missing:
            raise FileNotFoundError(f"Missing required directories: {missing}")
        
        print(f"  ✅ Structure valid: backend/ config/")
    
    def _run_module(self) -> Dict[str, Any]:
        """
        Run module and capture output
        
        Returns:
            Module output
        """
        # Find module file - check multiple locations
        search_paths = [
            self.extract_dir / "backend" / "modules",
            self.extract_dir / "backend" / "router",  # สำหรับ BrainRouter
            self.extract_dir / "backend",
            self.extract_dir / "src",
            self.extract_dir
        ]
        
        module_files = []
        for path in search_paths:
            if path.exists():
                files = list(path.glob("*.py"))
                files = [f for f in files if f.name != "__init__.py"]
                if files:
                    module_files = files
                    print(f"  Found modules in: {path.relative_to(self.extract_dir)}")
                    break
        
        if not module_files:
            raise FileNotFoundError(f"No module file found in any of: {[str(p.relative_to(self.extract_dir)) for p in search_paths]}")
        
        module_file = module_files[0]
        print(f"  Module file: {module_file.name}")
        
        # Import module dynamically
        spec = importlib.util.spec_from_file_location("target_module", module_file)
        target_module = importlib.util.module_from_spec(spec)
        sys.modules['target_module'] = target_module
        spec.loader.exec_module(target_module)
        
        # Find main class (improved filtering)
        classes = []
        # ให้ priority สูงสุดกับ class ที่ชื่อตรงกับ module
        module_base_name = module_file.stem.replace('_', '').lower()  # brain_router -> brainrouter
        
        keywords_priority = ['Monitor', 'Router', 'Validator', 'Manager', 'Processor', 'Deviation', 'Adjustment']
        
        for name, obj in vars(target_module).items():
            if not isinstance(obj, type):
                continue
            if name.startswith('_'):
                continue
            
            # Skip built-in types and imports from other modules
            if obj.__module__ != target_module.__name__:
                continue
            
            # Skip Exception classes
            try:
                if issubclass(obj, Exception):
                    continue
            except TypeError:
                continue
            
            # Skip Config/Dataclass types
            if 'Config' in name or 'Settings' in name:
                continue
            
            # Highest priority: exact match with module name
            priority = 0
            if name.lower().replace('_', '') == module_base_name:
                priority = 100
            else:
                # Prioritize classes with specific keywords
                for keyword in keywords_priority:
                    if keyword in name:
                        priority = keywords_priority.index(keyword) + 1
                        break
            
            classes.append((priority, name, obj))
        
        if not classes:
            raise ValueError(f"No suitable class found in module {module_file.name}")
        
        # Sort by priority (higher priority first)
        classes.sort(key=lambda x: -x[0])
        
        main_class = classes[0][2]
        print(f"  Main class: {main_class.__name__}")
        
        # Mock external dependencies if needed
        mock_context = self._noop()
        try:
            module_content = module_file.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            try:
                module_content = module_file.read_text(encoding='latin-1')
            except:
                module_content = ""
        
        if 'yfinance' in module_content:
            import pandas as pd
            mock_yf = MagicMock()
            mock_yf.download = MagicMock(return_value=pd.DataFrame())
            mock_context = patch.dict('sys.modules', {'yfinance': mock_yf})
        
        with mock_context:
            # Instantiate
            instance = main_class()
            
            # Run with appropriate method and arguments
            if hasattr(instance, 'run'):
                # Check if run() requires arguments (like BrainRouter)
                import inspect
                sig = inspect.signature(instance.run)
                params = list(sig.parameters.keys())
                
                if len(params) > 0:
                    # Module requires arguments - create mock inputs
                    print(f"  Module requires arguments: {params}")
                    module_id = self.module_name.lower().replace('_golden', '')
                    mock_inputs = self._create_mock_inputs(params, module_id)
                    result = instance.run(**mock_inputs)
                else:
                    result = instance.run()
            elif hasattr(instance, 'execute'):
                result = instance.execute()
            else:
                raise ValueError("Module has no run() or execute() method")
        
        print(f"  ✅ Module executed successfully")
        
        return result
    
    def _create_mock_inputs(self, params: list, module_id: str) -> Dict[str, Any]:
        """
        Create mock inputs for modules that require arguments
        
        Args:
            params: List of parameter names
            module_id: Module identifier
            
        Returns:
            Dictionary of mock inputs
        """
        mock_inputs = {}
        
        for param in params:
            # GIM result mock
            if 'gim' in param.lower():
                mock_inputs[param] = {
                    'composite_score': 0.5,
                    'is_risk_elevated': False,
                    'factor_scores': {'VIX': 0.0, 'TNX': 0.0, 'OIL': 0.0, 'GOLD': 0.0},
                    'fetch_status': 'OK',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    '_contract_version': '1.0'
                }
            
            # VAPD result mock
            elif 'vapd' in param.lower():
                mock_inputs[param] = {
                    'deviation_score': 0.3,
                    'is_deviation_significant': False,
                    'status': 'OK',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    '_contract_version': '1.0'
                }
            
            # EQL result mock
            elif 'eql' in param.lower():
                mock_inputs[param] = {
                    'defense_status': 'NORMAL',
                    'risk_level': 'LOW',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    '_contract_version': '1.0'
                }
            
            # Generic mock
            else:
                mock_inputs[param] = {
                    'status': 'OK',
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
        
        return mock_inputs
    
    def _build_receipt(self, clean_output: Dict[str, Any], raw_output: Dict[str, Any], *, decision_id: Optional[str] = None, timestamp_utc: Optional[str] = None) -> Dict[str, Any]:
        """
        Build decision receipt from module output (FULL / spec-aligned).

        This implementation fixes the runner↔GateC mismatch by:
        1) Using GateC.build_receipt() to compute all hashes deterministically
        2) Computing evidence_set_hash from an evidence_set_payload (not from refs list only)
        3) Validating receipt after construction (schema + allowlist + hash invariants)

        Args:
            clean_output: Cleaned module output (JSON-serializable).
            raw_output: Raw module output (may contain DataFrames / non-serializable).

        Returns:
            Decision receipt dict.

        Raises:
            GateCError: If receipt violates schema, reason allowlist, or hash invariants.
        """
        module_id = self.module_name.lower().replace('_golden', '')

        # Detect module type and extract decision (use raw output)
        decision_data = self._extract_decision(raw_output, module_id)

        # Build toolchain manifest (runner-level)
        toolchain_manifest = {
            "python": f"{sys.version_info.major}.{sys.version_info.minor}",
            "module_version": raw_output.get('_contract_version', '1.0'),
        }
        toolchain_manifest_digest = sha256_hex(canonical_json(toolchain_manifest))

        # Context (keep runner behavior; context_hash is a digest pointer)
        context_level = "L3"
        context_payload = {
            "module": module_id,
            "context_level": context_level,
        }
        context_hash = sha256_hex(canonical_json(context_payload))

        # Parameters payload (runner-level). NOTE: this is what parameters_hash binds.
        parameters_payload = {
            "module_name": module_id,
        }

        # Evidence refs: one primary output artifact hash (based on clean output)
        primary_output_hash = sha256_hex(canonical_json(clean_output))
        evidence_refs = [
            {
                "name": f"{module_id}.output",
                "ref_type": "sha256",
                "ref_hash": primary_output_hash,
            }
        ]

        # Evidence set payload: MUST be a payload (not only refs list) for stable hashing
        evidence_set_payload = {
            "evidence_refs": evidence_refs,
            "primary_output_hash": primary_output_hash,
        }

        # Build receipt using GateC (computes hashes + receipt_hash + determinism_key)
        receipt = self.gate_c.build_receipt(
            toolchain_manifest_digest=toolchain_manifest_digest,
            context_level=context_level,
            context_hash=context_hash,
            router_decision=decision_data.get("router_decision", ""),
            guard_verdict=decision_data.get("guard_verdict", ""),
            risk_params=decision_data.get("risk_params", {}),
            parameters_payload=parameters_payload,
            evidence_set_payload=evidence_set_payload,
            evidence_refs=evidence_refs,
            reason_codes=[],
            hybrid=decision_data.get("hybrid"),
            decision_id=decision_id,
            timestamp_utc=timestamp_utc,
            project_id="pythonbrain",
            module_id=module_id,
            language="python",
        )

        # Validate receipt after build (enforces receipt_hash self-field exclusion + schema)
        self.gate_c.validate(receipt)
        return receipt

    def _extract_decision(self, module_output: Dict[str, Any], module_id: str) -> Dict[str, Any]:
        """
        Extract decision data from module output
        
        Args:
            module_output: Module output
            module_id: Module identifier
            
        Returns:
            Decision data in Gate C format
        """
        # GIM-specific
        if 'gim' in module_id:
            return {
                "router_decision": "RISK_ELEVATED" if module_output.get('is_risk_elevated') else "NORMAL",
                "guard_verdict": "APPROVED",
                "risk_params": {
                    "composite_score": module_output.get('composite_score', 0.0),
                    "fetch_status": module_output.get('fetch_status', 'UNKNOWN')
                }
            }
        
        # BrainRouter-specific
        if 'router' in module_id or 'brain' in module_id:
            return {
                "router_decision": module_output.get('decision', 'UNKNOWN'),
                "guard_verdict": module_output.get('guard_verdict', 'APPROVED'),
                "risk_params": module_output.get('risk_params', {})
            }
        
        # Generic fallback
        return {
            "router_decision": module_output.get('decision', 'UNKNOWN'),
            "guard_verdict": "APPROVED",
            "risk_params": {}
        }
    
    def _validate_receipt(self, receipt: Dict[str, Any]):
        """
        Validate receipt with Gate C
        
        Args:
            receipt: Decision receipt
            
        Raises:
            GateCError: If validation fails
        """
        self.gate_c.validate(receipt)
        print(f"  ✅ Gate C validation: PASS")
    
    def _replay_and_persist(self, receipt: Dict[str, Any], clean_output: Dict[str, Any], raw_output: Dict[str, Any]):
        """
        Stage 6: Replay determinism check + Write-once receipt persistence
        
        This stage ensures:
        1. Replay determinism: Building receipt twice with same inputs produces identical hashes
        2. Write-once: Receipt is written to disk with write-once semantics (cannot overwrite)
        
        Args:
            receipt: Original receipt
            clean_output: Cleaned module output
            raw_output: Raw module output
            
        Raises:
            GateCError: If replay hashes mismatch or receipt already exists
        """
        # Replay: Build receipt again with same inputs
        print("  [6.1] Replay determinism check...")
        
        try:
            receipt_replay = self._build_receipt(clean_output, raw_output, decision_id=receipt.get('decision_id'), timestamp_utc=receipt.get('timestamp_utc'))
        except Exception as e:
            raise GateCError(
                f"Replay build failed: {e}",
                "RC_RUNTIME_ENV_DRIFT"
            )
        
        # Check determinism - verify both receipts have required fields
        if 'hashes' not in receipt or 'receipt_hash' not in receipt.get('hashes', {}):
            raise GateCError(
                "Original receipt missing receipt_hash",
                "RC_RECEIPT_SCHEMA_INVALID"
            )
        
        if 'hashes' not in receipt_replay or 'receipt_hash' not in receipt_replay.get('hashes', {}):
            raise GateCError(
                "Replay receipt missing receipt_hash",
                "RC_RECEIPT_SCHEMA_INVALID"
            )
        
        if receipt['hashes']['receipt_hash'] != receipt_replay['hashes']['receipt_hash']:
            raise GateCError(
                f"Replay receipt_hash mismatch: {receipt['hashes']['receipt_hash'][:16]}... != {receipt_replay['hashes']['receipt_hash'][:16]}...",
                "RC_RUNTIME_ENV_DRIFT"
            )
        
        if receipt.get('determinism_key') != receipt_replay.get('determinism_key'):
            raise GateCError(
                f"Replay determinism_key mismatch: {receipt.get('determinism_key', '')[:16]}... != {receipt_replay.get('determinism_key', '')[:16]}...",
                "RC_RUNTIME_ENV_DRIFT"
            )
        
        print(f"    ✅ Replay: receipt_hash identical")
        print(f"    ✅ Replay: determinism_key identical")
        
        # Write-once: Persist receipt to disk
        print("  [6.2] Write-once receipt persistence...")
        receipts_dir = self.work_dir / "receipts"
        receipts_dir.mkdir(exist_ok=True)
        
        receipt_filename = f"{receipt['decision_id']}.json"
        receipt_path = receipts_dir / receipt_filename
        
        # Check if already exists (write-once enforcement)
        if receipt_path.exists():
            raise GateCError(
                f"Receipt already exists: {receipt_path} (write-once violated)",
                "RC_RECEIPT_NOT_WRITTEN_PRE_EXECUTION"
            )
        
        # Write receipt with Gate C (canonical JSON + write-once semantics)
        self.gate_c.write_receipt(receipt, str(receipt_path))
        
        print(f"    ✅ Receipt written: receipts/{receipt_filename}")
        print(f"    ✅ Write-once enforced")
    
    def _log_stage(self, stage: str, status: str, data: Optional[Dict[str, Any]] = None):
        """Log stage result"""
        entry = {
            "stage": stage,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        if data:
            entry["data"] = data
        
        self.report["stages"].append(entry)
    
    def _save_report(self) -> str:
        """Save report to file"""
        report_path = self.work_dir / f"gate_c_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Clean report for JSON serialization
        clean_report = self._clean_for_json(self.report)
        
        with open(report_path, 'w') as f:
            json.dump(clean_report, f, indent=2)
        
        print(f"\n📄 Report saved: {report_path}")
        return str(report_path)

    def _clean_for_json(self, obj: Any) -> Any:
        """
        Clean object for JSON serialization
        
        Args:
            obj: Object to clean
            
        Returns:
            JSON-serializable object
        """
        import pandas as pd
        
        if isinstance(obj, dict):
            return {k: self._clean_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._clean_for_json(v) for v in obj]
        elif isinstance(obj, pd.DataFrame):
            return f"<DataFrame shape={obj.shape}>"
        elif isinstance(obj, pd.Series):
            return f"<Series len={len(obj)}>"
        elif hasattr(obj, '__dict__'):
            return f"<{obj.__class__.__name__}>"
        else:
            return obj

    
    @staticmethod
    def _noop():
        """No-op context manager"""
        from contextlib import contextmanager
        
        @contextmanager
        def _ctx():
            yield
        
        return _ctx()


def _expand_inputs(inputs: List[str]) -> List[str]:
    """Expand CLI inputs to a list of zip paths.

    Supports:
      - direct file paths
      - glob patterns (e.g. *.zip)
    """
    expanded: List[str] = []
    for item in inputs:
        # If item contains wildcard, expand; else keep.
        if any(ch in item for ch in ["*", "?", "["]):
            expanded.extend([str(p) for p in Path(".").glob(item)])
        else:
            expanded.append(item)
    # De-duplicate while preserving order
    seen = set()
    out_list: List[str] = []
    for p in expanded:
        if p not in seen:
            seen.add(p)
            out_list.append(p)
    return out_list


def _write_summary_csv(rows: List[Dict[str, Any]], out_path: str) -> str:
    """Write summary CSV.

    Columns are stable for easy diffing and CI.
    """
    fieldnames = [
        "module_zip",
        "status",
        "error",
        "receipt_path",
        "receipt_hash",
        "determinism_key",
        "report_path",
    ]
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})
    return out_path


def main() -> None:
    """CLI entrypoint.

    Examples:
        # Single module
        python gate_c_runner.py GIM_Golden.zip

        # Batch run with glob + summary
        python gate_c_runner.py *.zip --batch --out summary.csv
    """
    parser = argparse.ArgumentParser(description="Gate C Runner - Production")
    parser.add_argument("modules", nargs="+", help="Module zip(s) or glob patterns (e.g. *.zip)")
    parser.add_argument("--batch", action="store_true", help="Run all inputs and emit a summary CSV")
    parser.add_argument("--out", default="gate_c_summary.csv", help="Summary CSV output path (batch mode)")
    args = parser.parse_args()

    module_paths = _expand_inputs(args.modules)

    if not args.batch:
        # Backward-compatible single-run behavior: use the first input only.
        runner = GateCRunner()
        runner.run(module_paths[0])
        return

    rows: List[Dict[str, Any]] = []

    for module_zip in module_paths:
        # --- [CRITICAL PATCH] ล้าง Cache เพื่อป้องกันการนำ constants.py ของโมดูลเก่ามาใช้ ---
        import sys
        for m in list(sys.modules.keys()):
            if any(prefix in m for prefix in ['config', 'backend', 'target_module']):
                del sys.modules[m]
        # ----------------------------------------------------------------------------

        runner = GateCRunner()  # fresh runner per module (prevents import/path contamination)
        row: Dict[str, Any] = {
            "module_zip": module_zip,
            "status": "FAIL",
            "error": "",
            "receipt_path": "",
            "receipt_hash": "",
            "determinism_key": "",
            "report_path": "",
        }
        try:
            # run() prints its own console report; we additionally capture key outputs
            result = runner.run(module_zip)

            # Best-effort extraction from returned report dict if run() returns something.
            if isinstance(result, dict):
                row["status"] = "PASS" if result.get("status") == "PASS" else "FAIL"
                row["error"] = result.get("error", "")
                receipt = result.get("receipt") or {}
                if isinstance(receipt, dict):
                    row["receipt_hash"] = (receipt.get("hashes") or {}).get("receipt_hash", "")
                    row["determinism_key"] = receipt.get("determinism_key", "")
                    # ดึงพาธจากโฟลเดอร์ใบเสร็จจริง
                    row["receipt_path"] = f"receipts/{receipt.get('decision_id')}.json"
                row["report_path"] = result.get("report_path", "")
            else:
                row["status"] = "PASS"
        except Exception as exc:
            row["status"] = "FAIL"
            row["error"] = str(exc)

        rows.append(row)

    summary_path = _write_summary_csv(rows, args.out)
    print("\n" + "="*60)
    print("📊 Batch Summary")
    print("="*60)
    pass_count = sum(1 for r in rows if r["status"] == "PASS")
    print(f"Total: {len(rows)} | PASS: {pass_count} | FAIL: {len(rows) - pass_count}")
    print(f"Summary CSV: {summary_path}")


if __name__ == '__main__':
    main()
