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
import zipfile
import shutil
import importlib.util
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional
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
            print("\n[Stage 1/5] Extracting module...")
            self._extract_module(module_zip_path)
            self._log_stage("Extract", "PASS")
            
            # Stage 2: Validate structure
            print("[Stage 2/5] Validating structure...")
            self._validate_structure()
            self._log_stage("Structure", "PASS")
            
            # Stage 3: Run module
            print("[Stage 3/5] Running module...")
            module_output = self._run_module()
            self._log_stage("Module Run", "PASS", module_output)
            
            # Stage 4: Build receipt
            print("[Stage 4/5] Building decision receipt...")
            # Clean module output for JSON serialization
            clean_output = self._clean_for_json(module_output)
            receipt = self._build_receipt(clean_output, module_output)
            self._log_stage("Build Receipt", "PASS", {
                "decision_id": receipt['decision_id'],
                "receipt_hash": receipt['hashes']['receipt_hash'][:16] + "..."
            })
            
            # Stage 5: Validate with Gate C
            print("[Stage 5/5] Validating with Gate C...")
            self._validate_receipt(receipt)
            self._log_stage("Gate C Validation", "PASS")
            
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
    
    def _build_receipt(self, clean_output: Dict[str, Any], raw_output: Dict[str, Any]) -> Dict[str, Any]:
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
            decision_id=None,
            timestamp_utc=None,
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
    
    def _save_report(self):
        """Save report to file"""
        report_path = self.work_dir / f"gate_c_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Clean report for JSON serialization
        clean_report = self._clean_for_json(self.report)
        
        with open(report_path, 'w') as f:
            json.dump(clean_report, f, indent=2)
        
        print(f"\n📄 Report saved: {report_path}")
    
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


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python gate_c_runner.py MODULE.zip")
        print("\nExamples:")
        print("  python gate_c_runner.py GIM_Golden.zip")
        print("  python gate_c_runner.py BrainRouter_Golden.zip")
        print("  python gate_c_runner.py VAPD_Golden.zip")
        sys.exit(1)
    
    module_zip = sys.argv[1]
    
    runner = GateCRunner()
    report = runner.run(module_zip)
    
    # Exit code
    sys.exit(0 if report['status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
