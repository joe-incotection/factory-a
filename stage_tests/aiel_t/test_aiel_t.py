"""
AIEL-T Test Runner v1.0
========================

Full test runner with pytest integration for all engines.
"""

import pytest
import logging
from typing import Dict, Any
from AIEL_T_Engine import AIELTEngine

logger = logging.getLogger(__name__)


class TestInvariantsEngine:
    """Test suite for Invariants Engine"""
    
    @pytest.fixture
    def engine(self):
        """Setup Invariants Engine"""
        from Invariants_Engine import InvariantsEngine
        engine = InvariantsEngine()
        
        # Load sample invariants
        engine.invariants = {
            'INV_001_RISK_FACTOR_VALID': {
                'rule': 'risk_factor_scalar in [0.25,0.5,1.0]'
            },
            'INV_002_TRUST_RISK_MONOTONICITY': {
                'rule': 'if broker_trust_score < 0.5 then risk_factor_scalar <= 0.5'
            },
            'INV_003_GUARD_HARD_STOP': {
                'rule': 'if equity_drawdown > max_daily_drawdown_limit then veto=true'
            }
        }
        return engine
    
    def test_risk_factor_valid_pass(self, engine):
        """Test valid risk factor values"""
        data = {'risk_factor_scalar': 0.5}
        result = engine.validate(data)
        assert result['results']['INV_001_RISK_FACTOR_VALID'] == 'PASS'
    
    def test_risk_factor_invalid(self, engine):
        """Test invalid risk factor value"""
        data = {'risk_factor_scalar': 0.75}
        result = engine.validate(data)
        assert result['results']['INV_001_RISK_FACTOR_VALID'] == 'FAIL'
    
    def test_trust_risk_monotonicity_pass(self, engine):
        """Test trust-risk monotonicity passes"""
        data = {
            'broker_trust_score': 0.3,
            'risk_factor_scalar': 0.25
        }
        result = engine.validate(data)
        assert result['results']['INV_002_TRUST_RISK_MONOTONICITY'] == 'PASS'
    
    def test_trust_risk_monotonicity_fail(self, engine):
        """Test trust-risk monotonicity fails"""
        data = {
            'broker_trust_score': 0.3,
            'risk_factor_scalar': 1.0
        }
        result = engine.validate(data)
        assert result['results']['INV_002_TRUST_RISK_MONOTONICITY'] == 'FAIL'
    
    def test_guard_hard_stop_pass(self, engine):
        """Test guard hard stop triggers correctly"""
        data = {
            'equity_drawdown': 0.06,
            'max_daily_drawdown_limit': 0.05,
            'veto': True
        }
        result = engine.validate(data)
        assert result['results']['INV_003_GUARD_HARD_STOP'] == 'PASS'


class TestPatternEngine:
    """Test suite for Pattern Engine"""
    
    @pytest.fixture
    def engine(self):
        """Setup Pattern Engine"""
        from Pattern_Engine import PatternEngine
        return PatternEngine()
    
    def test_latency_pattern_good(self, engine):
        """Test latency pattern with good values"""
        data = {
            'latencies_ms': [10, 15, 12, 18, 20],
            'target_max_latency_ms': 50,
            'target_avg_latency_ms': 25
        }
        result = engine.validate(data)
        assert result['pattern_score'] > 0.9
    
    def test_latency_pattern_bad(self, engine):
        """Test latency pattern with bad values"""
        data = {
            'latencies_ms': [100, 150, 120, 180],
            'target_max_latency_ms': 50,
            'target_avg_latency_ms': 25
        }
        result = engine.validate(data)
        assert result['pattern_score'] <= 0.8
    
    def test_monotonicity_pattern_pass(self, engine):
        """Test monotonicity pattern passes"""
        data = {
            'trust_score_sequence': [1.0, 0.8, 0.6, 0.4],
            'risk_factor_sequence': [1.0, 0.5, 0.5, 0.25]
        }
        result = engine.validate(data)
        assert result['results']['monotonicity']['score'] >= 0.9
    
    def test_stability_pattern(self, engine):
        """Test stability pattern with stable values"""
        data = {
            'signal_values': [1.0, 0.98, 0.96, 0.94, 0.92]
        }
        result = engine.validate(data)
        assert result['results']['stability']['score'] >= 0.7


class TestContractEngine:
    """Test suite for Contract Engine"""
    
    @pytest.fixture
    def engine(self):
        """Setup Contract Engine"""
        from Contract_Engine import ContractEngine
        engine = ContractEngine()
        
        # Add field definitions
        engine.field_definitions = {
            'risk_factor_scalar': {
                'type': 'float',
                'range': '[0.25,0.5,1.0]'
            },
            'broker_trust_score': {
                'type': 'float',
                'range': '0.0-1.0'
            },
            'veto': {
                'type': 'bool'
            }
        }
        return engine
    
    def test_all_fields_valid(self, engine):
        """Test all fields pass validation"""
        data = {
            'risk_factor_scalar': 0.5,
            'broker_trust_score': 0.8,
            'veto': False
        }
        result = engine.validate(data)
        assert result['contract_score'] == 1.0
    
    def test_missing_field(self, engine):
        """Test missing field detection"""
        data = {
            'risk_factor_scalar': 0.5,
            'veto': False
            # broker_trust_score missing
        }
        result = engine.validate(data)
        assert result['contract_score'] < 1.0
        assert 'broker_trust_score' in result['results']
        assert result['results']['broker_trust_score'] == 'MISSING'
    
    def test_type_mismatch(self, engine):
        """Test type mismatch detection"""
        data = {
            'risk_factor_scalar': "0.5",  # String instead of float
            'broker_trust_score': 0.8,
            'veto': False
        }
        result = engine.validate(data)
        assert result['results']['risk_factor_scalar'] == 'TYPE_MISMATCH'
    
    def test_range_violation(self, engine):
        """Test range violation detection"""
        data = {
            'risk_factor_scalar': 0.75,  # Not in allowed set
            'broker_trust_score': 0.8,
            'veto': False
        }
        result = engine.validate(data)
        assert result['results']['risk_factor_scalar'] == 'RANGE_VIOLATION'


class TestScenarioEngine:
    """Test suite for Scenario Engine"""
    
    @pytest.fixture
    def engine(self):
        """Setup Scenario Engine"""
        from Scenario_Engine import ScenarioEngine
        return ScenarioEngine()
    
    def test_low_trust_scenario(self, engine):
        """Test low trust score scenario"""
        data = {
            'broker_trust_score': 0.2,
            'risk_factor_scalar': 0.25
        }
        result = engine.validate(data)
        
        # Find SC_001 result
        sc_001 = next(r for r in result['results'] if r['id'] == 'SC_001')
        assert sc_001['status'] == 'PASS'
    
    def test_drawdown_limit_scenario(self, engine):
        """Test drawdown limit exceeded scenario"""
        data = {
            'equity_drawdown': 0.06,
            'max_daily_drawdown_limit': 0.05,
            'guard_veto': True
        }
        result = engine.validate(data)
        
        # Find SC_002 result
        sc_002 = next(r for r in result['results'] if r['id'] == 'SC_002')
        assert sc_002['status'] == 'PASS'
    
    def test_connection_lost_scenario(self, engine):
        """Test connection lost scenario"""
        data = {
            'connection_alive': False,
            'allow_new_trades': False
        }
        result = engine.validate(data)
        
        # Find SC_006 result
        sc_006 = next(r for r in result['results'] if r['id'] == 'SC_006')
        assert sc_006['status'] == 'PASS'


class TestAIELTEngine:
    """Test suite for full AIEL-T Engine"""
    
    @pytest.fixture
    def engine(self):
        """Setup AIEL-T Engine"""
        engine = AIELTEngine()
        
        # Setup invariants
        engine.invariants_engine.invariants = {
            'INV_001_RISK_FACTOR_VALID': {'rule': 'risk_factor_scalar in [0.25,0.5,1.0]'}
        }
        
        # Setup contracts
        engine.contract_engine.field_definitions = {
            'risk_factor_scalar': {'type': 'float', 'range': '[0.25,0.5,1.0]'}
        }
        
        return engine
    
    def test_full_run_pass(self, engine):
        """Test full AIEL-T run with passing data"""
        data = {
            'risk_factor_scalar': 0.5,
            'broker_trust_score': 0.8,
            'equity_drawdown': 0.03,
            'max_daily_drawdown_limit': 0.05,
            'veto': False,
            'timestamps': ['2024-12-01T00:00:00Z', '2024-12-01T01:00:00Z'],
            'latencies_ms': [10, 15, 12],
            'target_max_latency_ms': 50,
            'target_avg_latency_ms': 25,
            'trust_score_sequence': [1.0, 0.9],
            'risk_factor_sequence': [1.0, 0.5],
            'signal_values': [1.0, 0.98],
            'boundary_tests': [{'correct_behavior': True}],
            'error_cases': [{'defaulted_to_safe': True}],
            'connection_alive': True,
            'allow_new_trades': True
        }
        
        result = engine.run(data)
        
        assert 'G_score' in result
        assert result['G_score'] >= 0.0
        assert result['G_score'] <= 1.0
        assert 'status' in result
        assert result['status'] in ['DEPLOYABLE', 'REVISION_REQUIRED', 'REJECT']
    
    def test_g_score_calculation(self, engine):
        """Test G-Score calculation formula"""
        g_score = engine._calculate_g_score(1.0, 1.0, 1.0, 1.0)
        assert g_score == 1.0
        
        g_score = engine._calculate_g_score(0.0, 0.0, 0.0, 0.0)
        assert g_score == 0.0
        
        # Test weighted average
        g_score = engine._calculate_g_score(1.0, 0.8, 0.9, 0.7)
        expected = 0.45 * 1.0 + 0.15 * 0.8 + 0.10 * 0.9 + 0.30 * 0.7
        assert abs(g_score - expected) < 0.0001
    
    def test_status_determination(self, engine):
        """Test status determination logic"""
        assert engine._determine_status(0.97) == 'DEPLOYABLE'
        assert engine._determine_status(0.88) == 'REVISION_REQUIRED'
        assert engine._determine_status(0.70) == 'REJECT'


if __name__ == "__main__":
    # Run all tests
    pytest.main([__file__, '-v', '--tb=short'])
