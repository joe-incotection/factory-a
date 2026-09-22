"""
gate_c_wrapper.py

Gate C Wrapper for Factory-A Integration
==========================================

เรียกใช้ Gate C หลัง AIEL-T ผ่าน
สร้าง Decision Receipt ก่อนส่งต่อ Integration

Position in flow:
    AIEL-T → Gate C Wrapper → Integration → M8/Stage2/M7
"""

import os
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


class GateCWrapper:
    """
    Gate C Wrapper for Factory-A
    
    Responsibilities:
    1. รับ AIEL-T result
    2. Extract parameters/evidence/context
    3. เรียก Gate C build receipt
    4. Persist receipt ก่อน execution
    5. Forward ไปยัง Integration
    """
    
    def __init__(self, 
                 base_dir: Optional[str] = None,
                 reasons_path: str = "REASON_CODES_v1.yaml",
                 locks_path: str = "GOLDEN_IO_LOCK_GATEC_v1.yaml"):
        """
        Initialize Gate C Wrapper
        
        Args:
            base_dir: Base directory for config files
            reasons_path: Path to REASON_CODES_v1.yaml
            locks_path: Path to GOLDEN_IO_LOCK_GATEC_v1.yaml
        """
        self.base_dir = base_dir or os.getcwd()
        
        # Import gate_c (lazy import)
        try:
            import gate_c
            self.gate_c = gate_c
            self.gate = gate_c.GateC(
                base_dir=self.base_dir,
                reasons_path=reasons_path,
                locks_path=locks_path
            )
            self.available = True
        except ImportError as e:
            print(f"[Gate C] Warning: gate_c module not available: {e}")
            self.available = False
    
    def build_receipt_from_aiel_t(
        self,
        aiel_t_result: Dict[str, Any],
        module_info: Dict[str, Any],
        router_decision: str = "APPROVED",
        guard_verdict: str = "APPROVED"
    ) -> Optional[Dict[str, Any]]:
        """
        สร้าง Decision Receipt จาก AIEL-T result
        
        Args:
            aiel_t_result: ผลจาก AIEL-T (format: AIEL-T-RESULT)
            module_info: ข้อมูล module (project_id, module_id, language)
            router_decision: Router decision (default: APPROVED)
            guard_verdict: Guard verdict (APPROVED/REJECTED/DEGRADED/SAFE_MODE)
            
        Returns:
            Decision Receipt หรือ None ถ้า Gate C ไม่พร้อม
        """
        if not self.available:
            print("[Gate C] Skipped: gate_c not available")
            return None
        
        # Extract ข้อมูลจาก AIEL-T result
        test_result = aiel_t_result.get("test_result", {})
        g_score = aiel_t_result.get("g_score", 0.0)
        toolchain = aiel_t_result.get("toolchain", {})
        
        # สร้าง parameters_payload
        parameters_payload = {
            "g_score": g_score,
            "test_coverage": test_result.get("coverage", 0.0),
            "tests_passed": test_result.get("tests_passed", 0),
            "tests_total": test_result.get("tests_total", 0),
            "module_info": module_info
        }
        
        # สร้าง evidence_set_payload
        evidence_set_payload = {
            "test_result": test_result,
            "toolchain": toolchain,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # สร้าง evidence_refs
        evidence_refs = self._build_evidence_refs(aiel_t_result, module_info)
        
        # คำนวณ toolchain_manifest_digest
        toolchain_manifest_digest = self._compute_toolchain_digest(toolchain)
        
        # คำนวณ context_hash
        context_hash = self._compute_context_hash(module_info, g_score)
        
        # สร้าง reason_codes (ถ้ามี)
        reason_codes = self._extract_reason_codes(aiel_t_result)
        
        # เรียก Gate C build_receipt
        try:
            receipt = self.gate.build_receipt(
                toolchain_manifest_digest=toolchain_manifest_digest,
                context_level=self._determine_context_level(g_score),
                context_hash=context_hash,
                router_decision=router_decision,
                guard_verdict=guard_verdict,
                risk_params={"g_score": g_score},
                parameters_payload=parameters_payload,
                evidence_set_payload=evidence_set_payload,
                evidence_refs=evidence_refs,
                reason_codes=reason_codes,
                project_id=module_info.get("project_id", "unknown_project"),
                module_id=module_info.get("module_id", "unknown_module"),
                language=module_info.get("language", "python")
            )
            
            print(f"[Gate C] ✅ Receipt created: {receipt['decision_id']}")
            return receipt
            
        except self.gate_c.GateCError as e:
            print(f"[Gate C] ❌ Failed to build receipt: {e}")
            print(f"[Gate C]    Reason code: {e.reason_code}")
            return None
    
    def write_receipt(
        self, 
        receipt: Dict[str, Any], 
        output_dir: Optional[str] = None
    ) -> Optional[str]:
        """
        เขียน receipt ลง filesystem (write-once)
        
        Args:
            receipt: Decision receipt
            output_dir: Output directory (default: self.base_dir)
            
        Returns:
            Path to written receipt or None if failed
        """
        if not self.available or receipt is None:
            return None
        
        output_dir = output_dir or self.base_dir
        decision_id = receipt.get("decision_id", "unknown")
        receipt_path = os.path.join(output_dir, f"Decision_Receipt_{decision_id}.json")
        
        try:
            abs_path = self.gate.write_receipt(receipt, receipt_path)
            print(f"[Gate C] ✅ Receipt written: {abs_path}")
            return abs_path
        except self.gate_c.GateCError as e:
            print(f"[Gate C] ❌ Failed to write receipt: {e}")
            return None
    
    def process_aiel_t_output(
        self,
        aiel_t_result: Dict[str, Any],
        module_info: Dict[str, Any],
        output_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process AIEL-T output → สร้าง + เขียน receipt
        
        Args:
            aiel_t_result: AIEL-T result
            module_info: Module information
            output_dir: Output directory
            
        Returns:
            Result with receipt info
        """
        result = {
            "gate_c_available": self.available,
            "receipt_created": False,
            "receipt_written": False
        }
        
        if not self.available:
            result["reason"] = "gate_c_not_available"
            return result
        
        # Check AIEL-T status
        if aiel_t_result.get("status") != "PASS":
            result["reason"] = "aiel_t_not_pass"
            return result
        
        # Build receipt
        receipt = self.build_receipt_from_aiel_t(
            aiel_t_result=aiel_t_result,
            module_info=module_info
        )
        
        if receipt is None:
            result["reason"] = "receipt_build_failed"
            return result
        
        result["receipt_created"] = True
        result["receipt"] = receipt
        
        # Write receipt
        receipt_path = self.write_receipt(receipt, output_dir)
        
        if receipt_path:
            result["receipt_written"] = True
            result["receipt_path"] = receipt_path
        else:
            result["reason"] = "receipt_write_failed"
        
        return result
    
    # ========================================
    # Helper methods
    # ========================================
    
    def _build_evidence_refs(
        self, 
        aiel_t_result: Dict[str, Any],
        module_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """สร้าง evidence_refs จาก AIEL-T result"""
        refs = []
        
        # Test result reference
        test_result = aiel_t_result.get("test_result", {})
        if test_result:
            test_hash = self._hash_dict(test_result)
            refs.append({
                "name": "aiel_t.test_result",
                "ref_type": "sha256",
                "ref_hash": test_hash
            })
        
        # Module reference
        module_hash = self._hash_dict(module_info)
        refs.append({
            "name": "module.info",
            "ref_type": "sha256",
            "ref_hash": module_hash
        })
        
        # ถ้าไม่มี refs ใดๆ ให้ใส่ default
        if not refs:
            refs.append({
                "name": "default.evidence",
                "ref_type": "memory_ref",
                "ref_hash": "default"
            })
        
        return refs
    
    def _compute_toolchain_digest(self, toolchain: Dict[str, Any]) -> str:
        """คำนวณ toolchain manifest digest"""
        if not toolchain:
            return "t_" + "0" * 62
        
        toolchain_hash = self._hash_dict(toolchain)
        return f"t_{toolchain_hash[:62]}"
    
    def _compute_context_hash(
        self, 
        module_info: Dict[str, Any], 
        g_score: float
    ) -> str:
        """คำนวณ context hash"""
        context_data = {
            "module_info": module_info,
            "g_score": g_score
        }
        context_hash = self._hash_dict(context_data)
        return f"c_{context_hash[:62]}"
    
    def _determine_context_level(self, g_score: float) -> str:
        """กำหนด context level จาก G-score"""
        if g_score >= 0.95:
            return "L3"  # High confidence
        elif g_score >= 0.85:
            return "L2"  # Medium confidence
        elif g_score >= 0.75:
            return "L1"  # Low confidence
        else:
            return "L0"  # Insufficient
    
    def _extract_reason_codes(self, aiel_t_result: Dict[str, Any]) -> List[str]:
        """Extract reason codes จาก AIEL-T result"""
        reason_codes = []
        
        # ถ้า coverage ต่ำ
        test_result = aiel_t_result.get("test_result", {})
        coverage = test_result.get("coverage", 1.0)
        
        if coverage < 0.95:
            reason_codes.append("RC_EVIDENCE_INCOMPLETE_SAFE_MODE")
        
        return reason_codes
    
    def _hash_dict(self, data: Dict[str, Any]) -> str:
        """Hash dictionary เป็น SHA256"""
        import json
        
        # Use canonical JSON if available
        try:
            from canonical_json import canonical_json
            json_str = canonical_json(data)
        except ImportError:
            json_str = json.dumps(data, sort_keys=True)
        
        return hashlib.sha256(json_str.encode()).hexdigest()


# ========================================
# Convenience function
# ========================================

def create_receipt_from_aiel_t(
    aiel_t_result: Dict[str, Any],
    project_id: str,
    module_id: str,
    language: str = "python",
    output_dir: Optional[str] = None,
    base_dir: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Helper function: สร้าง receipt จาก AIEL-T result
    
    Args:
        aiel_t_result: AIEL-T result
        project_id: Project ID
        module_id: Module ID
        language: Programming language
        output_dir: Output directory for receipt
        base_dir: Base directory for Gate C config
        
    Returns:
        Gate C result with receipt info
    """
    wrapper = GateCWrapper(base_dir=base_dir)
    
    module_info = {
        "project_id": project_id,
        "module_id": module_id,
        "language": language
    }
    
    return wrapper.process_aiel_t_output(
        aiel_t_result=aiel_t_result,
        module_info=module_info,
        output_dir=output_dir
    )
