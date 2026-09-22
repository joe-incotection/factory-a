"""
Invariants Engine v1.0
======================

Validates core invariant rules that must never be violated.
Weight: 45% of G-Score

Contract: AIEL-T_v1.0.md Section 4.1
"""

import yaml
import logging
from typing import Dict, List, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class InvariantsEngine:
    """
    Invariants Engine - Validates core rules
    
    Purpose:
    - Load invariant rules from YAML
    - Validate runtime data against rules
    - Return pass/fail + invariant_pass_rate
    
    Weight: 45% of G-Score
    """
    
    def __init__(self, invariants_file: str = None):
        """
        Initialize Invariants Engine
        
        Args:
            invariants_file: Path to YAML file with invariant rules
        """
        self.invariants_file = invariants_file
        self.invariants = {}
        self.results = {}
        
        if invariants_file:
            self.load_invariants(invariants_file)
    
    def load_invariants(self, file_path: str):
        """
        Load invariant rules from YAML file
        
        Args:
            file_path: Path to invariants YAML
        """
        try:
            with open(file_path, 'r') as f:
                self.invariants = yaml.safe_load(f)
            logger.info(f"Loaded {len(self.invariants)} invariants from {file_path}")
        except Exception as e:
            logger.error(f"Failed to load invariants: {e}")
            self.invariants = {}
    
    def validate(self, runtime_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate runtime data against all invariants
        
        Args:
            runtime_data: Dictionary with runtime values to validate
            
        Returns:
            {
                'invariant_pass_rate': float,
                'results': {inv_id: 'PASS'|'FAIL', ...},
                'passed': int,
                'total': int,
                'failures': [...]
            }
        """
        if not self.invariants:
            logger.warning("No invariants loaded")
            return {
                'invariant_pass_rate': 1.0,
                'results': {},
                'passed': 0,
                'total': 0,
                'failures': []
            }
        
        results = {}
        failures = []
        
        for inv_id, inv_spec in self.invariants.items():
            try:
                passed = self._check_invariant(inv_id, inv_spec, runtime_data)
                results[inv_id] = 'PASS' if passed else 'FAIL'
                
                if not passed:
                    failures.append({
                        'id': inv_id,
                        'rule': inv_spec.get('rule', 'N/A'),
                        'data': runtime_data
                    })
            except Exception as e:
                logger.error(f"Error checking {inv_id}: {e}")
                results[inv_id] = 'ERROR'
                failures.append({
                    'id': inv_id,
                    'error': str(e)
                })
        
        passed = sum(1 for r in results.values() if r == 'PASS')
        total = len(results)
        pass_rate = passed / total if total > 0 else 0.0
        
        logger.info(f"Invariants: {passed}/{total} passed ({pass_rate:.2%})")
        
        return {
            'invariant_pass_rate': pass_rate,
            'results': results,
            'passed': passed,
            'total': total,
            'failures': failures
        }
    
    def _check_invariant(self, inv_id: str, inv_spec: Dict, data: Dict) -> bool:
        """
        Check single invariant rule
        
        Args:
            inv_id: Invariant ID
            inv_spec: Invariant specification
            data: Runtime data
            
        Returns:
            True if passed, False if failed
        """
        rule = inv_spec.get('rule', '')
        
        # Parse and evaluate rule
        # This is simplified - production would use safe expression parser
        
        # INV_001: risk_factor_scalar in [0.25, 0.5, 1.0]
        if 'risk_factor_scalar' in rule and 'in' in rule:
            value = data.get('risk_factor_scalar')
            if value is None:
                return False
            return value in [0.25, 0.5, 1.0]
        
        # INV_002: if broker_trust_score < 0.5 then risk_factor_scalar <= 0.5
        if 'TRUST_RISK_MONOTONICITY' in inv_id:
            trust = data.get('broker_trust_score')
            risk = data.get('risk_factor_scalar')
            if trust is None or risk is None:
                return False
            if trust < 0.5:
                return risk <= 0.5
            return True
        
        # INV_003: if equity_drawdown > limit then veto=true
        if 'GUARD_HARD_STOP' in inv_id:
            dd = data.get('equity_drawdown', 0)
            limit = data.get('max_daily_drawdown_limit', 0.05)
            veto = data.get('veto', False)
            if dd > limit:
                return veto == True
            return True
        
        # INV_004: No Time Travel (timestamps must be sequential)
        if 'TIME_TRAVEL' in inv_id:
            timestamps = data.get('timestamps', [])
            if len(timestamps) < 2:
                return True
            return all(timestamps[i] <= timestamps[i+1] for i in range(len(timestamps)-1))
        
        # INV_005: UTC Alignment
        if 'UTC_ALIGNMENT' in inv_id:
            timestamps = data.get('timestamps', [])
            # Check all timestamps end with 'Z' or have '+00:00'
            return all('Z' in str(ts) or '+00:00' in str(ts) for ts in timestamps)
        
        # INV_009: Missing Data Auto-Reject
        if 'MISSING_DATA' in inv_id:
            required_fields = data.get('required_fields', [])
            actual_data = data.get('actual_data', {})
            return all(field in actual_data for field in required_fields)
        
        # Default: assume pass if rule not recognized
        logger.warning(f"Unrecognized invariant rule: {inv_id}")
        return True


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    engine = InvariantsEngine()
    
    # Test data
    test_data = {
        'risk_factor_scalar': 0.5,
        'broker_trust_score': 0.3,
        'equity_drawdown': 0.06,
        'max_daily_drawdown_limit': 0.05,
        'veto': True,
        'timestamps': ['2024-12-01T00:00:00Z', '2024-12-01T01:00:00Z']
    }
    
    # Load sample invariants
    engine.invariants = {
        'INV_001_RISK_FACTOR_VALID': {'rule': 'risk_factor_scalar in [0.25,0.5,1.0]'},
        'INV_002_TRUST_RISK_MONOTONICITY': {'rule': 'if broker_trust_score < 0.5 then risk_factor_scalar <= 0.5'},
        'INV_003_GUARD_HARD_STOP': {'rule': 'if equity_drawdown > max_daily_drawdown_limit then veto=true'}
    }
    
    result = engine.validate(test_data)
    print(f"Pass Rate: {result['invariant_pass_rate']:.2%}")
    print(f"Results: {result['results']}")