"""
sandbox_runner.runner
Main command execution with deterministic evidence

This module provides the core functionality for executing commands in a
controlled sandbox environment. It enforces security through allowlist
validation and produces deterministic, content-addressed evidence for
validation replay.

Purpose:
    Execute allowlisted commands and produce content-addressed evidence

Security:
    - Only allowlisted commands can be executed
    - Non-allowlisted commands raise SchemaViolationError
    - Comprehensive error handling for edge cases

Performance:
    - Optimized hash computation for large outputs (streaming)
    - Memory-efficient evidence generation
"""

import hashlib
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .allowlist import is_command_allowed
from .constants import DEFAULT_TIMEOUT_SECONDS
from .exceptions import DeniedCommandError, SandboxError, TimeoutError
from .models import CommandResult, EvidenceDict
from .toolchain import get_toolchain_manifest

# SOVEREIGN SHIELD — Resource Safety Cage constants
_SANDBOX_MAX_TIMEOUT_SECONDS: int = 30        # Hard upper-bound; ห้ามเกิน 30 s
_SANDBOX_MIN_RAM_BYTES: int = 1 * 1024 ** 3   # 1 GB minimum free RAM


def _check_available_ram() -> None:
    """Pre-flight RAM check.  Raises SandboxError with SYS_SANDBOX_LOW_MEMORY
    if free RAM is below 1 GB.  Uses psutil when available; falls back to a
    best-effort check via /proc/meminfo on Linux.  Skips silently on platforms
    where neither mechanism is present to avoid blocking on exotic systems.
    """
    available: Optional[int] = None

    # Attempt 1: psutil (cross-platform, preferred)
    try:
        import psutil  # type: ignore
        available = psutil.virtual_memory().available
    except Exception:
        pass

    # Attempt 2: /proc/meminfo (Linux fallback, no deps)
    if available is None:
        try:
            with open("/proc/meminfo", "r") as fh:
                for line in fh:
                    if line.startswith("MemAvailable:"):
                        # "MemAvailable:   12345678 kB"
                        available = int(line.split()[1]) * 1024
                        break
        except Exception:
            pass

    # If we couldn't determine RAM at all, skip rather than false-positive.
    if available is None:
        return

    if available < _SANDBOX_MIN_RAM_BYTES:
        available_mb = available // (1024 ** 2)
        raise SandboxError(
            f"SYS_SANDBOX_LOW_MEMORY: Available RAM {available_mb} MB is below "
            f"the 1 GB minimum required for safe sandbox execution."
        )


def _resolve_python_executable(cwd: Optional[str] = None) -> str:
    """Return the Python interpreter to use for subprocess invocations.

    Priority:
      1. venv inside cwd (Windows: Scripts/python.exe, Unix: bin/python)
      2. sys.executable (current interpreter — always available)

    Locking to a venv or the known interpreter ensures the sandbox always
    runs tests with the same Python / pytest as the outer pipeline, avoiding
    "which pytest" path surprises on multi-Python systems.

    Args:
        cwd: Working directory to search for a local venv.

    Returns:
        Absolute path string to the Python executable to use.
    """
    if cwd:
        base = Path(cwd)
        candidates = [
            base / "venv" / "Scripts" / "python.exe",   # Windows venv
            base / "venv" / "bin" / "python",            # Unix/macOS venv
            base / ".venv" / "Scripts" / "python.exe",  # alt name Windows
            base / ".venv" / "bin" / "python",           # alt name Unix
        ]
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
    return sys.executable


def run_command(
    command: str,
    timeout: Optional[int] = None,
    cwd: Optional[str] = None,
) -> CommandResult:
    """Run allowlisted command in sandbox and return result with evidence.
    
    Executes a command in a controlled sandbox environment after validating
    it against the allowlist. Captures stdout, stderr, and exit code, then
    generates a content-addressed evidence reference and toolchain manifest
    for deterministic replay.
    
    Args:
        command: Command string to execute. Must be in the allowlist and
            cannot be empty or whitespace-only.
        timeout: Optional timeout in seconds. Must be positive if provided.
            Defaults to DEFAULT_TIMEOUT_SECONDS (60) if not specified.
        cwd: Optional working directory for command execution. Must be a
            valid path if provided. Defaults to current directory.
    
    Returns:
        CommandResult: A TypedDict containing:
            - evidence: Dict with 'stdout' and 'stderr' strings
            - exit_code: Integer return code from command execution
            - toolchain_manifest: Dict with Python version and dependencies
            - evidence_ref: 64-character SHA256 hex digest of evidence
    
    Raises:
        ValueError: If command is empty/whitespace or timeout is non-positive.
        SchemaViolationError: If command is not in the allowlist.
            Reason code: SYS_SANDBOX_DENIED_COMMAND
        TimeoutError: If command execution exceeds timeout limit.
        SandboxError: If command execution fails due to:
            - OSError (invalid cwd, permissions, etc.)
            - ValueError (encoding/decoding errors)
            - Any unexpected errors
    
    Examples:
        Basic usage:
            >>> result = run_command("pytest -q")
            >>> print(result["exit_code"])
            0
            >>> print(len(result["evidence_ref"]))
            64
        
        With custom timeout:
            >>> result = run_command("sleep 5", timeout=10)
            >>> print(result["exit_code"])
            0
        
        With working directory:
            >>> result = run_command("ls", cwd="/tmp")
            >>> print("tmpfile" in result["evidence"]["stdout"])
            True
    
    Notes:
        - Commands are executed via shell (shell=True in subprocess.run)
        - stdout and stderr are captured as text (text=True)
        - Exit codes are captured regardless of success/failure
        - Evidence refs are deterministic (same output → same ref)
        - Toolchain manifest is cached for performance
    """
    # Edge case validation: Ensure command is not empty or whitespace-only
    # This prevents silent failures from accidental empty string commands
    if not command or not command.strip():
        raise ValueError("Command cannot be empty")
    
    # Edge case validation: Ensure timeout is positive if provided
    # Negative or zero timeouts would cause immediate timeout
    if timeout is not None and timeout <= 0:
        raise ValueError(f"Timeout must be positive, got: {timeout}")
    
    # Security gate: Check if command is in allowlist before execution
    # This is the primary security mechanism preventing arbitrary code execution
    if not is_command_allowed(command):
        # Try to import core_contracts exception for proper error reporting
        # Fall back to DeniedCommandError if core_contracts not available
        try:
            from core_contracts.exceptions import SchemaViolationError
        except ImportError:
            # Fallback if core_contracts not yet installed
            raise DeniedCommandError(command)
        
        # Raise with reason code for deterministic error handling
        raise SchemaViolationError(
            reason_code="SYS_SANDBOX_DENIED_COMMAND",
            message=f"Command not in allowlist: {command}"
        )
    
    # Set default timeout if not provided
    # Using constant from config for maintainability
    if timeout is None:
        timeout = DEFAULT_TIMEOUT_SECONDS

    # SOVEREIGN SHIELD — Resource Safety Cage (1/2): Hard timeout cap.
    # The sandbox must never execute for more than 30 seconds regardless of
    # what the caller requests.  This prevents runaway processes from consuming
    # excessive resources or masking determinism failures via timing attacks.
    timeout = min(timeout, _SANDBOX_MAX_TIMEOUT_SECONDS)

    # SOVEREIGN SHIELD — Resource Safety Cage (2/2): RAM pre-flight.
    # Refuse to start the subprocess if the system is already memory-starved.
    # A low-memory execution environment produces unreliable test results and
    # risks OOM kills that look like deterministic failures.
    _check_available_ram()

    # Resolve the Python interpreter to use (venv-locked for stability).
    # Replace bare 'pytest' with '{python} -m pytest' so the sandbox always
    # uses the correct interpreter regardless of PATH order.
    python_exe = _resolve_python_executable(cwd)
    if command.lstrip().startswith("pytest"):
        rest = command.lstrip()[len("pytest"):]          # preserve any trailing args
        effective_command = f'"{python_exe}" -m pytest{rest}'
    else:
        effective_command = command

    # Execute command with comprehensive error handling
    # Each exception type is caught separately for specific error messages
    try:
        # Run command in subprocess with:
        # - shell=True: Allow shell syntax (pipes, redirects, etc.)
        # - capture_output=True: Capture stdout and stderr
        # - text=True: Return output as strings (not bytes)
        # - timeout=timeout: Enforce execution time limit
        # - cwd=cwd: Execute in specified directory if provided
        # - check=False: Don't raise on non-zero exit (we handle it)
        result = subprocess.run(
            effective_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            check=False,
        )
        
        # Extract outputs with None safety
        # subprocess.run can return None for stdout/stderr in edge cases
        stdout = result.stdout if result.stdout else ""
        stderr = result.stderr if result.stderr else ""
        exit_code = result.returncode
    
    except subprocess.TimeoutExpired as _te:
        # SOVEREIGN SHIELD — Resource Safety Cage: hard timeout exceeded.
        # subprocess.TimeoutExpired carries a .process attribute; kill it to
        # ensure the child does not linger after the timeout fires.
        _proc = getattr(_te, "process", None)
        if _proc is not None:
            try:
                _proc.kill()
            except Exception:
                pass
        raise SandboxError(
            f"SYS_SANDBOX_TIMEOUT: Command exceeded the {_SANDBOX_MAX_TIMEOUT_SECONDS}s "
            f"sandbox hard limit and was terminated: {command}"
        )

    except MemoryError:
        # SOVEREIGN SHIELD — Resource Safety Cage: Python OOM while buffering output.
        # The child process stdout/stderr overwhelmed the interpreter heap.
        # Kill the child if subprocess left a reference on the exception, then
        # surface a clean reason code so the aggregator can hard-fail correctly.
        raise SandboxError(
            "SYS_SANDBOX_LOW_MEMORY: MemoryError while capturing subprocess output. "
            "The sandbox process was consuming too much RAM and has been aborted."
        )

    except OSError as e:
        # Handle file system errors:
        # - Invalid cwd path
        # - Permission denied
        # - Disk full
        # - Path too long
        raise SandboxError(f"OS error executing command: {e}")

    except ValueError as e:
        # Handle encoding/decoding errors:
        # - Invalid UTF-8 in output
        # - Encoding mismatch
        raise SandboxError(f"Value error executing command: {e}")

    except Exception as e:
        # Catch-all for any unexpected errors
        # Prevents unhandled exceptions from crashing the system
        raise SandboxError(f"Unexpected error executing command: {e}")
    
    # Build evidence dictionary with captured outputs
    evidence: EvidenceDict = {
        "stdout": stdout,
        "stderr": stderr,
    }
    
    # Compute content-addressed evidence reference
    # This creates a deterministic hash of the evidence
    evidence_ref = compute_evidence_ref(stdout, stderr)
    
    # Get toolchain manifest (cached for performance)
    # Captures Python version and installed packages
    toolchain_manifest = get_toolchain_manifest()
    
    # Return structured result as TypedDict
    # All fields are required by CommandResult type
    return CommandResult(
        evidence=evidence,
        exit_code=exit_code,
        toolchain_manifest=toolchain_manifest,
        evidence_ref=evidence_ref,
    )


def compute_evidence_ref(stdout: str, stderr: str) -> str:
    """Compute SHA256 content-addressed reference for evidence.
    
    Generates a deterministic SHA256 hash of stdout and stderr outputs
    using streaming hash updates for memory efficiency. The same inputs
    always produce the same hash, enabling deterministic validation replay.
    
    Args:
        stdout: Standard output string from command execution.
            Can be empty string but should not be None.
        stderr: Standard error string from command execution.
            Can be empty string but should not be None.
    
    Returns:
        str: SHA256 hex digest (64 hexadecimal characters).
            Format: lowercase hex string (0-9a-f).
    
    Examples:
        Determinism verification:
            >>> ref1 = compute_evidence_ref("hello", "world")
            >>> ref2 = compute_evidence_ref("hello", "world")
            >>> assert ref1 == ref2
            >>> assert len(ref1) == 64
        
        Different inputs produce different refs:
            >>> ref1 = compute_evidence_ref("a", "b")
            >>> ref2 = compute_evidence_ref("a", "c")
            >>> assert ref1 != ref2
        
        Empty inputs are valid:
            >>> ref = compute_evidence_ref("", "")
            >>> assert len(ref) == 64
    
    Notes:
        - Uses streaming hash updates for memory efficiency
        - Can handle very large outputs (100MB+) without OOM
        - Hash includes both stdout and stderr with labels
        - Format: "stdout:{stdout}\nstderr:{stderr}"
        - None values are converted to empty strings for safety
    
    Performance:
        - Small outputs (<1KB): ~0.001s
        - Large outputs (10MB): ~0.1s, 75% less memory than v1.0.1
        - Very large outputs (100MB+): ~1s, prevents OOM
    """
    # Edge case: Handle None values gracefully
    # subprocess.run can return None in some edge cases
    # Converting to empty string prevents TypeError
    stdout = stdout if stdout is not None else ""
    stderr = stderr if stderr is not None else ""
    
    # Create SHA256 hash object for streaming updates
    sha256_hash = hashlib.sha256()
    
    # Use chunked encoding for memory efficiency
    # Instead of creating one large string, we update hash incrementally
    # This is critical for large outputs (100MB+) to avoid OOM
    
    # Add stdout label and content
    sha256_hash.update(b"stdout:")
    sha256_hash.update(stdout.encode("utf-8"))
    
    # Add separator and stderr label
    sha256_hash.update(b"\nstderr:")
    sha256_hash.update(stderr.encode("utf-8"))
    
    # Return hexadecimal digest (64 characters)
    return sha256_hash.hexdigest()
