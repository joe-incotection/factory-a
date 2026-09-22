"""
sandbox_runner.models
Type definitions for Module 3

This module provides strict type definitions using TypedDict for all
structured data in the sandbox runner. These types enable static type
checking, IDE autocomplete, and runtime validation.

Purpose:
    Provide strict type definitions for better type safety

Type Hierarchy:
    CommandResult (top-level result)
    ├── EvidenceDict (stdout/stderr)
    └── ToolchainManifest (environment info)

Benefits:
    - Static type checking with mypy
    - IDE autocomplete and error detection
    - Self-documenting code structure
    - Runtime type validation (when needed)
    - Prevention of structure mismatch errors
"""

from typing import Dict, TypedDict


class EvidenceDict(TypedDict):
    """Evidence dictionary structure containing command outputs.
    
    This type defines the structure for evidence captured during command
    execution. Evidence consists of stdout and stderr streams, which are
    used to compute the content-addressed evidence reference.
    
    Attributes:
        stdout: Standard output stream from command execution.
            Empty string if command produced no output.
            Never None (converted to "" if needed).
        stderr: Standard error stream from command execution.
            Empty string if command produced no error output.
            Never None (converted to "" if needed).
    
    Examples:
        Creating evidence:
            >>> evidence: EvidenceDict = {
            ...     "stdout": "test output",
            ...     "stderr": ""
            ... }
        
        Type checking catches errors:
            >>> evidence: EvidenceDict = {
            ...     "output": "wrong key"  # Type error!
            ... }
        
        Using in function:
            >>> def process_evidence(ev: EvidenceDict) -> None:
            ...     print(ev["stdout"])  # IDE autocomplete works!
    
    Notes:
        - Both fields are required (not Optional)
        - Both fields are strings (not bytes)
        - Empty output is "" not None
        - Used in compute_evidence_ref() for hashing
        - Part of CommandResult structure
    
    Validation:
        - TypedDict provides structure validation
        - Missing keys cause type errors
        - Wrong types cause type errors
        - Extra keys are allowed (TypedDict default)
    """
    stdout: str
    stderr: str


class ToolchainManifest(TypedDict):
    """Toolchain manifest structure for environment information.
    
    This type defines the structure for toolchain information captured
    during command execution. The manifest enables deterministic replay
    by recording the exact environment configuration.
    
    Attributes:
        python_version: Python version string in format "major.minor.micro".
            Example: "3.11.5" or "3.12.3"
            Captured from sys.version_info.
        dependencies: Dictionary mapping package names to versions.
            Example: {"pytest": "8.0.0", "ruff": "0.1.0"}
            Captured from pip freeze output.
            Empty dict {} if pip not available.
    
    Examples:
        Creating manifest:
            >>> manifest: ToolchainManifest = {
            ...     "python_version": "3.12.3",
            ...     "dependencies": {"pytest": "8.0.0"}
            ... }
        
        Accessing fields:
            >>> def check_python(m: ToolchainManifest) -> bool:
            ...     version = m["python_version"]
            ...     major = int(version.split(".")[0])
            ...     return major >= 3
        
        Type safety:
            >>> manifest: ToolchainManifest = {
            ...     "python_version": 3.12  # Type error! Must be string
            ... }
    
    Notes:
        - Both fields are required
        - python_version is always populated
        - dependencies can be empty dict
        - Captured by get_toolchain_manifest()
        - Used for validation replay verification
        - Cached for performance (see toolchain.py)
    
    Determinism:
        - Same environment → same manifest
        - Enables deterministic replay
        - Critical for validation verification
        - Used in golden test verification
    """
    python_version: str
    dependencies: Dict[str, str]


class CommandResult(TypedDict):
    """Command execution result structure.
    
    This is the top-level type returned by run_command(). It contains
    all information about command execution: evidence, exit code,
    toolchain manifest, and evidence reference.
    
    Attributes:
        evidence: EvidenceDict containing stdout and stderr.
            Never None, fields may be empty strings.
        exit_code: Integer exit code from command execution.
            0 typically means success.
            Non-zero typically means error.
            Can be negative for signal termination.
        toolchain_manifest: ToolchainManifest with environment info.
            Contains Python version and dependencies.
            Used for deterministic replay.
        evidence_ref: Content-addressed reference (SHA256 hex digest).
            64-character lowercase hex string.
            Computed from stdout and stderr.
            Deterministic: same evidence → same ref.
    
    Examples:
        Function return type:
            >>> def run_command(...) -> CommandResult:
            ...     return CommandResult(
            ...         evidence={"stdout": "...", "stderr": "..."},
            ...         exit_code=0,
            ...         toolchain_manifest={...},
            ...         evidence_ref="abc123..."
            ...     )
        
        Using the result:
            >>> result: CommandResult = run_command("pytest -q")
            >>> print(result["exit_code"])
            0
            >>> print(len(result["evidence_ref"]))
            64
            >>> print(result["evidence"]["stdout"])
            'test output...'
        
        Type checking:
            >>> result: CommandResult = run_command("...")
            >>> result["wrong_key"]  # Type error!
            >>> result["exit_code"] = "0"  # Type error! Must be int
    
    Notes:
        - All four fields are required
        - This is the primary output contract
        - Structure is part of golden I/O
        - Fields cannot be None (use empty values)
        - Evidence ref is always 64 characters
        - Exit code can be any integer
    
    Golden I/O Contract:
        - Structure must remain stable (no breaking changes)
        - Field names are part of public API
        - Field types are guaranteed
        - Used in golden test verification
        - Changes require new major version
    """
    evidence: EvidenceDict
    exit_code: int
    toolchain_manifest: ToolchainManifest
    evidence_ref: str
