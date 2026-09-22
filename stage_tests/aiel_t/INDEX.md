# 📚 AIEL-T Framework v1.0 - Complete Index

**Welcome to AIEL-T Framework!** This is your complete index to all files and resources.

---

## 🎯 Start Here

**New to AIEL-T?** Follow this path:

1. 📖 **README.md** - Overview and main documentation (START HERE)
2. 🚀 **GETTING_STARTED.md** - 5-minute quick start guide
3. 🧪 Run: `python aiel_t_cli.py --quick-test`
4. 📊 View reports in `sample_reports/`
5. 📂 **PROJECT_STRUCTURE.md** - Understand the codebase

---

## 📁 File Categories

### 🔧 Core Engine Files (THE HEART OF AIEL-T)

**Main Orchestrator:**
- **AIEL_T_Engine.py** ⭐⭐⭐
  - Main orchestrator that combines all 4 engines
  - Calculates G-Score
  - Determines deployment status
  - **USE THIS:** Import this file in your code
  - Lines: ~350
  - Key Class: `AIELTEngine`

**The 4 Validation Engines:**

1. **Invariants_Engine.py** ⭐⭐⭐ (45% of G-Score)
   - Validates hard constraints
   - Pass/Fail rules
   - YAML-based rules
   - Lines: ~220
   - Key Class: `InvariantsEngine`

2. **Scenario_Engine.py** ⭐⭐⭐ (30% of G-Score)
   - Simulates critical scenarios
   - Tests resilience
   - 7 default scenarios
   - Lines: ~200
   - Key Class: `ScenarioEngine`

3. **Pattern_Engine.py** ⭐⭐ (15% of G-Score)
   - Analyzes behavioral patterns
   - Checks latency, monotonicity, stability
   - Lines: ~200
   - Key Class: `PatternEngine`

4. **Contract_Engine.py** ⭐⭐ (10% of G-Score)
   - Validates spec compliance
   - Type/range checking
   - Lines: ~270
   - Key Class: `ContractEngine`

---

### 🎨 Supporting Files

**Reporting:**
- **Report_Generator.py**
  - Generates Markdown and HTML reports
  - Beautiful formatted output
  - Lines: ~350
  - Key Class: `ReportGenerator`
  - Static methods: `generate_markdown()`, `generate_html()`

**Command-Line Interface:**
- **aiel_t_cli.py** ⭐ (YOUR PRIMARY TOOL)
  - CLI for easy execution
  - Quick test mode
  - Full validation mode
  - Lines: ~220
  - Entry Point: `main()`
  - **USE THIS:** Run from terminal

**Testing:**
- **test_aiel_t.py**
  - Full pytest test suite
  - 19 test cases
  - 94.7% pass rate
  - Lines: ~320
  - Coverage: All engines

---

### 📝 Configuration Files

**Main Config:**
- **config.yaml** ⭐ (CUSTOMIZE THIS)
  - Sample configuration
  - Edit for your project
  - Paths to spec files
  - Engine weights
  - Thresholds

**Sample Data:**
- **runtime_data.json** ⭐ (TEMPLATE FOR YOUR DATA)
  - Example runtime data
  - Shows expected format
  - Use as template
  - Contains all required fields

**Dependencies:**
- **requirements.txt**
  - Python packages needed
  - pyyaml, pytest
  - Run: `pip install -r requirements.txt`

---

### 📚 Documentation Files

**Must Read (in order):**

1. **README.md** ⭐⭐⭐ (START HERE - 5 minutes)
   - Complete overview
   - Feature list
   - Quick examples
   - G-Score formula

2. **GETTING_STARTED.md** ⭐⭐⭐ (NEXT - 5 minutes)
   - Step-by-step setup
   - Quick test walkthrough
   - Common use cases
   - Troubleshooting

3. **PROJECT_STRUCTURE.md** ⭐⭐ (For developers)
   - File organization
   - Data flow
   - Entry points
   - How to extend

4. **CHANGELOG.md** ⭐ (Version history)
   - Release notes
   - Feature changes
   - Known issues
   - Roadmap

5. **LICENSE** (Legal)
   - MIT License
   - Open source
   - Commercial use allowed

---

### 📊 Sample Reports (Generated)

In `sample_reports/` directory:

- **quick_test_report.json**
  - Machine-readable
  - Full details
  - For CI/CD integration

- **quick_test_report.md**
  - Human-readable
  - Good for docs
  - Markdown format

- **quick_test_report.html**
  - Interactive
  - Beautiful design
  - Open in browser

---

## 🗺️ Navigation Guide

### I want to...

**...get started quickly**
→ Read `GETTING_STARTED.md` → Run `python aiel_t_cli.py --quick-test`

**...understand the framework**
→ Read `README.md` → Read `PROJECT_STRUCTURE.md`

**...integrate into my project**
→ Edit `config.yaml` → Prepare `runtime_data.json` → Run CLI

**...use it in Python code**
→ Import `AIEL_T_Engine.py` → See README "Python API" section

**...run tests**
→ Run `pytest test_aiel_t.py -v`

**...customize validation**
→ Edit invariants YAML → Add custom scenarios → Modify patterns

**...generate reports**
→ Reports auto-generated → Or use `Report_Generator.py` directly

**...understand G-Score**
→ See README "G-Score Formula" section

**...deploy to production**
→ Get G-Score ≥ 0.95 → Check `status` == 'DEPLOYABLE'

---

## 📏 File Size & Complexity

| File | LOC | Complexity | Priority |
|------|-----|------------|----------|
| AIEL_T_Engine.py | ~350 | Medium | ⭐⭐⭐ |
| Invariants_Engine.py | ~220 | Low | ⭐⭐⭐ |
| Scenario_Engine.py | ~200 | Low | ⭐⭐⭐ |
| Pattern_Engine.py | ~200 | Medium | ⭐⭐ |
| Contract_Engine.py | ~270 | Medium | ⭐⭐ |
| Report_Generator.py | ~350 | Low | ⭐⭐ |
| aiel_t_cli.py | ~220 | Low | ⭐⭐⭐ |
| test_aiel_t.py | ~320 | Low | ⭐ |

**Total Lines of Code:** ~1,800 LOC
**Total Files:** 18 files
**Languages:** Python (8 files), Markdown (5 files), YAML (1 file), JSON (1 file)

---

## 🔄 Typical Workflow

```
1. Install
   └─ pip install -r requirements.txt

2. Quick Test (first time)
   └─ python aiel_t_cli.py --quick-test

3. Customize
   ├─ Edit config.yaml
   └─ Prepare runtime_data.json

4. Validate
   └─ python aiel_t_cli.py --config config.yaml --data runtime_data.json

5. Review
   ├─ Check G-Score
   ├─ Read recommendations
   └─ View reports

6. Deploy (if G ≥ 0.95)
   └─ Proceed to production
```

---

## 🎓 Learning Path

**Beginner (30 minutes):**
1. Read README.md (10 min)
2. Read GETTING_STARTED.md (5 min)
3. Run quick test (5 min)
4. View sample reports (10 min)

**Intermediate (1 hour):**
5. Read PROJECT_STRUCTURE.md (15 min)
6. Customize config.yaml (15 min)
7. Prepare your runtime_data.json (20 min)
8. Run full validation (10 min)

**Advanced (2+ hours):**
9. Study engine source code
10. Add custom invariants
11. Add custom scenarios
12. Add custom pattern checks
13. Integrate with CI/CD
14. Write additional tests

---

## 🔍 Quick Reference

### G-Score Formula
```
G = 0.45 × Invariants + 0.15 × Patterns + 0.10 × Contracts + 0.30 × Scenarios
```

### Thresholds
- G ≥ 0.95 → 🟢 DEPLOYABLE
- 0.80 ≤ G < 0.95 → 🟡 REVISION REQUIRED
- G < 0.80 → 🔴 REJECT

### CLI Commands
```bash
# Quick test
python aiel_t_cli.py --quick-test

# Full validation
python aiel_t_cli.py --config config.yaml --data runtime_data.json

# With verbose logging
python aiel_t_cli.py --quick-test --verbose

# Custom output directory
python aiel_t_cli.py --config config.yaml --data runtime_data.json --output ./my_reports
```

### Python API
```python
from AIEL_T_Engine import AIELTEngine

engine = AIELTEngine(config={'invariants_file': 'rules.yaml'})
results = engine.run(runtime_data)
print(f"G-Score: {results['G_score']}")
```

---

## 📞 Support Resources

**Documentation:**
- README.md - Main docs
- GETTING_STARTED.md - Quick start
- PROJECT_STRUCTURE.md - Code structure

**Code:**
- test_aiel_t.py - Test examples
- aiel_t_cli.py - CLI examples
- sample_reports/ - Report examples

**Contact:**
- 📧 Email: support@aiel-factory.com
- 🐛 Issues: GitHub Issues
- 📖 Docs: https://docs.aiel-factory.com

---

## ✅ Checklist for First-Time Users

- [ ] Install dependencies (`pip install -r requirements.txt`)
- [ ] Read README.md
- [ ] Read GETTING_STARTED.md
- [ ] Run quick test (`python aiel_t_cli.py --quick-test`)
- [ ] View sample reports
- [ ] Understand G-Score formula
- [ ] Customize config.yaml
- [ ] Prepare runtime_data.json
- [ ] Run full validation
- [ ] Check if G-Score ≥ 0.95
- [ ] Integrate into your project

---

## 🎯 Summary

**AIEL-T Framework v1.0 contains:**

✅ 8 Python modules (~1,800 LOC)
✅ 4 validation engines (Invariants, Patterns, Contracts, Scenarios)
✅ 1 main orchestrator (AIEL_T_Engine)
✅ 1 CLI tool (easy execution)
✅ 3 report formats (JSON, MD, HTML)
✅ 5 documentation files (comprehensive)
✅ 19 test cases (94.7% pass rate)
✅ Sample config & data files
✅ MIT License (commercial use OK)

**Total Package Size:** ~100KB (code + docs)
**Setup Time:** 5 minutes
**Learning Curve:** Beginner-friendly

---

**Ready to start?** → Open `GETTING_STARTED.md` now! 🚀

---

*AIEL-T Framework v1.0 - Complete Index*
*Generated: 2024-12-10*
