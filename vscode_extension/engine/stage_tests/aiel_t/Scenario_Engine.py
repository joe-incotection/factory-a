"""
Scenario Engine v1.0
====================

Simulates critical scenarios and validates system resilience.
Weight: 30% of G-Score

Contract: AIEL-T_v1.0.md Section 4.4
"""

import logging
from typing import Dict, List, Any, Callable

logger = logging.getLogger(__name__)


class ScenarioEngine:
    """
    Scenario Engine - Tests system resilience
    
    Purpose:
    - Simulate critical failure conditions
    - Test stress scenarios
    - Validate recovery behavior
    
    Weight: 30% of G-Score
    """
    
    def __init__(self):
        """Initialize Scenario Engine"""
        self.scenarios = []
        self.results = []
        self._register_default_scenarios()
    
    def _register_default_scenarios(self):
        """Register default scenarios for trading systems"""
        self.scenarios = [
            {
                'id': 'SC_001',
                'name': 'Low Trust Score',
                'condition': lambda d: d.get('broker_trust_score', 1.0) < 0.3,
                'expected': lambda d: d.get('risk_factor_scalar', 1.0) <= 0.5,
                'description': 'When trust < 0.3, risk must be <= 0.5'
            },
            {
                'id': 'SC_002',
                'name': 'Drawdown Limit Exceeded',
                'condition': lambda d: d.get('equity_drawdown', 0) > d.get('max_daily_drawdown_limit', 0.05),
                'expected': lambda d: d.get('guard_veto', False) == True,
                'description': 'When DD > limit, guard must veto'
            },
            {
                'id': 'SC_003',
                'name': 'Spread Spike',
                'condition': lambda d: d.get('spread_points', 0) > d.get('normal_spread', 2) * 3,
                'expected': lambda d: d.get('position_size_reduced', False) == True,
                'description': 'When spread spikes 3x, reduce size'
            },
            {
                'id': 'SC_004',
                'name': 'Missing Data Bar',
                'condition': lambda d: d.get('data_has_gaps', False) == True,
                'expected': lambda d: d.get('data_rejected', False) == True,
                'description': 'M8 must auto-reject dataset with gaps'
            },
            {
                'id': 'SC_005',
                'name': 'Price Anomaly Detected',
                'condition': lambda d: d.get('price_anomaly_detected', False) == True,
                'expected': lambda d: d.get('policy_mode', '') in ['DEFENSIVE', 'CONSERVATIVE'],
                'description': 'Price anomaly must trigger defensive mode'
            },
            {
                'id': 'SC_006',
                'name': 'Connection Lost',
                'condition': lambda d: d.get('connection_alive', True) == False,
                'expected': lambda d: d.get('allow_new_trades', True) == False,
                'description': 'Lost connection must block new trades'
            },
            {
                'id': 'SC_007',
                'name': 'High Volatility Regime',
                'condition': lambda d: d.get('volatility_regime', '') == 'EXTREME',
                'expected': lambda d: d.get('risk_factor_scalar', 1.0) < 1.0,
                'description': 'Extreme volatility must reduce risk'
            }
        ]
    
    def add_scenario(self, scenario: Dict[str, Any]):
        """
        Add custom scenario
        
        Args:
            scenario: {
                'id': str,
                'name': str,
                'condition': callable,
                'expected': callable,
                'description': str
            }
        """
        self.scenarios.append(scenario)
    
    def validate(self, runtime_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run all scenarios and validate behavior
        
        Args:
            runtime_data: System state data
            
        Returns:
            {
                'scenario_score': float,
                'results': [...],
                'passed': int,
                'total': int,
                'failures': [...]
            }
        """
        results = []
        failures = []
        
        for scenario in self.scenarios:
            try:
                # Check if condition triggered
                condition_met = scenario['condition'](runtime_data)
                
                if condition_met:
                    # Check if expected behavior occurred
                    expected_met = scenario['expected'](runtime_data)
                    
                    result = {
                        'id': scenario['id'],
                        'name': scenario['name'],
                        'condition_triggered': True,
                        'expected_behavior': expected_met,
                        'status': 'PASS' if expected_met else 'FAIL'
                    }
                    
                    if not expected_met:
                        failures.append({
                            'id': scenario['id'],
                            'name': scenario['name'],
                            'description': scenario['description'],
                            'data': runtime_data
                        })
                else:
                    # Condition not triggered - N/A
                    result = {
                        'id': scenario['id'],
                        'name': scenario['name'],
                        'condition_triggered': False,
                        'status': 'N/A'
                    }
                
                results.append(result)
                
            except Exception as e:
                logger.error(f"Error in scenario {scenario.get('id', 'unknown')}: {e}")
                results.append({
                    'id': scenario.get('id', 'unknown'),
                    'status': 'ERROR',
                    'error': str(e)
                })
        
        # Calculate score - only count triggered scenarios
        triggered = [r for r in results if r.get('condition_triggered', False)]
        if not triggered:
            logger.warning("No scenarios triggered - using default score 1.0")
            score = 1.0
            passed = 0
            total = 0
        else:
            passed = sum(1 for r in triggered if r.get('status') == 'PASS')
            total = len(triggered)
            score = passed / total if total > 0 else 0.0
        
        logger.info(f"Scenarios: {passed}/{total} passed ({score:.2%})")
        
        return {
            'scenario_score': score,
            'results': results,
            'passed': passed,
            'total': total,
            'triggered': len(triggered),
            'failures': failures
        }


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    engine = ScenarioEngine()
    
    # Test data - low trust scenario
    test_data = {
        'broker_trust_score': 0.2,  # Low!
        'risk_factor_scalar': 0.25,  # Should be reduced
        'equity_drawdown': 0.06,
        'max_daily_drawdown_limit': 0.05,
        'guard_veto': True,  # Should veto
        'connection_alive': True,
        'allow_new_trades': False
    }
    
    result = engine.validate(test_data)
    print(f"Scenario Score: {result['scenario_score']:.2%}")
    print(f"Passed: {result['passed']}/{result['triggered']} triggered")
    print(f"Results: {result['results']}")