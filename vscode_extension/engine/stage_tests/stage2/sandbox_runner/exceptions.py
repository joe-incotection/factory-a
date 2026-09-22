"""
sandbox_runner.exceptions
Custom exceptions for sandbox command execution

This module defines the exception hierarchy for sandbox command execution
errors. All exceptions inherit from SandboxError base class, enabling
comprehensive error handling and specific error identification.

Exception Hierarchy:
    SandboxError (base)
    ├── DeniedCommandError (security)
    └── TimeoutError (execution)

Purpose:
    Provide structured error reporting for sandbox operations

Design Principles:
    - Specific exceptions for different error types
    - Informative error messages with context
    - Reason codes for deterministic error handling
    - Consistent exception hierarchy
"""


class SandboxError(Exception):
    """Base exception for all sandbox-related errors.
    
    This is the root of the sandbox exception hierarchy. Catching this
    exception will catch all sandbox-specific errors, enabling broad
    error handling when specific error types don't need differentiation.
    
    Attributes:
        Inherits from built-in Exception class.
    
    Examples:
        Catch all sandbox errors:
            >>> try:
            ...     run_command("some-command")
            ... except SandboxError as e:
            ...     print(f"Sandbox error: {e}")
        
        Subclass for custom errors:
            >>> class CustomSandboxError(SandboxError):
            ...     pass
    
    Notes:
        - Used as base class for specific exceptions
        - Can be caught directly for generic error handling
        - Subclasses should provide more specific error context
    """
    pass


class DeniedCommandError(SandboxError):
    """Raised when attempting to run non-allowlisted command.
    
    This exception is raised when a command fails allowlist validation.
    It indicates a security policy violation - the command is not approved
    for execution in the sandbox environment.
    
    Attributes:
        command: The command string that was denied.
        
    Error Message Format:
        "SYS_SANDBOX_DENIED_COMMAND: Command not in allowlist: {command}"
    
    Examples:
        Denied command execution:
            >>> try:
            ...     run_command("rm -rf /")
            ... except DeniedCommandError as e:
            ...     print(e.command)
            'rm -rf /'
            ...     print(str(e))
            'SYS_SANDBOX_DENIED_COMMAND: Command not in allowlist: rm -rf /'
    
    Notes:
        - This is a security-critical exception
        - Indicates allowlist validation failure
        - Should not be suppressed in production
        - Contains SYS_SANDBOX_DENIED_COMMAND reason code
        - Used for both direct denial and SchemaViolationError fallback
    
    Security:
        - Prevents execution of unauthorized commands
        - Part of defense-in-depth strategy
        - Should be logged for security monitoring
        - Reason code enables deterministic error handling
    """
    
    def __init__(self, command: str):
        """Initialize DeniedCommandError with command context.
        
        Args:
            command: The command string that was denied execution.
                This is stored for error reporting and logging.
        """
        self.command = command
        # Construct error message with reason code
        # Reason code "SYS_SANDBOX_DENIED_COMMAND" is part of golden I/O contract
        super().__init__(
            f"SYS_SANDBOX_DENIED_COMMAND: Command not in allowlist: {command}"
        )


class TimeoutError(SandboxError):
    """Raised when command execution exceeds timeout limit.
    
    This exception is raised when a command takes longer than the allowed
    timeout period. It indicates the command was terminated forcefully to
    prevent indefinite hanging or resource exhaustion.
    
    Attributes:
        command: The command string that timed out.
        timeout: The timeout value in seconds that was exceeded.
    
    Error Message Format:
        "Command timed out after {timeout} seconds: {command}"
    
    Examples:
        Command timeout:
            >>> try:
            ...     run_command("sleep 100", timeout=1)
            ... except TimeoutError as e:
            ...     print(e.command)
            'sleep 100'
            ...     print(e.timeout)
            1
            ...     print(str(e))
            'Command timed out after 1 seconds: sleep 100'
    
    Notes:
        - Indicates command exceeded allowed execution time
        - Command process is terminated when timeout occurs
        - Timeout is enforced by subprocess.run(timeout=...)
        - Default timeout is 60 seconds (DEFAULT_TIMEOUT_SECONDS)
        - Can be prevented by setting higher timeout value
    
    Common Causes:
        - Command genuinely takes longer than timeout
        - Command is stuck waiting for input
        - Infinite loop in command code
        - Resource contention slowing execution
        - Timeout set too low for command complexity
    
    Remediation:
        - Increase timeout parameter if command is legitimately slow
        - Investigate why command is taking longer than expected
        - Check for deadlocks or infinite loops
        - Consider async execution for very long commands
    """
    
    def __init__(self, command: str, timeout: int):
        """Initialize TimeoutError with command and timeout context.
        
        Args:
            command: The command string that timed out during execution.
            timeout: The timeout value in seconds that was exceeded.
                This is the limit that was configured, not the actual
                execution time (which was >= timeout).
        """
        self.command = command
        self.timeout = timeout
        # Construct error message with both command and timeout
        super().__init__(
            f"Command timed out after {timeout} seconds: {command}"
        )
