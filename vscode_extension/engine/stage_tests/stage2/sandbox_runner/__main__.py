"""
sandbox_runner CLI
Quick test interface for Module 3

This module provides a command-line interface for testing and using
the sandbox runner. It supports running commands, checking allowlist
membership, and listing approved commands.

Purpose:
    Provide CLI access to sandbox runner functionality

Features:
    - Run allowlisted commands directly
    - Check if commands are allowed
    - List all allowlisted commands
    - JSON output for programmatic use

Usage Examples:
    Run a command:
        $ python -m sandbox_runner "pytest -q"
        {
          "evidence": {"stdout": "...", "stderr": "..."},
          "exit_code": 0,
          ...
        }
    
    Check if command is allowed:
        $ python -m sandbox_runner --check "pytest -q"
        ✓ Command is allowed: pytest -q
    
    List allowlisted commands:
        $ python -m sandbox_runner --list
        Allowlisted commands:
          - false
          - pytest -q
          - python --version
          - ruff check .
          - sleep 10

Exit Codes:
    - 0: Success (command allowed or execution successful)
    - 1: Failure (command denied or execution failed)
    - Matches command exit code when running commands

Notes:
    - Output is JSON for programmatic parsing
    - Exit code mirrors command exit code
    - Errors go to stderr, results to stdout
    - Suitable for scripting and automation
"""

import json
import sys
from typing import NoReturn

from . import (
    is_command_allowed,
    run_command,
)
from .allowlist import get_default_allowlist


def main() -> NoReturn:
    """Main CLI entry point.
    
    Parses command-line arguments and dispatches to appropriate handler.
    Always exits with sys.exit() - never returns normally.
    
    Args:
        None. Uses sys.argv for argument parsing.
    
    Returns:
        NoReturn: Always exits via sys.exit(), never returns.
    
    Exit Codes:
        - 0: Success
        - 1: Error or command denied
        - Command exit code when running commands
    
    Notes:
        - Minimal argument parsing (no argparse dependency)
        - JSON output for programmatic use
        - Errors printed to stderr
        - Results printed to stdout
    """
    # Check if any arguments provided
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)
    
    # Get first argument (command or flag)
    arg = sys.argv[1]
    
    # Handle --list flag: display all allowlisted commands
    if arg == "--list":
        print("Allowlisted commands:")
        # Sort for consistent output
        for cmd in sorted(get_default_allowlist()):
            print(f"  - {cmd}")
        sys.exit(0)
    
    # Handle --check flag: verify command allowlist status
    if arg == "--check":
        # Require command argument after --check
        if len(sys.argv) < 3:
            print("Error: --check requires command argument")
            sys.exit(1)
        
        # Extract command to check
        command = sys.argv[2]
        allowed = is_command_allowed(command)
        
        # Print result with visual indicator
        if allowed:
            print(f"✓ Command is allowed: {command}")
            sys.exit(0)
        else:
            print(f"✗ Command is NOT allowed: {command}")
            sys.exit(1)
    
    # Default action: run the command
    command = arg
    
    try:
        # Execute command via sandbox runner
        result = run_command(command)
        
        # Print result as formatted JSON
        # indent=2 for human-readable output
        print(json.dumps(result, indent=2))
        
        # Exit with command's exit code
        # This enables shell scripting: python -m sandbox_runner "..." && next_command
        sys.exit(result["exit_code"])
    
    except Exception as e:
        # Catch all exceptions and print to stderr
        # This includes DeniedCommandError, TimeoutError, etc.
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def print_usage() -> None:
    """Print usage information to stdout.
    
    Displays help text showing available commands and usage examples.
    Called when no arguments are provided or --help is requested.
    
    Args:
        None
    
    Returns:
        None. Prints to stdout.
    
    Output Format:
        - Module name and purpose
        - Usage patterns
        - Example commands
        - All output goes to stdout
    """
    print("""
sandbox_runner - Module 3 CLI

Usage:
    python -m sandbox_runner <command>           Run allowlisted command
    python -m sandbox_runner --check <command>   Check if command is allowed
    python -m sandbox_runner --list              List allowlisted commands

Examples:
    python -m sandbox_runner "pytest -q"
    python -m sandbox_runner --check "ruff check ."
    python -m sandbox_runner --list
""")


# Standard Python idiom: only run if executed as script
# Not executed when imported as module
if __name__ == "__main__":
    main()
