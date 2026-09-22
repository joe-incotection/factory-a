"""
Pattern Engine v1.0
===================

Validates structural and behavioral patterns.
Weight: 15% of G-Score

Contract: AIEL-T_v1.0.md Section 4.2
"""

import logging
from typing import Dict, List, Any
import statistics

logger = logging.getLogger(__name__)


class PatternEngine:
    """
    Pattern Engine - Validates behavioral patterns
    
    Purpose:
    - Detect latency patterns
    - Check monotonicity
    - Validate fail-safe patterns
    - Check boundary behavior
    
    Weight: 15% of G-Score
    """
    
    def __init__(self):
        """Initialize Pattern Engine"""
        self.pattern_checks = [
            self._check_latency_pattern,
            self._check_monotonicity_pattern,
            self._check_boundary_pattern,
            self._check_failsafe_pattern,
            self._check_stability_pattern
        ]
    
    def validate(self, runtime_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate all patterns
        
        Args:
            runtime_data: System performance/behavior data
            
        Returns:
            {
                'pattern_score': float,
                'results': {...},
                'passed': int,
                'total': int
            }
        """
        results = {}
        scores = []
        
        for check in self.pattern_checks:
            try:
                pattern_name = check.__name__.replace('_check_', '').replace('_pattern', '')
                score = check(runtime_data)
                results[pattern_name] = {
                    'score': score,
                    'status': 'PASS' if score >= 0.9 else 'WARN' if score >= 0.7 else 'FAIL'
                }
                scores.append(score)
            except Exception as e:
                logger.error(f"Error in pattern check {check.__name__}: {e}")
                results[pattern_name] = {'score': 0.0, 'status': 'ERROR', 'error': str(e)}
                scores.append(0.0)
        
        pattern_score = statistics.mean(scores) if scores else 0.0
        passed = sum(1 for s in scores if s >= 0.9)
        total = len(scores)
        
        logger.info(f"Patterns: {passed}/{total} passed, avg score {pattern_score:.2%}")
        
        return {
            'pattern_score': pattern_score,
            'results': results,
            'passed': passed,
            'total': total
        }
    
    def _check_latency_pattern(self, data: Dict) -> float:
        """
        Check latency is within acceptable bounds
        
        Returns: 0.0-1.0 score
        """
        latencies = data.get('latencies_ms', [])
        if not latencies:
            return 1.0  # No data = assume OK
        
        max_latency = max(latencies)
        avg_latency = statistics.mean(latencies)
        target_max = data.get('target_max_latency_ms', 100)
        target_avg = data.get('target_avg_latency_ms', 50)
        
        # Score based on how well we meet targets
        max_score = 1.0 if max_latency <= target_max else max(0.0, 1.0 - (max_latency - target_max) / target_max)
        avg_score = 1.0 if avg_latency <= target_avg else max(0.0, 1.0 - (avg_latency - target_avg) / target_avg)
        
        return (max_score + avg_score) / 2
    
    def _check_monotonicity_pattern(self, data: Dict) -> float:
        """
        Check that trust/risk relationship is monotonic
        
        Returns: 0.0-1.0 score
        """
        trust_scores = data.get('trust_score_sequence', [])
        risk_factors = data.get('risk_factor_sequence', [])
        
        if len(trust_scores) < 2 or len(risk_factors) < 2:
            return 1.0  # Not enough data
        
        if len(trust_scores) != len(risk_factors):
            return 0.5  # Mismatched data
        
        violations = 0
        for i in range(1, len(trust_scores)):
            # If trust decreased, risk should not increase
            if trust_scores[i] < trust_scores[i-1]:
                if risk_factors[i] > risk_factors[i-1]:
                    violations += 1
        
        total_checks = len(trust_scores) - 1
        if total_checks == 0:
            return 1.0
        
        score = 1.0 - (violations / total_checks)
        return max(0.0, score)
    
    def _check_boundary_pattern(self, data: Dict) -> float:
        """
        Check behavior at boundaries (limits)
        
        Returns: 0.0-1.0 score
        """
        boundary_tests = data.get('boundary_tests', [])
        if not boundary_tests:
            return 1.0  # No boundary tests
        
        passed = sum(1 for test in boundary_tests if test.get('correct_behavior', False))
        total = len(boundary_tests)
        
        return passed / total if total > 0 else 0.0
    
    def _check_failsafe_pattern(self, data: Dict) -> float:
        """
        Check that system defaults to safe state on error
        
        Returns: 0.0-1.0 score
        """
        error_cases = data.get('error_cases', [])
        if not error_cases:
            return 1.0  # No errors = assume safe
        
        safe_defaults = sum(1 for case in error_cases if case.get('defaulted_to_safe', False))
        total = len(error_cases)
        
        return safe_defaults / total if total > 0 else 0.0
    
    def _check_stability_pattern(self, data: Dict) -> float:
        """
        Check stability (no oscillations, spikes)
        
        Returns: 0.0-1.0 score
        """
        values = data.get('signal_values', [])
        if len(values) < 3:
            return 1.0  # Not enough data
        
        # Check for rapid oscillations
        changes = [abs(values[i] - values[i-1]) for i in range(1, len(values))]
        if not changes:
            return 1.0
        
        avg_change = statistics.mean(changes)
        max_change = max(changes)
        
        # Good stability: small average change, no huge spikes
        stability_score = 1.0
        
        if avg_change > 0.2:  # Average change > 20%
            stability_score *= 0.7
        
        if max_change > 0.5:  # Any single change > 50%
            stability_score *= 0.5
        
        # Check for oscillation pattern (up-down-up-down)
        oscillations = 0
        for i in range(2, len(values)):
            if (values[i] - values[i-1]) * (values[i-1] - values[i-2]) < 0:
                oscillations += 1
        
        if oscillations > len(values) * 0.5:  # >50% oscillating
            stability_score *= 0.5
        
        return max(0.0, stability_score)


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    engine = PatternEngine()
    
    # Test data
    test_data = {
        'latencies_ms': [10, 15, 12, 18, 20, 14],
        'target_max_latency_ms': 50,
        'target_avg_latency_ms': 25,
        'trust_score_sequence': [1.0, 0.8, 0.6, 0.4, 0.2],
        'risk_factor_sequence': [1.0, 0.5, 0.5, 0.25, 0.25],
        'signal_values': [1.0, 0.95, 0.92, 0.90, 0.88],
        'boundary_tests': [
            {'correct_behavior': True},
            {'correct_behavior': True},
            {'correct_behavior': False}
        ],
        'error_cases': [
            {'defaulted_to_safe': True},
            {'defaulted_to_safe': True}
        ]
    }
    
    result = engine.validate(test_data)
    print(f"Pattern Score: {result['pattern_score']:.2%}")
    print(f"Results: {result['results']}")