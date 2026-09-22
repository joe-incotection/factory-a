"""
Contract Engine v1.0
====================

Validates compliance with specification contracts.
Weight: 10% of G-Score

Contract: AIEL-T_v1.0.md Section 4.3
"""

import yaml
import logging
from typing import Dict, List, Any
from pathlib import Path
import re

logger = logging.getLogger(__name__)


class ContractEngine:
    """
    Contract Engine - Validates spec compliance
    
    Purpose:
    - Load specification files (YAML/MD)
    - Validate runtime data matches spec contracts
    - Check field existence, types, ranges
    - Validate cross-layer consistency
    
    Weight: 10% of G-Score
    """
    
    def __init__(self, spec_files: List[str] = None):
        """
        Initialize Contract Engine
        
        Args:
            spec_files: List of paths to spec files (YAML or MD)
        """
        self.spec_files = spec_files or []
        self.contracts = {}
        self.field_definitions = {}
        
        if spec_files:
            for spec_file in spec_files:
                self.load_contract(spec_file)
    
    def load_contract(self, file_path: str):
        """
        Load contract specification from file
        
        Args:
            file_path: Path to spec file
        """
        try:
            path = Path(file_path)
            
            if path.suffix in ['.yaml', '.yml']:
                with open(file_path, 'r') as f:
                    spec = yaml.safe_load(f)
                    self._parse_yaml_contract(spec, path.stem)
            elif path.suffix == '.md':
                with open(file_path, 'r') as f:
                    content = f.read()
                    self._parse_md_contract(content, path.stem)
            else:
                logger.warning(f"Unsupported spec file format: {file_path}")
                
            logger.info(f"Loaded contract from {file_path}")
        except Exception as e:
            logger.error(f"Failed to load contract {file_path}: {e}")
    
    def _parse_yaml_contract(self, spec: Dict, contract_name: str):
        """Parse YAML specification into contract rules"""
        self.contracts[contract_name] = spec
        
        # Extract field definitions if present
        if 'fields' in spec:
            for field_name, field_spec in spec['fields'].items():
                self.field_definitions[field_name] = field_spec
    
    def _parse_md_contract(self, content: str, contract_name: str):
        """Parse Markdown specification into contract rules"""
        # Simple MD parsing - look for field definitions
        # Format: field_name: type (range)
        field_pattern = r'`(\w+)`\s*:\s*(\w+)(?:\s*\(([^)]+)\))?'
        matches = re.findall(field_pattern, content)
        
        fields = {}
        for field_name, field_type, field_range in matches:
            fields[field_name] = {
                'type': field_type,
                'range': field_range if field_range else None
            }
        
        if fields:
            self.contracts[contract_name] = {'fields': fields}
            self.field_definitions.update(fields)
    
    def validate(self, runtime_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate runtime data against all loaded contracts
        
        Args:
            runtime_data: Dictionary with runtime values
            
        Returns:
            {
                'contract_score': float,
                'results': {...},
                'violations': [...],
                'matched': int,
                'total': int
            }
        """
        if not self.field_definitions:
            logger.warning("No contracts loaded")
            return {
                'contract_score': 1.0,
                'results': {},
                'violations': [],
                'matched': 0,
                'total': 0
            }
        
        results = {}
        violations = []
        
        for field_name, field_spec in self.field_definitions.items():
            try:
                # Check if field exists
                if field_name not in runtime_data:
                    results[field_name] = 'MISSING'
                    violations.append({
                        'field': field_name,
                        'issue': 'Field missing from runtime data',
                        'expected': field_spec
                    })
                    continue
                
                value = runtime_data[field_name]
                
                # Check type
                expected_type = field_spec.get('type', '')
                type_valid = self._check_type(value, expected_type)
                
                if not type_valid:
                    results[field_name] = 'TYPE_MISMATCH'
                    violations.append({
                        'field': field_name,
                        'issue': f'Type mismatch: expected {expected_type}, got {type(value).__name__}',
                        'value': value
                    })
                    continue
                
                # Check range/constraints
                field_range = field_spec.get('range')
                if field_range:
                    range_valid = self._check_range(value, field_range)
                    if not range_valid:
                        results[field_name] = 'RANGE_VIOLATION'
                        violations.append({
                            'field': field_name,
                            'issue': f'Value outside range: {field_range}',
                            'value': value
                        })
                        continue
                
                # All checks passed
                results[field_name] = 'PASS'
                
            except Exception as e:
                logger.error(f"Error validating {field_name}: {e}")
                results[field_name] = 'ERROR'
                violations.append({
                    'field': field_name,
                    'error': str(e)
                })
        
        matched = sum(1 for r in results.values() if r == 'PASS')
        total = len(results)
        score = matched / total if total > 0 else 0.0
        
        logger.info(f"Contract: {matched}/{total} fields valid ({score:.2%})")
        
        return {
            'contract_score': score,
            'results': results,
            'violations': violations,
            'matched': matched,
            'total': total
        }
    
    def _check_type(self, value: Any, expected_type: str) -> bool:
        """
        Check if value matches expected type
        
        Args:
            value: Value to check
            expected_type: Expected type name (str, int, float, bool, list, dict)
            
        Returns:
            True if type matches
        """
        type_map = {
            'str': str,
            'string': str,
            'int': int,
            'integer': int,
            'float': float,
            'number': (int, float),
            'bool': bool,
            'boolean': bool,
            'list': list,
            'array': list,
            'dict': dict,
            'object': dict
        }
        
        expected = type_map.get(expected_type.lower())
        if expected is None:
            logger.warning(f"Unknown type: {expected_type}")
            return True  # Don't fail on unknown types
        
        return isinstance(value, expected)
    
    def _check_range(self, value: Any, range_spec: str) -> bool:
        """
        Check if value is within specified range
        
        Args:
            value: Value to check
            range_spec: Range specification (e.g., "0-1", "[0.25,0.5,1.0]", ">0")
            
        Returns:
            True if value in range
        """
        try:
            # Discrete values: [0.25, 0.5, 1.0]
            if range_spec.startswith('[') and range_spec.endswith(']'):
                allowed = eval(range_spec)
                return value in allowed
            
            # Range: 0-1 or 0.0-1.0
            if '-' in range_spec and not range_spec.startswith('-'):
                parts = range_spec.split('-')
                if len(parts) == 2:
                    min_val = float(parts[0])
                    max_val = float(parts[1])
                    return min_val <= value <= max_val
            
            # Comparison: >0, >=0, <1, <=1
            if range_spec.startswith('>='):
                return value >= float(range_spec[2:])
            if range_spec.startswith('<='):
                return value <= float(range_spec[2:])
            if range_spec.startswith('>'):
                return value > float(range_spec[1:])
            if range_spec.startswith('<'):
                return value < float(range_spec[1:])
            
            logger.warning(f"Unrecognized range spec: {range_spec}")
            return True
            
        except Exception as e:
            logger.error(f"Error checking range {range_spec}: {e}")
            return False
    
    def validate_cross_layer(self, data_layers: Dict[str, Dict]) -> Dict[str, Any]:
        """
        Validate consistency across multiple layers
        
        Args:
            data_layers: Dict of layer_name -> layer_data
            
        Returns:
            {
                'cross_layer_score': float,
                'violations': [...]
            }
        """
        violations = []
        
        # Example: Check if PolicyController risk_factor respects BrokerContext trust
        if 'BrokerContext' in data_layers and 'PolicyController' in data_layers:
            trust = data_layers['BrokerContext'].get('broker_trust_score')
            risk = data_layers['PolicyController'].get('risk_factor_scalar')
            
            if trust is not None and risk is not None:
                # INV_002: if trust < 0.5 then risk <= 0.5
                if trust < 0.5 and risk > 0.5:
                    violations.append({
                        'type': 'CROSS_LAYER_VIOLATION',
                        'rule': 'Trust-Risk Monotonicity',
                        'issue': f'Low trust ({trust}) but high risk ({risk})'
                    })
        
        # Check if Guard can override Policy
        if 'ExecutionGuard' in data_layers and 'PolicyController' in data_layers:
            guard_veto = data_layers['ExecutionGuard'].get('veto', False)
            policy_allow = data_layers['PolicyController'].get('allow_trade', True)
            
            # Guard veto must override policy
            if guard_veto and policy_allow:
                violations.append({
                    'type': 'CROSS_LAYER_VIOLATION',
                    'rule': 'Guard Override',
                    'issue': 'Guard veto but policy still allows trade'
                })
        
        score = 1.0 if len(violations) == 0 else 0.0
        
        return {
            'cross_layer_score': score,
            'violations': violations
        }


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    engine = ContractEngine()
    
    # Add sample field definitions
    engine.field_definitions = {
        'risk_factor_scalar': {
            'type': 'float',
            'range': '[0.25,0.5,1.0]'
        },
        'broker_trust_score': {
            'type': 'float',
            'range': '0.0-1.0'
        },
        'equity_drawdown': {
            'type': 'float',
            'range': '>=0'
        },
        'veto': {
            'type': 'bool'
        }
    }
    
    # Test data
    test_data = {
        'risk_factor_scalar': 0.5,
        'broker_trust_score': 0.8,
        'equity_drawdown': 0.03,
        'veto': False
    }
    
    result = engine.validate(test_data)
    print(f"Contract Score: {result['contract_score']:.2%}")
    print(f"Results: {result['results']}")
    
    # Test cross-layer
    layers = {
        'BrokerContext': {'broker_trust_score': 0.3},
        'PolicyController': {'risk_factor_scalar': 0.25}
    }
    cross_result = engine.validate_cross_layer(layers)
    print(f"Cross-Layer Score: {cross_result['cross_layer_score']:.2%}")
