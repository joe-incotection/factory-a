"""
AIEL-T Engine v1.0 (Main Orchestrator)
=======================================

Main orchestrator that combines all 4 engines and calculates G-Score.

Contract: AIEL-T_v1.0.md Section 5
"""

import logging
import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime

# Import all engines
from Invariants_Engine import InvariantsEngine
from Pattern_Engine import PatternEngine
from Contract_Engine import ContractEngine
from Scenario_Engine import ScenarioEngine

logger = logging.getLogger(__name__)


class AIELTEngine:
    """
    AIEL-T Main Orchestrator
    
    Combines:
    - Invariants Engine (45%)
    - Pattern Engine (15%)
    - Contract Engine (10%)
    - Scenario Engine (30%)
    
    Output: G-Score + detailed report
    """
    
    # G-Score weights per spec
    WEIGHTS = {
        'invariants': 0.45,
        'patterns': 0.15,
        'contracts': 0.10,
        'scenarios': 0.30
    }
    
    PASS_THRESHOLD = 0.95
    REVISION_THRESHOLD = 0.80
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize AIEL-T Engine
        
        Args:
            config: Configuration dict with paths and settings
        """
        self.config = config or {}
        
        # Initialize all engines
        self.invariants_engine = InvariantsEngine(
            invariants_file=self.config.get('invariants_file')
        )
        self.pattern_engine = PatternEngine()
        self.contract_engine = ContractEngine(
            spec_files=self.config.get('spec_files', [])
        )
        self.scenario_engine = ScenarioEngine()
        
        logger.info("AIEL-T Engine v1.0 initialized")
    
    def run(self, runtime_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run all validation engines and calculate G-Score
        
        Args:
            runtime_data: Complete runtime data from system
            
        Returns:
            {
                'G_score': float,
                'status': str,
                'invariants': {...},
                'patterns': {...},
                'contracts': {...},
                'scenarios': {...},
                'timestamp': str,
                'summary': {...}
            }
        """
        logger.info("=" * 60)
        logger.info("AIEL-T Engine v1.0 - Starting Validation")
        logger.info("=" * 60)
        
        results = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'config': self.config
        }
        
        # 1. Run Invariants Engine (45%)
        logger.info("\n[1/4] Running Invariants Engine...")
        invariants_result = self.invariants_engine.validate(runtime_data)
        results['invariants'] = invariants_result
        
        # 2. Run Pattern Engine (15%)
        logger.info("\n[2/4] Running Pattern Engine...")
        pattern_result = self.pattern_engine.validate(runtime_data)
        results['patterns'] = pattern_result
        
        # 3. Run Contract Engine (10%)
        logger.info("\n[3/4] Running Contract Engine...")
        contract_result = self.contract_engine.validate(runtime_data)
        results['contracts'] = contract_result
        
        # 4. Run Scenario Engine (30%)
        logger.info("\n[4/4] Running Scenario Engine...")
        scenario_result = self.scenario_engine.validate(runtime_data)
        results['scenarios'] = scenario_result
        
        # Calculate G-Score
        g_score = self._calculate_g_score(
            invariants_result.get('invariant_pass_rate', 0.0),
            pattern_result.get('pattern_score', 0.0),
            contract_result.get('contract_score', 0.0),
            scenario_result.get('scenario_score', 0.0)
        )
        
        results['G_score'] = g_score
        results['status'] = self._determine_status(g_score)
        
        # Generate summary
        results['summary'] = self._generate_summary(results)
        
        logger.info("\n" + "=" * 60)
        logger.info(f"G-Score: {g_score:.4f} ({results['status']})")
        logger.info("=" * 60)
        
        return results
    
    def _calculate_g_score(
        self,
        invariant_score: float,
        pattern_score: float,
        contract_score: float,
        scenario_score: float
    ) -> float:
        """
        Calculate weighted G-Score
        
        Formula:
        G = 0.45 * invariant_pass_rate
          + 0.15 * pattern_score
          + 0.10 * contract_score
          + 0.30 * scenario_score
        """
        g_score = (
            self.WEIGHTS['invariants'] * invariant_score +
            self.WEIGHTS['patterns'] * pattern_score +
            self.WEIGHTS['contracts'] * contract_score +
            self.WEIGHTS['scenarios'] * scenario_score
        )
        
        return round(g_score, 4)
    
    def _determine_status(self, g_score: float) -> str:
        """
        Determine deployment status based on G-Score
        
        Returns:
            'DEPLOYABLE' | 'REVISION_REQUIRED' | 'REJECT'
        """
        if g_score >= self.PASS_THRESHOLD:
            return 'DEPLOYABLE'
        elif g_score >= self.REVISION_THRESHOLD:
            return 'REVISION_REQUIRED'
        else:
            return 'REJECT'
    
    def _generate_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary of all test results"""
        summary = {
            'overall_status': results['status'],
            'g_score': results['G_score'],
            'breakdown': {
                'invariants': {
                    'score': results['invariants'].get('invariant_pass_rate', 0.0),
                    'passed': results['invariants'].get('passed', 0),
                    'total': results['invariants'].get('total', 0),
                    'weight': self.WEIGHTS['invariants']
                },
                'patterns': {
                    'score': results['patterns'].get('pattern_score', 0.0),
                    'passed': results['patterns'].get('passed', 0),
                    'total': results['patterns'].get('total', 0),
                    'weight': self.WEIGHTS['patterns']
                },
                'contracts': {
                    'score': results['contracts'].get('contract_score', 0.0),
                    'matched': results['contracts'].get('matched', 0),
                    'total': results['contracts'].get('total', 0),
                    'weight': self.WEIGHTS['contracts']
                },
                'scenarios': {
                    'score': results['scenarios'].get('scenario_score', 0.0),
                    'passed': results['scenarios'].get('passed', 0),
                    'triggered': results['scenarios'].get('triggered', 0),
                    'weight': self.WEIGHTS['scenarios']
                }
            }
        }
        
        # Collect all failures
        failures = []
        
        if results['invariants'].get('failures'):
            failures.extend([
                {'engine': 'invariants', **f}
                for f in results['invariants']['failures']
            ])
        
        if results['contracts'].get('violations'):
            failures.extend([
                {'engine': 'contracts', **v}
                for v in results['contracts']['violations']
            ])
        
        if results['scenarios'].get('failures'):
            failures.extend([
                {'engine': 'scenarios', **f}
                for f in results['scenarios']['failures']
            ])
        
        summary['total_failures'] = len(failures)
        summary['failures'] = failures[:10]  # Top 10 failures
        
        # Add recommendations
        summary['recommendations'] = self._generate_recommendations(results)
        
        return summary
    
    def _generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        # Check invariants
        inv_score = results['invariants'].get('invariant_pass_rate', 0.0)
        if inv_score < 1.0:
            recommendations.append(
                f"⚠️  Invariants: {inv_score:.1%} pass rate - "
                f"Fix {results['invariants'].get('total', 0) - results['invariants'].get('passed', 0)} "
                f"critical rule violations"
            )
        
        # Check patterns
        pattern_score = results['patterns'].get('pattern_score', 0.0)
        if pattern_score < 0.9:
            recommendations.append(
                f"⚠️  Patterns: {pattern_score:.1%} score - "
                "Review behavioral patterns and stability"
            )
        
        # Check contracts
        contract_score = results['contracts'].get('contract_score', 0.0)
        if contract_score < 0.95:
            recommendations.append(
                f"⚠️  Contracts: {contract_score:.1%} compliance - "
                "Ensure all spec requirements are met"
            )
        
        # Check scenarios
        scenario_score = results['scenarios'].get('scenario_score', 0.0)
        if scenario_score < 0.9:
            recommendations.append(
                f"⚠️  Scenarios: {scenario_score:.1%} pass rate - "
                "Fix resilience issues in critical scenarios"
            )
        
        if not recommendations:
            recommendations.append("✅ All checks passed - System ready for deployment")
        
        return recommendations
    
    def save_report(self, results: Dict[str, Any], output_file: str):
        """
        Save test report to JSON file
        
        Args:
            results: Test results from run()
            output_file: Path to output JSON file
        """
        try:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            
            logger.info(f"Report saved to {output_file}")
        except Exception as e:
            logger.error(f"Failed to save report: {e}")
    
    def print_summary(self, results: Dict[str, Any]):
        """Print formatted summary to console"""
        summary = results.get('summary', {})
        
        print("\n" + "=" * 70)
        print("AIEL-T v1.0 - TEST SUMMARY")
        print("=" * 70)
        print(f"\nG-Score: {results['G_score']:.4f}")
        print(f"Status:  {results['status']}")
        print(f"\nTimestamp: {results['timestamp']}")
        
        print("\n" + "-" * 70)
        print("ENGINE BREAKDOWN:")
        print("-" * 70)
        
        breakdown = summary.get('breakdown', {})
        for engine_name, engine_data in breakdown.items():
            score = engine_data.get('score', 0.0)
            weight = engine_data.get('weight', 0.0)
            
            print(f"\n{engine_name.upper()}")
            print(f"  Score:  {score:.4f} (weight: {weight:.0%})")
            
            if engine_name == 'invariants':
                print(f"  Passed: {engine_data.get('passed', 0)}/{engine_data.get('total', 0)}")
            elif engine_name == 'patterns':
                print(f"  Passed: {engine_data.get('passed', 0)}/{engine_data.get('total', 0)}")
            elif engine_name == 'contracts':
                print(f"  Valid:  {engine_data.get('matched', 0)}/{engine_data.get('total', 0)}")
            elif engine_name == 'scenarios':
                print(f"  Passed: {engine_data.get('passed', 0)}/{engine_data.get('triggered', 0)} triggered")
        
        print("\n" + "-" * 70)
        print("RECOMMENDATIONS:")
        print("-" * 70)
        for rec in summary.get('recommendations', []):
            print(f"  {rec}")
        
        if summary.get('total_failures', 0) > 0:
            print(f"\n⚠️  Total Failures: {summary['total_failures']}")
            print("   (See full report for details)")
        
        print("\n" + "=" * 70)


if __name__ == "__main__":
    # Test AIEL-T Engine
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Sample config
    config = {
        'invariants_file': None,  # Would load from YAML
        'spec_files': []
    }
    
    # Sample runtime data
    test_data = {
        # Invariants data
        'risk_factor_scalar': 0.5,
        'broker_trust_score': 0.7,
        'equity_drawdown': 0.03,
        'max_daily_drawdown_limit': 0.05,
        'veto': False,
        'timestamps': ['2024-12-01T00:00:00Z', '2024-12-01T01:00:00Z'],
        
        # Pattern data
        'latencies_ms': [10, 15, 12, 18, 20],
        'target_max_latency_ms': 50,
        'target_avg_latency_ms': 25,
        'trust_score_sequence': [1.0, 0.9, 0.8, 0.7],
        'risk_factor_sequence': [1.0, 0.5, 0.5, 0.5],
        'signal_values': [1.0, 0.98, 0.96, 0.94],
        'boundary_tests': [{'correct_behavior': True}],
        'error_cases': [{'defaulted_to_safe': True}],
        
        # Scenario data
        'connection_alive': True,
        'allow_new_trades': True
    }
    
    # Run AIEL-T
    engine = AIELTEngine(config)
    
    # Load sample invariants
    engine.invariants_engine.invariants = {
        'INV_001_RISK_FACTOR_VALID': {'rule': 'risk_factor_scalar in [0.25,0.5,1.0]'},
        'INV_002_TRUST_RISK_MONOTONICITY': {'rule': 'if trust < 0.5 then risk <= 0.5'}
    }
    
    # Load sample contracts
    engine.contract_engine.field_definitions = {
        'risk_factor_scalar': {'type': 'float', 'range': '[0.25,0.5,1.0]'},
        'broker_trust_score': {'type': 'float', 'range': '0.0-1.0'}
    }
    
    results = engine.run(test_data)
    
    # Print summary
    engine.print_summary(results)
    
    # Save report
    engine.save_report(results, '/home/claude/aiel_t_report.json')
