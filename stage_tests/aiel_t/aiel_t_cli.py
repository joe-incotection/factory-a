#!/usr/bin/env python3
"""
AIEL-T CLI Runner v1.0
======================

Command-line interface for running AIEL-T validation.

Usage:
    python aiel_t_cli.py --config config.yaml --data runtime_data.json
    python aiel_t_cli.py --quick-test
"""

import argparse
import logging
import json
import yaml
import sys
from pathlib import Path
from AIEL_T_Engine import AIELTEngine
from Report_Generator import ReportGenerator


def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def load_config(config_file: str) -> dict:
    """Load configuration from YAML file"""
    try:
        with open(config_file, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logging.error(f"Failed to load config: {e}")
        sys.exit(1)


def load_runtime_data(data_file: str) -> dict:
    """Load runtime data from JSON file"""
    try:
        with open(data_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load runtime data: {e}")
        sys.exit(1)


def run_quick_test():
    """Run a quick test with sample data"""
    print("\n🧪 Running AIEL-T Quick Test...")
    print("=" * 70)
    
    # Sample config
    config = {
        'invariants_file': None,
        'spec_files': []
    }
    
    # Sample runtime data
    runtime_data = {
        # Invariants data
        'risk_factor_scalar': 0.5,
        'broker_trust_score': 0.8,
        'equity_drawdown': 0.03,
        'max_daily_drawdown_limit': 0.05,
        'veto': False,
        'timestamps': ['2024-12-01T00:00:00Z', '2024-12-01T01:00:00Z'],
        'required_fields': ['risk_factor_scalar', 'broker_trust_score'],
        'actual_data': {'risk_factor_scalar': 0.5, 'broker_trust_score': 0.8},
        
        # Pattern data
        'latencies_ms': [10, 15, 12, 18, 20],
        'target_max_latency_ms': 50,
        'target_avg_latency_ms': 25,
        'trust_score_sequence': [1.0, 0.9, 0.8, 0.7],
        'risk_factor_sequence': [1.0, 0.5, 0.5, 0.5],
        'signal_values': [1.0, 0.98, 0.96, 0.94],
        'boundary_tests': [{'correct_behavior': True}, {'correct_behavior': True}],
        'error_cases': [{'defaulted_to_safe': True}],
        
        # Scenario data
        'connection_alive': True,
        'allow_new_trades': True
    }
    
    # Create engine
    engine = AIELTEngine(config)
    
    # Setup sample invariants
    engine.invariants_engine.invariants = {
        'INV_001_RISK_FACTOR_VALID': {
            'rule': 'risk_factor_scalar in [0.25,0.5,1.0]'
        },
        'INV_002_TRUST_RISK_MONOTONICITY': {
            'rule': 'if broker_trust_score < 0.5 then risk_factor_scalar <= 0.5'
        }
    }
    
    # Setup sample contracts
    engine.contract_engine.field_definitions = {
        'risk_factor_scalar': {'type': 'float', 'range': '[0.25,0.5,1.0]'},
        'broker_trust_score': {'type': 'float', 'range': '0.0-1.0'},
        'veto': {'type': 'bool'}
    }
    
    # Run validation
    results = engine.run(runtime_data)
    
    # Print summary
    engine.print_summary(results)
    
    # Generate reports
    # output_dir = Path('/home/claude/aiel_t_output')
    output_dir = Path("aiel_t_output")
    output_dir.mkdir(exist_ok=True)
    
    json_file = output_dir / 'quick_test_report.json'
    md_file = output_dir / 'quick_test_report.md'
    html_file = output_dir / 'quick_test_report.html'
    
    engine.save_report(results, str(json_file))
    ReportGenerator.generate_markdown(results, str(md_file))
    ReportGenerator.generate_html(results, str(html_file))
    
    print(f"\n📄 Reports saved to: {output_dir}")
    print(f"  - {json_file.name}")
    print(f"  - {md_file.name}")
    print(f"  - {html_file.name}")
    
    return results['G_score'] >= AIELTEngine.PASS_THRESHOLD


def run_full_validation(config_file: str, data_file: str, output_dir: str):
    """Run full AIEL-T validation"""
    print("\n🧪 Running AIEL-T Full Validation...")
    print("=" * 70)
    
    # Load config
    print(f"\n📋 Loading config from: {config_file}")
    config = load_config(config_file)
    
    # Load runtime data
    print(f"📊 Loading runtime data from: {data_file}")
    runtime_data = load_runtime_data(data_file)
    
    # Create engine
    print("\n🔧 Initializing AIEL-T Engine...")
    engine = AIELTEngine(config)
    
    # Run validation
    results = engine.run(runtime_data)
    
    # Print summary
    engine.print_summary(results)
    
    # Save reports
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    json_file = output_path / 'aiel_t_report.json'
    md_file = output_path / 'aiel_t_report.md'
    html_file = output_path / 'aiel_t_report.html'
    
    print(f"\n💾 Saving reports to: {output_dir}")
    engine.save_report(results, str(json_file))
    ReportGenerator.generate_markdown(results, str(md_file))
    ReportGenerator.generate_html(results, str(html_file))
    
    print(f"✅ Reports saved:")
    print(f"  - {json_file}")
    print(f"  - {md_file}")
    print(f"  - {html_file}")
    
    return results['G_score'] >= AIELTEngine.PASS_THRESHOLD


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='AIEL-T v1.0 - Automated Intelligence Evaluation Layer Test Engine',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick test with sample data
  python aiel_t_cli.py --quick-test
  
  # Full validation with config and data
  python aiel_t_cli.py --config config.yaml --data runtime_data.json
  
  # Custom output directory
  python aiel_t_cli.py --config config.yaml --data runtime_data.json --output ./reports
  
  # Verbose logging
  python aiel_t_cli.py --quick-test --verbose
        """
    )
    
    parser.add_argument(
        '--quick-test',
        action='store_true',
        help='Run quick test with sample data'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='Path to YAML config file'
    )
    
    parser.add_argument(
        '--data',
        type=str,
        help='Path to JSON runtime data file'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='./aiel_t_output',
        help='Output directory for reports (default: ./aiel_t_output)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='AIEL-T v1.0'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Validate arguments
    if args.quick_test:
        # Run quick test
        success = run_quick_test()
    elif args.config and args.data:
        # Run full validation
        success = run_full_validation(args.config, args.data, args.output)
    else:
        parser.print_help()
        print("\n❌ Error: Either --quick-test or both --config and --data are required")
        sys.exit(1)
    
    # Exit with appropriate code
    if success:
        print("\n✅ VALIDATION PASSED")
        sys.exit(0)
    else:
        print("\n⚠️  VALIDATION FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
