#!/usr/bin/env python3
"""
M8 Historical Logger - AIEL-T Certification Test
=================================================

Tests M8 Historical Logger using AIEL-T Framework
to certify it meets quality standards (G-Score >= 0.95)
"""

import json
import yaml
import logging
from pathlib import Path
from datetime import datetime

# Import AIEL-T Engines
from AIEL_T_Engine import AIELTEngine
from Invariants_Engine import InvariantsEngine
from Pattern_Engine import PatternEngine
from Contract_Engine import ContractEngine
from Scenario_Engine import ScenarioEngine
from Report_Generator import ReportGenerator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_m8_runtime_data(filepath: str) -> dict:
    """Load M8 runtime data from JSON"""
    with open(filepath, 'r') as f:
        return json.load(f)


def create_m8_specific_invariants(engine: InvariantsEngine, data: dict):
    """Add M8-specific invariant checks"""
    
    # M8-specific invariants (beyond generic YAML)
    m8_invariants = {
        'INV_M8_UTC_FORMAT': {
            'rule': 'All timestamps in UTC ISO 8601 format',
            'check': lambda: all(ts.endswith('Z') for ts in data.get('timestamps', []))
        },
        'INV_M8_SEQUENTIAL': {
            'rule': 'Timestamps must be sequential',
            'check': lambda: data.get('timestamps', []) == sorted(data.get('timestamps', []))
        },
        'INV_M8_OHLC_VALID': {
            'rule': 'OHLCV relationships valid',
            'check': lambda: all(
                ohlc['low'] <= ohlc['open'] <= ohlc['high'] and
                ohlc['low'] <= ohlc['close'] <= ohlc['high']
                for ohlc in data.get('ohlcv_sample', [])
            )
        },
        'INV_M8_QUALITY_GATE': {
            'rule': 'Quality score >= 0.95',
            'check': lambda: data.get('quality_score', 0) >= 0.95
        },
        'INV_M8_MAX_GAPS': {
            'rule': 'Gaps <= 5 (market gaps acceptable)',
            'check': lambda: data.get('gaps_unfilled', 999) <= 5
        },
        'INV_M8_ZERO_ANOMALIES': {
            'rule': 'No anomalies detected',
            'check': lambda: data.get('anomalies_flagged', 999) == 0
        },
        'INV_M8_ALL_VALIDATED': {
            'rule': 'All bars validated',
            'check': lambda: data.get('all_bars_validated', False) == True
        },
        'INV_M8_SYMBOL_CONSISTENT': {
            'rule': 'Symbol consistent across bars',
            'check': lambda: data.get('symbols_consistent', False) == True
        }
    }
    
    return m8_invariants


def create_m8_scenarios(engine: ScenarioEngine):
    """Add M8-specific scenarios"""
    
    # M8 Gap Handling Scenario
    engine.add_scenario({
        'id': 'SC_M8_001',
        'name': 'Gap Handling',
        'condition': lambda d: d.get('gaps_detected', 0) > 0,
        'expected': lambda d: d.get('gaps_unfilled', 999) <= 5,
        'description': 'When gaps detected, must handle correctly (<=5 acceptable)'
    })
    
    # M8 Primary Source Scenario
    engine.add_scenario({
        'id': 'SC_M8_002',
        'name': 'Primary Source Usage',
        'condition': lambda d: d.get('primary_available', False),
        'expected': lambda d: d.get('bars_from_primary', 0) > 0,
        'description': 'When primary available, must use it'
    })
    
    # M8 Data Validation Scenario
    engine.add_scenario({
        'id': 'SC_M8_003',
        'name': 'Data Validation',
        'condition': lambda d: d.get('total_bars', 0) > 0,
        'expected': lambda d: d.get('validated', False) == True,
        'description': 'All fetched data must be validated'
    })
    
    # M8 Quality Gate Scenario
    engine.add_scenario({
        'id': 'SC_M8_004',
        'name': 'Quality Gate',
        'condition': lambda d: True,  # Always check
        'expected': lambda d: d.get('quality_score', 0) >= 0.95,
        'description': 'Quality score must meet threshold'
    })


def validate_m8_contracts(data: dict) -> dict:
    """Validate M8 output contracts"""
    
    violations = []
    
    # Check required fields
    required_fields = [
        'session_id', 'symbol', 'timeframe', 'total_bars',
        'quality_score', 'gaps_unfilled', 'anomalies_flagged',
        'validated', 'primary_source'
    ]
    
    for field in required_fields:
        if field not in data:
            violations.append({
                'type': 'MISSING_FIELD',
                'field': field,
                'severity': 'CRITICAL'
            })
    
    # Check metadata structure
    if 'session_id' in data:
        if not data['session_id'].startswith('m8_'):
            violations.append({
                'type': 'INVALID_FORMAT',
                'field': 'session_id',
                'value': data['session_id'],
                'expected': 'Must start with m8_'
            })
    
    # Check quality score range
    if 'quality_score' in data:
        if not (0.0 <= data['quality_score'] <= 1.0):
            violations.append({
                'type': 'OUT_OF_RANGE',
                'field': 'quality_score',
                'value': data['quality_score'],
                'expected': '0.0 to 1.0'
            })
    
    # Check timestamps format
    if 'timestamps' in data:
        for i, ts in enumerate(data['timestamps'][:10]):  # Check first 10
            if not ts.endswith('Z'):
                violations.append({
                    'type': 'INVALID_TIMESTAMP',
                    'index': i,
                    'value': ts,
                    'expected': 'Must end with Z (UTC)'
                })
                break  # Report only first violation
    
    score = 1.0 if len(violations) == 0 else max(0.0, 1.0 - (len(violations) * 0.1))
    
    return {
        'contract_score': score,
        'violations': violations,
        'total_checks': len(required_fields) + 2,  # Fields + format checks
        'passed': len(required_fields) + 2 - len(violations)
    }


def run_m8_certification():
    """Main certification test"""
    
    print("\n" + "=" * 70)
    print("M8 HISTORICAL LOGGER - AIEL-T CERTIFICATION TEST")
    print("=" * 70)
    
    # Load configuration and data
    logger.info("Loading M8 runtime data...")
    runtime_data = load_m8_runtime_data('m8_runtime_data.json')
    
    logger.info(f"M8 Session: {runtime_data['session_id']}")
    logger.info(f"Symbol: {runtime_data['symbol']}, Timeframe: {runtime_data['timeframe']}")
    logger.info(f"Total Bars: {runtime_data['total_bars']}")
    logger.info(f"Quality Score: {runtime_data['quality_score']:.4f}")
    
    # Create AIEL-T Engine
    config = {
        'invariants_file': 'm8_invariants.yaml',
        'spec_files': []
    }
    
    engine = AIELTEngine(config)
    
    # Add M8-specific invariants
    logger.info("\nAdding M8-specific invariants...")
    m8_invs = create_m8_specific_invariants(engine.invariants_engine, runtime_data)
    
    # Convert to format expected by Invariants Engine
    for inv_id, inv_spec in m8_invs.items():
        engine.invariants_engine.invariants[inv_id] = {
            'rule': inv_spec['rule']
        }
    
    # Add M8-specific scenarios
    logger.info("Adding M8-specific scenarios...")
    create_m8_scenarios(engine.scenario_engine)
    
    # Add M8 contract fields
    logger.info("Configuring M8 contract validation...")
    engine.contract_engine.field_definitions = {
        'session_id': {'type': 'str'},
        'symbol': {'type': 'str'},
        'timeframe': {'type': 'str'},
        'total_bars': {'type': 'int', 'range': '>0'},
        'quality_score': {'type': 'float', 'range': '0.0-1.0'},
        'gaps_unfilled': {'type': 'int', 'range': '>=0'},
        'anomalies_flagged': {'type': 'int', 'range': '>=0'},
        'validated': {'type': 'bool'},
        'primary_source': {'type': 'str'}
    }
    
    # Run AIEL-T validation
    logger.info("\n" + "=" * 70)
    logger.info("RUNNING AIEL-T VALIDATION...")
    logger.info("=" * 70)
    
    # Manual invariant checks (since we have custom logic)
    inv_results = {}
    for inv_id, inv_spec in m8_invs.items():
        try:
            passed = inv_spec['check']()
            inv_results[inv_id] = 'PASS' if passed else 'FAIL'
        except Exception as e:
            logger.error(f"Error checking {inv_id}: {e}")
            inv_results[inv_id] = 'ERROR'
    
    inv_pass_rate = sum(1 for r in inv_results.values() if r == 'PASS') / len(inv_results)
    
    # Inject results into engine
    runtime_data['_invariant_results'] = inv_results
    runtime_data['_invariant_pass_rate'] = inv_pass_rate
    
    # Run full validation
    results = engine.run(runtime_data)
    
    # Override invariant results with our custom checks
    results['invariants']['results'] = inv_results
    results['invariants']['invariant_pass_rate'] = inv_pass_rate
    results['invariants']['passed'] = sum(1 for r in inv_results.values() if r == 'PASS')
    results['invariants']['total'] = len(inv_results)
    
    # Add M8-specific contract validation
    m8_contracts = validate_m8_contracts(runtime_data)
    results['m8_contracts'] = m8_contracts
    
    # Recalculate G-Score with updated invariants
    results['G_score'] = engine._calculate_g_score(
        inv_pass_rate,
        results['patterns']['pattern_score'],
        results['contracts']['contract_score'],
        results['scenarios']['scenario_score']
    )
    results['status'] = engine._determine_status(results['G_score'])
    results['summary'] = engine._generate_summary(results)
    
    # Print summary
    engine.print_summary(results)
    
    # Generate detailed M8 certification report
    print("\n" + "=" * 70)
    print("M8 CERTIFICATION RESULTS")
    print("=" * 70)
    
    print(f"\n📊 M8 Metrics:")
    print(f"  Session ID: {runtime_data['session_id']}")
    print(f"  Total Bars: {runtime_data['total_bars']}")
    print(f"  Quality Score: {runtime_data['quality_score']:.4f}")
    print(f"  Gaps: {runtime_data['gaps_unfilled']} (threshold: ≤5)")
    print(f"  Anomalies: {runtime_data['anomalies_flagged']} (threshold: 0)")
    print(f"  Data Validated: {runtime_data['validated']}")
    
    print(f"\n⭐ AIEL-T Results:")
    print(f"  G-Score: {results['G_score']:.4f}")
    print(f"  Status: {results['status']}")
    print(f"  Invariants: {inv_pass_rate:.2%}")
    print(f"  Patterns: {results['patterns']['pattern_score']:.2%}")
    print(f"  Contracts: {results['contracts']['contract_score']:.2%}")
    print(f"  Scenarios: {results['scenarios']['scenario_score']:.2%}")
    
    # Certification decision
    print(f"\n{'='*70}")
    if results['G_score'] >= 0.95 and runtime_data['quality_score'] >= 0.95:
        print("✅ CERTIFICATION: PASS")
        print("M8 Historical Logger is CERTIFIED for production deployment")
        certification = "PASSED"
    else:
        print("⚠️  CERTIFICATION: REQUIRES REVISION")
        print("M8 Historical Logger needs improvements before deployment")
        certification = "REQUIRES_REVISION"
    print("=" * 70)
    
    # Save reports
    output_dir = Path('tests/m8_aiel_t/reports')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save JSON report
    json_file = output_dir / 'M8_CERTIFICATION_REPORT.json'
    results['certification'] = {
        'status': certification,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'g_score': results['G_score'],
        'm8_quality_score': runtime_data['quality_score'],
        'meets_standards': results['G_score'] >= 0.95
    }
    engine.save_report(results, str(json_file))
    
    # Generate Markdown report
    md_file = output_dir / 'M8_CERTIFICATION_REPORT.md'
    ReportGenerator.generate_markdown(results, str(md_file))
    
    # Generate HTML report
    html_file = output_dir / 'M8_CERTIFICATION_REPORT.html'
    ReportGenerator.generate_html(results, str(html_file))
    
    print(f"\n📄 Reports Generated:")
    print(f"  - {json_file}")
    print(f"  - {md_file}")
    print(f"  - {html_file}")
    
    return results['G_score'] >= 0.95


if __name__ == "__main__":
    try:
        success = run_m8_certification()
        exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Certification test failed: {e}", exc_info=True)
        exit(2)
