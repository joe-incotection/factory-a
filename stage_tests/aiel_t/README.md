# 🧪 AIEL-T Framework v1.0

**Automated Intelligence Evaluation Layer — Test & Verification Engine**

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/aiel-factory/aiel-t)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [G-Score Formula](#g-score-formula)
- [Engine Details](#engine-details)
- [Configuration](#configuration)
- [Reports](#reports)
- [Testing](#testing)
- [Contributing](#contributing)

---

## 🎯 Overview

AIEL-T is a **generic test & verification framework** for validating the structural integrity, behavioral patterns, and contract compliance of any software system.

Originally designed for trading systems (Python Brain + ControlLayer), AIEL-T is **language-agnostic** and can be applied to:
- Trading systems
- APIs and microservices
- Data pipelines
- IoT systems
- Any rule-based software

### Purpose

1. ✅ Validate **Invariant Rules** (hard constraints)
2. 📊 Analyze **Structural Patterns** (behavioral quality)
3. 📝 Check **Contract Compliance** (spec adherence)
4. 🎭 Simulate **Critical Scenarios** (resilience testing)
5. ⭐ Calculate **G-Score** (deployment readiness)

---

## 🏗️ Architecture

AIEL-T consists of **4 independent engines** that combine to produce a final G-Score:

```
┌─────────────────────────────────────────────────────┐
│              AIEL-T Framework v1.0                  │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌──────────────────┐  ┌──────────────────┐        │
│  │ 1. Invariants    │  │ 2. Patterns      │        │
│  │    Engine        │  │    Engine        │        │
│  │    (45%)         │  │    (15%)         │        │
│  └──────────────────┘  └──────────────────┘        │
│                                                      │
│  ┌──────────────────┐  ┌──────────────────┐        │
│  │ 3. Contract      │  │ 4. Scenarios     │        │
│  │    Engine        │  │    Engine        │        │
│  │    (10%)         │  │    (30%)         │        │
│  └──────────────────┘  └──────────────────┘        │
│                                                      │
│  ─────────────────────────────────────────────      │
│                    ↓                                 │
│              G-SCORE CALCULATION                     │
│         (Weighted Average of 4 Engines)              │
│                    ↓                                 │
│    🟢 DEPLOYABLE | 🟡 REVISION | 🔴 REJECT          │
└─────────────────────────────────────────────────────┘
```

---

## ✨ Features

### Core Capabilities

- ⚡ **4 Validation Engines** with weighted scoring
- 📊 **G-Score Calculation** (0.0 - 1.0)
- 🎯 **Configurable Thresholds** (PASS ≥ 0.95, REVISION ≥ 0.80)
- 📝 **Multiple Report Formats** (JSON, Markdown, HTML)
- 🔧 **CLI Tool** for easy execution
- 🧪 **Full Test Suite** with pytest

### Engine Breakdown

| Engine | Weight | Purpose |
|--------|--------|---------|
| **Invariants** | 45% | Validate hard constraints (pass/fail rules) |
| **Patterns** | 15% | Analyze behavioral patterns (latency, monotonicity, stability) |
| **Contracts** | 10% | Check spec compliance (field types, ranges, existence) |
| **Scenarios** | 30% | Test critical failure conditions and resilience |

---

## 📦 Installation

### Prerequisites

- Python 3.10 or higher
- pip package manager

### Install Dependencies

```bash
# Clone repository
git clone https://github.com/aiel-factory/aiel-t.git
cd aiel-t

# Install dependencies
pip install -r requirements.txt

# Or install manually
pip install pyyaml pytest
```

### Verify Installation

```bash
python aiel_t_cli.py --version
# Output: AIEL-T v1.0
```

---

## 🚀 Quick Start

### 1. Run Quick Test (Sample Data)

```bash
python aiel_t_cli.py --quick-test
```

This runs AIEL-T with built-in sample data and generates reports in `./aiel_t_output/`

### 2. Run with Your Data

```bash
python aiel_t_cli.py --config config.yaml --data runtime_data.json
```

### 3. View Reports

```bash
# JSON report
cat aiel_t_output/aiel_t_report.json

# Markdown report
cat aiel_t_output/aiel_t_report.md

# HTML report (open in browser)
open aiel_t_output/aiel_t_report.html
```

---

## 📚 Usage

### Command-Line Interface

```bash
# Quick test
python aiel_t_cli.py --quick-test

# Full validation
python aiel_t_cli.py --config config.yaml --data runtime_data.json

# Custom output directory
python aiel_t_cli.py --config config.yaml --data runtime_data.json --output ./reports

# Verbose logging
python aiel_t_cli.py --quick-test --verbose

# Show help
python aiel_t_cli.py --help
```

### Python API

```python
from AIEL_T_Engine import AIELTEngine

# Create engine
config = {
    'invariants_file': 'invariants.yaml',
    'spec_files': ['spec1.yaml', 'spec2.md']
}
engine = AIELTEngine(config)

# Prepare runtime data
runtime_data = {
    'risk_factor_scalar': 0.5,
    'broker_trust_score': 0.8,
    # ... more fields
}

# Run validation
results = engine.run(runtime_data)

# Check G-Score
print(f"G-Score: {results['G_score']}")
print(f"Status: {results['status']}")

# Save report
engine.save_report(results, 'report.json')
engine.print_summary(results)
```

---

## ⭐ G-Score Formula

```
G = 0.45 × invariant_pass_rate
  + 0.15 × pattern_score
  + 0.10 × contract_score
  + 0.30 × scenario_score
```

### Interpretation

| G-Score | Status | Action |
|---------|--------|--------|
| ≥ 0.95 | 🟢 DEPLOYABLE | Ready for production |
| 0.80 - 0.94 | 🟡 REVISION REQUIRED | Needs improvements |
| < 0.80 | 🔴 REJECT | Critical issues, do not deploy |

---

## 🔍 Engine Details

### 1. Invariants Engine (45%)

**Purpose:** Validate hard constraints that must never be violated.

**Input:** YAML file with invariant rules

```yaml
INV_001_RISK_FACTOR_VALID:
  rule: risk_factor_scalar in [0.25,0.5,1.0]

INV_002_TRUST_RISK_MONOTONICITY:
  rule: if broker_trust_score < 0.5 then risk_factor_scalar <= 0.5
```

**Output:** Pass/Fail for each invariant + overall pass rate

### 2. Pattern Engine (15%)

**Purpose:** Analyze behavioral patterns for quality indicators.

**Patterns Checked:**
- ⏱️ Latency Pattern
- 📈 Monotonicity Pattern
- 🎯 Boundary Pattern
- 🛡️ Fail-Safe Pattern
- 📊 Stability Pattern

**Output:** Score 0.0 - 1.0 for each pattern

### 3. Contract Engine (10%)

**Purpose:** Validate compliance with specification contracts.

**Checks:**
- Field existence
- Type correctness
- Range/constraint validation
- Cross-layer consistency

**Output:** Score based on matched fields / total fields

### 4. Scenario Engine (30%)

**Purpose:** Simulate critical failure scenarios and validate resilience.

**Default Scenarios:**
- SC_001: Low Trust Score
- SC_002: Drawdown Limit Exceeded
- SC_003: Spread Spike
- SC_004: Missing Data Bar
- SC_005: Price Anomaly Detected
- SC_006: Connection Lost
- SC_007: High Volatility Regime

**Output:** Pass/Fail for triggered scenarios + overall pass rate

---

## ⚙️ Configuration

### config.yaml Example

```yaml
meta:
  name: "AIEL-T Framework Config"
  version: "1.0.0"
  domain: "trading/python_brain"

spec_sources:
  master_spec: "specs/Master_Spec.md"
  invariants_file: "specs/Invariants.yaml"

targets:
  - name: "BrokerContext"
    module: "control_layer.broker_context"
    type: "python"

test_outputs:
  root_dir: "tests/aiel_t/"
  reports_dir: "tests/aiel_t/reports/"

scoring:
  weights:
    invariants: 0.45
    patterns: 0.15
    contracts: 0.10
    scenarios: 0.30
  pass_threshold: 0.95
```

### runtime_data.json Example

```json
{
  "risk_factor_scalar": 0.5,
  "broker_trust_score": 0.8,
  "equity_drawdown": 0.03,
  "max_daily_drawdown_limit": 0.05,
  "veto": false,
  "timestamps": ["2024-12-01T00:00:00Z"],
  "latencies_ms": [10, 15, 12],
  "connection_alive": true
}
```

---

## 📊 Reports

AIEL-T generates 3 types of reports:

### 1. JSON Report
```bash
aiel_t_output/aiel_t_report.json
```
Machine-readable, full details, suitable for CI/CD integration.

### 2. Markdown Report
```bash
aiel_t_output/aiel_t_report.md
```
Human-readable, good for documentation and code reviews.

### 3. HTML Report
```bash
aiel_t_output/aiel_t_report.html
```
Beautifully formatted, interactive, perfect for presentations.

---

## 🧪 Testing

### Run All Tests

```bash
pytest test_aiel_t.py -v
```

### Run Specific Engine Tests

```bash
# Test Invariants Engine
pytest test_aiel_t.py::TestInvariantsEngine -v

# Test Pattern Engine
pytest test_aiel_t.py::TestPatternEngine -v

# Test Contract Engine
pytest test_aiel_t.py::TestContractEngine -v

# Test Scenario Engine
pytest test_aiel_t.py::TestScenarioEngine -v

# Test Full AIEL-T Engine
pytest test_aiel_t.py::TestAIELTEngine -v
```

### Test Coverage

```bash
pytest test_aiel_t.py --cov=. --cov-report=html
```

---

## 📂 Project Structure

```
aiel-t/
├── AIEL_T_Engine.py          # Main orchestrator
├── Invariants_Engine.py      # Invariants validation
├── Pattern_Engine.py         # Pattern analysis
├── Contract_Engine.py        # Contract compliance
├── Scenario_Engine.py        # Scenario simulation
├── Report_Generator.py       # Report generation
├── aiel_t_cli.py             # CLI interface
├── test_aiel_t.py            # Test suite
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── config.yaml               # Sample config
└── aiel_t_output/            # Generated reports
    ├── aiel_t_report.json
    ├── aiel_t_report.md
    └── aiel_t_report.html
```

---

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **AIEL Factory** - Framework design and implementation
- **Python Brain Project** - Original use case and requirements
- **ControlLayer Architecture** - Inspiration for multi-layer validation

---

## 📞 Support

- 📧 Email: support@aiel-factory.com
- 🐛 Issues: [GitHub Issues](https://github.com/aiel-factory/aiel-t/issues)
- 📖 Docs: [Full Documentation](https://docs.aiel-factory.com)

---

## 🎯 Roadmap

- [ ] Add support for more file formats (XML, CSV)
- [ ] Implement ML-based pattern detection
- [ ] Add real-time monitoring dashboard
- [ ] Support for distributed testing
- [ ] Integration with CI/CD platforms (Jenkins, GitHub Actions)

---

**Made with ❤️ by AIEL Factory**

*"Test smarter, deploy safer"*
