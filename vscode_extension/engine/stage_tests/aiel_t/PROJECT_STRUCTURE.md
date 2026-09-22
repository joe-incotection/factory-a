# 📂 AIEL-T Framework - Project Structure

This document explains the organization and purpose of each file in the AIEL-T Framework.

---

## 📁 Directory Layout

```
aiel_t_framework_v1.0/
│
├── Core Engine Files (The 4 Engines + Orchestrator)
│   ├── AIEL_T_Engine.py          ★ Main orchestrator
│   ├── Invariants_Engine.py      ★ Invariants validation (45%)
│   ├── Pattern_Engine.py         ★ Pattern analysis (15%)
│   ├── Contract_Engine.py        ★ Contract compliance (10%)
│   └── Scenario_Engine.py        ★ Scenario simulation (30%)
│
├── Supporting Files
│   ├── Report_Generator.py       Generates MD/HTML/JSON reports
│   ├── aiel_t_cli.py             Command-line interface
│   └── test_aiel_t.py            Full test suite (pytest)
│
├── Configuration & Data
│   ├── config.yaml               Sample configuration file
│   ├── runtime_data.json         Sample runtime data
│   └── requirements.txt          Python dependencies
│
├── Documentation
│   ├── README.md                 Main documentation
│   ├── GETTING_STARTED.md        Quick start guide
│   ├── PROJECT_STRUCTURE.md      This file
│   └── LICENSE                   MIT License
│
└── Sample Reports (Generated)
    └── sample_reports/
        ├── quick_test_report.json
        ├── quick_test_report.md
        └── quick_test_report.html
```

---

## 📄 File Descriptions

### Core Engine Files

#### `AIEL_T_Engine.py` ⭐ Main Orchestrator
**Purpose:** Coordinates all 4 engines and calculates G-Score

**Key Classes:**
- `AIELTEngine` - Main orchestrator class

**Key Methods:**
- `run(runtime_data)` - Execute all validation engines
- `_calculate_g_score()` - Calculate weighted G-Score
- `_determine_status()` - Determine deployment status
- `save_report()` - Save results to JSON
- `print_summary()` - Print formatted summary

**Used By:** CLI, direct Python integration

**Weight:** Orchestrates 100% of validation

---

#### `Invariants_Engine.py` ⭐ Invariants Validator
**Purpose:** Validate hard constraints that must never be violated

**Key Classes:**
- `InvariantsEngine` - Validates invariant rules

**Key Methods:**
- `load_invariants(file_path)` - Load rules from YAML
- `validate(runtime_data)` - Check all invariants
- `_check_invariant()` - Check single invariant

**Input:** YAML file with invariant rules
**Output:** Pass/Fail for each rule + pass rate

**Weight:** 45% of G-Score

**Example Invariants:**
- INV_001: Risk factor must be in [0.25, 0.5, 1.0]
- INV_002: If trust < 0.5 then risk <= 0.5
- INV_003: If drawdown > limit then veto = true

---

#### `Pattern_Engine.py` ⭐ Pattern Analyzer
**Purpose:** Analyze behavioral patterns for quality indicators

**Key Classes:**
- `PatternEngine` - Analyzes behavioral patterns

**Key Methods:**
- `validate(runtime_data)` - Check all patterns
- `_check_latency_pattern()` - Latency analysis
- `_check_monotonicity_pattern()` - Monotonicity check
- `_check_boundary_pattern()` - Boundary behavior
- `_check_failsafe_pattern()` - Fail-safe defaults
- `_check_stability_pattern()` - Stability analysis

**Output:** Score 0.0-1.0 for each pattern

**Weight:** 15% of G-Score

**Patterns Checked:**
1. Latency (within bounds?)
2. Monotonicity (trust-risk relationship)
3. Boundary (correct behavior at limits)
4. Fail-Safe (safe defaults on error)
5. Stability (no oscillations/spikes)

---

#### `Contract_Engine.py` ⭐ Contract Validator
**Purpose:** Validate compliance with specification contracts

**Key Classes:**
- `ContractEngine` - Validates spec compliance

**Key Methods:**
- `load_contract(file_path)` - Load spec files (YAML/MD)
- `validate(runtime_data)` - Check all contracts
- `_check_type()` - Validate field types
- `_check_range()` - Validate value ranges
- `validate_cross_layer()` - Cross-layer consistency

**Input:** Spec files (YAML or Markdown)
**Output:** Score based on matched fields / total fields

**Weight:** 10% of G-Score

**Checks:**
- Field existence
- Type correctness (str, int, float, bool, list, dict)
- Range constraints ([0.25,0.5,1.0], 0.0-1.0, >0, >=0, etc.)
- Cross-layer consistency

---

#### `Scenario_Engine.py` ⭐ Scenario Simulator
**Purpose:** Simulate critical failure scenarios and validate resilience

**Key Classes:**
- `ScenarioEngine` - Tests system resilience

**Key Methods:**
- `_register_default_scenarios()` - Setup default scenarios
- `add_scenario()` - Add custom scenario
- `validate(runtime_data)` - Run all scenarios

**Output:** Pass/Fail for triggered scenarios + pass rate

**Weight:** 30% of G-Score

**Default Scenarios:**
- SC_001: Low Trust Score (trust < 0.3 → risk <= 0.5)
- SC_002: Drawdown Limit Exceeded (DD > limit → veto)
- SC_003: Spread Spike (spread > 3x normal → reduce size)
- SC_004: Missing Data Bar (gaps → reject)
- SC_005: Price Anomaly (anomaly → defensive mode)
- SC_006: Connection Lost (disconnected → block trades)
- SC_007: High Volatility (extreme vol → reduce risk)

---

### Supporting Files

#### `Report_Generator.py`
**Purpose:** Generate formatted reports from test results

**Key Classes:**
- `ReportGenerator` - Static methods for report generation

**Key Methods:**
- `generate_markdown()` - Create MD report
- `generate_html()` - Create HTML report

**Outputs:**
- Markdown (.md) - Human-readable, good for docs
- HTML (.html) - Interactive, pretty, for presentations
- JSON is handled by main engine

---

#### `aiel_t_cli.py`
**Purpose:** Command-line interface for easy execution

**Key Functions:**
- `main()` - CLI entry point
- `run_quick_test()` - Run with sample data
- `run_full_validation()` - Run with custom config/data
- `setup_logging()` - Configure logging

**Usage:**
```bash
python aiel_t_cli.py --quick-test
python aiel_t_cli.py --config config.yaml --data runtime_data.json
```

---

#### `test_aiel_t.py`
**Purpose:** Comprehensive test suite using pytest

**Test Classes:**
- `TestInvariantsEngine` - Tests for invariants
- `TestPatternEngine` - Tests for patterns
- `TestContractEngine` - Tests for contracts
- `TestScenarioEngine` - Tests for scenarios
- `TestAIELTEngine` - Tests for main engine

**Usage:**
```bash
pytest test_aiel_t.py -v
```

---

### Configuration Files

#### `config.yaml`
Sample configuration file showing all available options.

**Key Sections:**
- `meta` - Project metadata
- `spec_sources` - Paths to spec files
- `targets` - Modules to test
- `test_outputs` - Output directories
- `scoring` - Weights and thresholds

---

#### `runtime_data.json`
Sample runtime data showing expected format.

**Key Sections:**
- `invariants_data` - Data for invariants engine
- `pattern_data` - Data for pattern engine
- `scenario_data` - Data for scenario engine
- `contract_data` - Data for contract engine

---

#### `requirements.txt`
Python package dependencies.

**Required:**
- `pyyaml>=6.0` - YAML parsing
- `pytest>=7.4.0` - Testing framework

**Optional:**
- `colorama>=0.4.6` - Colored output
- `tabulate>=0.9.0` - Pretty tables

---

## 🔄 Data Flow

```
1. User provides:
   - config.yaml (configuration)
   - runtime_data.json (system data)

2. CLI loads config and data
   ↓
3. AIEL_T_Engine orchestrator
   ↓
4. Each engine validates:
   - Invariants_Engine → Pass/Fail
   - Pattern_Engine → Score 0.0-1.0
   - Contract_Engine → Score 0.0-1.0
   - Scenario_Engine → Pass/Fail
   ↓
5. Calculate G-Score
   ↓
6. Determine Status
   ↓
7. Generate Reports:
   - JSON (machine-readable)
   - Markdown (human-readable)
   - HTML (presentation)
```

---

## 🎯 Entry Points

### For End Users
- **CLI:** `aiel_t_cli.py` - Quick test or full validation
- **Quick Test:** No config needed, uses sample data

### For Developers
- **Python API:** Import `AIELTEngine` directly
- **Testing:** Run `pytest test_aiel_t.py`

### For CI/CD
- **Exit Codes:** 0 = PASS, 1 = FAIL
- **Reports:** Parse JSON output for automation

---

## 📊 Weight Distribution

```
Total G-Score = 1.0 (100%)

├─ Invariants Engine: 0.45 (45%)
├─ Scenario Engine:   0.30 (30%)
├─ Pattern Engine:    0.15 (15%)
└─ Contract Engine:   0.10 (10%)
```

**Rationale:**
- **Invariants (45%):** Most critical - hard constraints
- **Scenarios (30%):** Very important - resilience testing
- **Patterns (15%):** Important - quality indicators
- **Contracts (10%):** Baseline - spec compliance

---

## 🔧 Extending AIEL-T

### Add Custom Invariant
Edit your `invariants.yaml`:
```yaml
INV_CUSTOM_001:
  rule: your_field in [allowed_values]
```

### Add Custom Pattern Check
Edit `Pattern_Engine.py`, add method:
```python
def _check_my_pattern(self, data: Dict) -> float:
    # Your logic here
    return score  # 0.0 to 1.0
```

### Add Custom Scenario
```python
engine.scenario_engine.add_scenario({
    'id': 'SC_CUSTOM_001',
    'name': 'My Scenario',
    'condition': lambda d: d.get('field') > threshold,
    'expected': lambda d: d.get('response') == expected_value,
    'description': 'What this tests'
})
```

---

## 📞 Support

For questions about specific files or extending the framework:
- 📖 Read README.md for overview
- 🚀 Read GETTING_STARTED.md for quick start
- 📧 Contact: support@aiel-factory.com

---

*AIEL-T Framework v1.0 - Project Structure Documentation*
