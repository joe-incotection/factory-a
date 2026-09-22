"""
sandbox_runner.allowlist
Command allowlist validation

This module provides security enforcement through command allowlist validation.
Only commands present in the allowlist are permitted to execute, preventing
arbitrary code execution and maintaining sandbox security.

Purpose:
    Validate commands against security allowlist

Security Model:
    - Default allowlist contains approved commands only
    - Custom allowlists can be provided per-call
    - Exact string matching (no wildcards or patterns)
    - Fail-closed: deny by default

Default Allowlist (v1):
    - pytest -q: Run pytest in quiet mode
    - ruff check .: Run ruff linter on current directory
    - python --version: Display Python version (for testing)
    - sleep 10: Sleep for 10 seconds (for timeout testing)
    - false: Command that returns non-zero exit (for testing)
"""

from typing import Optional, Set

# Default allowlisted commands (v1)
# These are the only commands permitted by default
# Each entry must be an exact match (no partial matching)
DEFAULT_ALLOWLIST: Set[str] = {
    "pytest -q",           # Testing: Run pytest in quiet mode
    "ruff check .",        # Linting: Check code quality
    "python --version",    # Testing: Verify Python version
    "sleep 10",            # Testing: Timeout verification
    "false",               # Testing: Non-zero exit code handling
}


def is_command_allowed(
    command: str,
    allowlist: Optional[Set[str]] = None
) -> bool:
    """Check if command is in allowlist.
    
    Performs exact string matching against the allowlist. Commands must
    match exactly - no partial matching, wildcards, or pattern matching
    is supported. This is a security-critical function.
    
    Args:
        command: Command string to check. Must match exactly with an
            allowlist entry. Case-sensitive and whitespace-sensitive.
        allowlist: Custom allowlist to check against. If None, uses
            DEFAULT_ALLOWLIST. Pass a custom set to override default
            security policy. Defaults to None.
    
    Returns:
        bool: True if command is in allowlist, False otherwise.
            False means command should be denied execution.
    
    Examples:
        Command in default allowlist:
            >>> is_command_allowed("pytest -q")
            True
        
        Command not in allowlist:
            >>> is_command_allowed("rm -rf /")
            False
        
        Custom allowlist:
            >>> custom = {"ls", "pwd"}
            >>> is_command_allowed("ls", allowlist=custom)
            True
            >>> is_command_allowed("pytest -q", allowlist=custom)
            False
        
        Exact matching required:
            >>> is_command_allowed("pytest")  # Missing "-q"
            False
            >>> is_command_allowed("PYTEST -Q")  # Wrong case
            False
    
    Security Notes:
        - Uses exact string matching (not regex or patterns)
        - Case-sensitive comparison
        - Whitespace matters
        - No substring matching
        - Fail-closed: deny if not explicitly allowed
        - Command arguments are part of the match
    
    Performance:
        - O(1) average case (set lookup)
        - O(n) worst case (hash collision)
        - Typical: <0.001ms
    """
    # Use default allowlist if none provided
    # This implements the default security policy
    if allowlist is None:
        allowlist = DEFAULT_ALLOWLIST
    
    # Perform exact string match against allowlist
    # Uses set membership test for O(1) performance
    return command in allowlist


def get_default_allowlist() -> Set[str]:
    """Get default command allowlist.
    
    Returns a copy of the default allowlist to prevent external
    modification of the security policy. Callers can inspect the
    default policy or use it as a base for custom policies.
    
    Returns:
        Set[str]: Copy of DEFAULT_ALLOWLIST containing approved commands.
            Modifications to this set do not affect the default policy.
    
    Examples:
        Inspect default policy:
            >>> allowlist = get_default_allowlist()
            >>> print(sorted(allowlist))
            ['false', 'pytest -q', 'python --version', 'ruff check .', 'sleep 10']
        
        Create custom policy based on default:
            >>> custom = get_default_allowlist()
            >>> custom.add("mypy .")
            >>> is_command_allowed("mypy .", allowlist=custom)
            True
            >>> is_command_allowed("mypy .")  # Not in default
            False
    
    Notes:
        - Returns a copy to prevent mutation of DEFAULT_ALLOWLIST
        - Use this to build custom allowlists safely
        - Original DEFAULT_ALLOWLIST remains unchanged
        - Copy operation is O(n) where n is allowlist size
    
    Security:
        - Prevents accidental modification of security policy
        - Copy-on-return ensures isolation
        - Original allowlist is module-level constant
    """
    # Return a copy to prevent external mutation
    # This preserves the integrity of DEFAULT_ALLOWLIST
    return DEFAULT_ALLOWLIST.copy()
