# 🚀 Getting Started with AIEL-T v1.0

Welcome to AIEL-T Framework! This guide will get you up and running in 5 minutes.

---

## 📋 Prerequisites

- Python 3.10 or higher
- pip package manager
- Basic understanding of JSON/YAML

---

## ⚡ Quick Start (5 Minutes)

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Run Quick Test

```bash
python aiel_t_cli.py --quick-test
```

That's it! You should see:
- ✅ G-Score: 1.0000
- ✅ Status: DEPLOYABLE
- 📊 Reports generated in `aiel_t_output/`

### Step 3: View Reports

```bash
# View JSON report
cat aiel_t_output/quick_test_report.json

# View Markdown report
cat aiel_t_output/quick_test_report.md

# Open HTML report in browser
# (double-click the file or use 'open' command)
open aiel_t_output/quick_test_report.html
```

---

## 📚 Next Steps

### 1. Customize Configuration

Edit `config.yaml` to match your project:

```yaml
spec_sources:
  invariants_file: "path/to/your/invariants.yaml"

targets:
  - name: "YourModule"
    module: "your_project.your_module"
```

### 2. Prepare Runtime Data

Create `your_runtime_data.json` with your system's actual data:

```json
{
  "risk_factor_scalar": 0.5,
  "broker_trust_score": 0.8,
  "latencies_ms": [10, 15, 12],
  ...
}
```

Use `runtime_data.json` as a template.

### 3. Run Full Validation

```bash
python aiel_t_cli.py --config config.yaml --data your_runtime_data.json
```

### 4. Integrate with Your Code

```python
from AIEL_T_Engine import AIELTEngine

# Create engine
engine = AIELTEngine(config={'invariants_file': 'invariants.yaml'})

# Run validation
results = engine.run(your_runtime_data)

# Check result
if results['status'] == 'DEPLOYABLE':
    print("✅ Ready to deploy!")
else:
    print(f"⚠️  Issues found. G-Score: {results['G_score']}")
```

---

## 🔧 Common Use Cases

### Use Case 1: CI/CD Integration

```bash
# In your CI/CD pipeline
python aiel_t_cli.py --config config.yaml --data runtime_data.json

# Check exit code
if [ $? -eq 0 ]; then
    echo "Tests passed, proceeding with deployment"
else
    echo "Tests failed, blocking deployment"
    exit 1
fi
```

### Use Case 2: Pre-Deployment Validation

```python
# Before deploying your system
engine = AIELTEngine(config)
results = engine.run(production_data)

if results['G_score'] >= 0.95:
    deploy_to_production()
else:
    send_alert_to_team(results['summary']['recommendations'])
```

### Use Case 3: Monitoring Existing System

```python
# Run periodic validation on live system
while True:
    runtime_data = collect_system_metrics()
    results = engine.run(runtime_data)
    
    if results['G_score'] < 0.80:
        trigger_emergency_shutdown()
        alert_team()
    
    time.sleep(3600)  # Check every hour
```

---

## 📊 Understanding G-Score

| G-Score | Status | Meaning |
|---------|--------|---------|
| 0.95 - 1.00 | 🟢 DEPLOYABLE | All checks passed, safe to deploy |
| 0.80 - 0.94 | 🟡 REVISION REQUIRED | Minor issues, needs fixes before deploy |
| 0.00 - 0.79 | 🔴 REJECT | Critical issues, do NOT deploy |

**Formula:**
```
G = 0.45 × Invariants + 0.15 × Patterns + 0.10 × Contracts + 0.30 × Scenarios
```

---

## 🧪 Running Tests

```bash
# Run all tests
pytest test_aiel_t.py -v

# Run specific engine tests
pytest test_aiel_t.py::TestInvariantsEngine -v
pytest test_aiel_t.py::TestPatternEngine -v
pytest test_aiel_t.py::TestContractEngine -v
pytest test_aiel_t.py::TestScenarioEngine -v
```

---

## 📖 Understanding the 4 Engines

### 1. Invariants Engine (45%)
Validates hard constraints that must NEVER be violated.

**Example Invariant:**
```yaml
INV_001_RISK_FACTOR_VALID:
  rule: risk_factor_scalar in [0.25, 0.5, 1.0]
```

### 2. Pattern Engine (15%)
Analyzes behavioral patterns like latency, monotonicity, stability.

**Checks:**
- Is latency within acceptable bounds?
- Are values monotonic where expected?
- Is the system stable (no oscillations)?

### 3. Contract Engine (10%)
Validates compliance with specification contracts.

**Checks:**
- Are all required fields present?
- Are field types correct?
- Are values within allowed ranges?

### 4. Scenario Engine (30%)
Simulates critical failure scenarios.

**Example Scenarios:**
- What happens when trust score drops?
- What happens when connection is lost?
- What happens when drawdown limit is exceeded?

---

## 🆘 Troubleshooting

### Problem: ModuleNotFoundError

**Solution:**
```bash
pip install -r requirements.txt
```

### Problem: G-Score Too Low

**Solution:**
1. Check `summary['recommendations']` in the report
2. Fix the issues mentioned
3. Re-run validation

### Problem: No Scenarios Triggered

**Solution:**
This is OK if your runtime data doesn't trigger any failure scenarios. It means your system is operating normally.

---

## 📞 Getting Help

- 📖 Read the full README.md
- 🐛 Check GitHub Issues
- 📧 Contact: support@aiel-factory.com

---

## 🎯 What's Next?

1. ✅ Run quick test (you did this!)
2. 📝 Customize config.yaml for your project
3. 📊 Prepare your runtime data
4. 🧪 Run full validation
5. 🚀 Integrate with your deployment pipeline

**Congratulations!** You're now ready to use AIEL-T for your project! 🎉

---

*Generated by AIEL-T v1.0 Framework*
