"""
sandbox_runner.constants
Module constants and configuration values

This module centralizes all configuration constants used throughout the
sandbox runner. Constants are defined here to maintain DRY principle
and enable easy configuration updates.

Purpose:
    Centralize configuration constants for maintainability

Design Principles:
    - Single source of truth for configuration
    - Typed constants with explicit annotations
    - Comprehensive documentation
    - Grouped by functionality

Benefits:
    - Easy to find and update configuration
    - Prevents magic numbers in code
    - Self-documenting configuration
    - Type-safe constant definitions
"""

# Timeout configuration
# These constants control execution time limits for various operations

DEFAULT_TIMEOUT_SECONDS: int = 60
"""Default command execution timeout in seconds.

This timeout is applied when run_command() is called without an explicit
timeout parameter. It prevents commands from running indefinitely and
consuming resources.

Usage:
    - Applied to subprocess.run(timeout=...) calls
    - Can be overridden per-call with timeout parameter
    - Set to 60 seconds for balance of usability and safety

Notes:
    - Most commands should complete well under 60 seconds
    - Long-running tests may need custom timeout
    - Timeout prevents resource exhaustion
    - Command is terminated forcefully on timeout

Examples:
    Using default timeout:
        >>> run_command("pytest -q")  # Uses 60s timeout
    
    Override with custom timeout:
        >>> run_command("pytest -q", timeout=120)  # Uses 120s
    
    Timeout too short causes TimeoutError:
        >>> run_command("sleep 100")  # Times out after 60s
"""

PIP_FREEZE_TIMEOUT_SECONDS: int = 10
"""Timeout for pip freeze command in seconds.

This timeout is applied when running 'pip freeze' to enumerate installed
packages. It prevents pip from hanging indefinitely if there are network
issues or environment problems.

Usage:
    - Applied in _fetch_packages_from_pip()
    - Used for toolchain manifest generation
    - Timeout returns empty dict on failure

Notes:
    - 10 seconds is sufficient for most environments
    - Large environments with many packages may take 5-8 seconds
    - Network-based package resolution can slow pip freeze
    - On timeout, returns empty dependencies dict

Performance:
    - Typical: 1-2 seconds for standard environment
    - Large environment: 5-8 seconds (hundreds of packages)
    - Timeout case: Returns immediately with empty dict

Failure Handling:
    - Timeout: Returns {} (empty dependencies)
    - Non-zero exit: Returns {} (empty dependencies)
    - pip not found: Returns {} (empty dependencies)
"""

# Evidence configuration
# These constants define evidence reference properties

EVIDENCE_HASH_ALGORITHM: str = "sha256"
"""Hash algorithm for evidence references.

Defines which hash algorithm is used to compute content-addressed
evidence references. SHA256 provides strong collision resistance
and deterministic output.

Usage:
    - Used in compute_evidence_ref()
    - Applied via hashlib.sha256()
    - Part of determinism guarantee

Properties:
    - Algorithm: SHA-256 (256-bit hash)
    - Output: 64 hexadecimal characters
    - Collision resistance: Extremely high (2^256)
    - Deterministic: Same input → same output

Notes:
    - SHA256 is cryptographically secure
    - Output is deterministic (critical for replay)
    - No known practical collisions
    - Standard choice for content addressing

DO NOT CHANGE without version bump:
    - Evidence refs are part of golden I/O
    - Changing algorithm breaks determinism
    - Would invalidate all existing evidence refs
    - Requires major version increment
"""

EVIDENCE_REF_LENGTH: int = 64
"""Expected length of evidence reference in characters.

SHA256 hash produces 256 bits = 32 bytes = 64 hex characters.
This constant documents the expected length for validation.

Usage:
    - Documentation of expected length
    - Could be used for validation
    - Helps catch implementation errors

Properties:
    - Length: 64 characters
    - Format: Lowercase hexadecimal (0-9a-f)
    - Fixed: Always 64 for SHA256

Examples:
    Valid evidence ref:
        >>> ref = compute_evidence_ref("test", "data")
        >>> assert len(ref) == EVIDENCE_REF_LENGTH
        >>> assert len(ref) == 64
        >>> assert all(c in "0123456789abcdef" for c in ref)
    
    Validation check:
        >>> def validate_ref(ref: str) -> bool:
        ...     return len(ref) == EVIDENCE_REF_LENGTH

Notes:
    - Length is guaranteed by SHA256 algorithm
    - Always 64 for SHA256 hex digest
    - Different hash algorithms would need different length
    - Useful for validation and documentation
"""
