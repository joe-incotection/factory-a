# Module 3 — sandbox_runner

**Version:** 1.0.0  
**Purpose:** Run allowlisted commands in deterministic sandbox with content-addressed evidence

## Overview

The `sandbox_runner` module executes commands in a controlled environment and produces deterministic, content-addressed evidence for validation replay.

## Key Features

### 1. Command Allowlist (Security)
- Only pre-approved commands can run
- Default allowlist (v1):
  - `pytest -q`
  - `ruff check .`
- Non-allowlisted commands raise `SYS_SANDBOX_DENIED_COMMAND`

### 2. Content-Addressed Evidence
- Evidence refs are SHA256 hashes
- Same command output → same evidence ref
- Enables deterministic replay

### 3. Toolchain Manifest
- Always included in results
- Captures Python version + dependencies
- Required for reproducibility

## API

### `run_command(command, timeout=None, cwd=None)`

Execute allowlisted command and return result.

**Parameters:**
- `command` (str): Command to execute
- `timeout` (int, optional): Timeout in seconds (default: 60)
- `cwd` (str, optional): Working directory (default: current)

**Returns:**
```python
{
    "evidence": {
        "stdout": str,
        "stderr": str
    },
    "exit_code": int,
    "toolchain_manifest": {
        "python_version": str,
        "dependencies": dict
    },
    "evidence_ref": str  # SHA256 hash
}
```

**Raises:**
- `SchemaViolationError`: Command not in allowlist
- `TimeoutError`: Command execution timeout

### `compute_evidence_ref(stdout, stderr)`

Compute SHA256 reference for evidence.

**Parameters:**
- `stdout` (str): Standard output
- `stderr` (str): Standard error

**Returns:**
- SHA256 hex digest (64 characters)

### `is_command_allowed(command, allowlist=None)`

Check if command is in allowlist.

**Parameters:**
- `command` (str): Command to check
- `allowlist` (Set[str], optional): Custom allowlist

**Returns:**
- `True` if allowed, `False` otherwise

## Examples

### Basic Usage

```python
from sandbox_runner import run_command

# Run allowed command
result = run_command("pytest -q")
print(f"Exit code: {result['exit_code']}")
print(f"Evidence ref: {result['evidence_ref']}")
```

### Denied Command

```python
from sandbox_runner import run_command
from core_contracts.exceptions import SchemaViolationError

try:
    run_command("rm -rf /")
except SchemaViolationError as e:
    print(e.reason_code)  # SYS_SANDBOX_DENIED_COMMAND
```

### Evidence Reference

```python
from sandbox_runner import compute_evidence_ref

ref1 = compute_evidence_ref("hello", "world")
ref2 = compute_evidence_ref("hello", "world")
assert ref1 == ref2  # Deterministic!
```

## Testing

Run golden tests:

```bash
pytest test_golden_module3.py -m golden -v
```

### Golden Tests (7/7 MUST PASS)

1. ✓ Denied command raises SYS_SANDBOX_DENIED_COMMAND
2. ✓ Allowlisted commands accepted
3. ✓ Evidence refs content-addressed (SHA256)
4. ✓ toolchain_manifest always present
5. ✓ Command execution deterministic
6. ✓ Timeout enforced
7. ✓ Exit code captured

## Security Notes

- **Allowlist is enforced** - no command execution without approval
- **No network access by default** - configure sandbox policy carefully
- **Timeout protection** - prevents infinite loops
- **No shell injection** - uses subprocess safely

## Dependencies

- Python 3.11+
- subprocess (stdlib)
- hashlib (stdlib)
- core_contracts (Module 1)

## Determinism Guarantees

1. **Same input → same output**: Re-running identical commands produces identical evidence refs
2. **No timestamps**: Results don't include execution time
3. **No absolute paths**: Paths are normalized
4. **Stable ordering**: All collections are sorted

## Change Control

- Version: 1.0.0
- Status: AIEL-0 (Raw Code)
- Next: AIEL-1 (Structure refinement)

## Related Modules

- Module 1 (core_contracts): Schema validation, reason codes
- Module 4 (engine_aiel_s_py): Static analysis consumer
- Module 5 (engine_aiel_t_py): Runtime test consumer
