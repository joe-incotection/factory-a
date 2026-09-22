# Stage2 Validator Package

**Version:** 1.0.0  
**Status:** Production Ready (AIEL-3 Certified)

## Modules

- **M1** (core_contracts): Schema validation + canonicalization
- **M2** (ingest_enumerator): ZIP processing + manifest generation
- **M3** (sandbox_runner): Secure command execution
- **M4** (engine_aiel_s_py): Static code analysis
- **M5** (engine_aiel_t_py): Runtime test execution
- **M6** (aggregate_and_report): Score aggregation + final verdict

## Test Results

```
Golden Tests: 42/42 PASSED (7 per module)
Integration: 18/18 PASSED
Quality: ⭐⭐⭐⭐⭐
```

## Usage

```python
from stage2 import (
    process_zip,
    analyze_code,
    run_tests,
    aggregate_and_report
)

# Process submission
manifest = process_zip("submission.zip")

# Static analysis
static_findings = analyze_code(code, "file.py")

# Runtime testing
runtime_result = run_tests("tests/")

# Final verdict
result = aggregate_and_report(...)
```

## Installation

```bash
# Extract to your project
unzip stage2.zip -d your_project/

# Import
from stage2 import *
```

## Requirements

- Python 3.11+
- pytest (for M5)
- No external dependencies for M1-M4, M6
