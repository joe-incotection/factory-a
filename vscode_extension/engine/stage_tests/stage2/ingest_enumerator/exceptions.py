"""Custom exceptions for ingest_enumerator module.

This module defines the exception hierarchy for the ingest_enumerator package.
All exceptions inherit from IngestError, providing a clear error taxonomy for
different failure scenarios during ZIP/snapshot ingestion.

Typical usage example:

    from ingest_enumerator.exceptions import PathTraversalError
    
    try:
        path = normalize_path("../etc/passwd")
    except PathTraversalError as e:
        print(f"Security violation: {e}")

Module: ingest_enumerator (Module 2)
Purpose: Exception types for zip/snapshot ingestion errors
AIEL-3: Enhanced documentation with usage examples and best practices
"""


class IngestError(Exception):
    """Base exception for all ingest_enumerator errors.
    
    This is the root of the exception hierarchy for this module. All other
    exceptions inherit from this class, allowing clients to catch all
    ingest-related errors with a single except clause if desired.
    
    Best practice: Catch specific exceptions (PathTraversalError, etc.) when
    you want to handle different error types differently. Use IngestError only
    as a fallback for unexpected errors.
    
    Example:
        try:
            manifest = process_zip("submission.zip")
        except PathTraversalError:
            # Handle security violations
            log_security_event()
        except EmptySubmissionError:
            # Handle empty submissions
            return error_response("empty")
        except IngestError as e:
            # Catch-all for other ingest errors
            log_error(e)
    """
    
    pass


class PathTraversalError(IngestError):
    """Raised when a path traversal attempt is detected.
    
    This security exception is raised when a path attempts to escape the
    submission root directory using techniques like:
    - Parent directory references (..)
    - Absolute paths (/etc/passwd)
    - Windows-style paths (C:\\windows\\system32)
    
    Security requirement: All paths must be relative and contained within
    the submission root. This prevents malicious submissions from accessing
    files outside their sandbox.
    
    Attributes:
        path: The offending path that triggered the security violation.
    
    Examples of rejected paths:
        - "../etc/passwd" (escapes root)
        - "../../outside" (escapes multiple levels)
        - "/absolute/path" (absolute path)
        - "C:\\windows\\path" (Windows drive letter)
        - "src/../../escape" (escapes after normalization)
    
    Note:
        This exception is critical for security. Always log these events
        as they may indicate malicious activity.
    """
    
    def __init__(self, path: str, message: str = None):
        """Initialize PathTraversalError with path and optional message.
        
        Args:
            path: The path that triggered the security violation.
            message: Optional custom error message. If not provided, a default
                message is generated from the path.
        
        Example:
            raise PathTraversalError("../etc/passwd", "Attempted directory escape")
        """
        self.path = path
        if message is None:
            message = f"Path traversal detected: {path}"
        super().__init__(message)


class EmptySubmissionError(IngestError):
    """Raised when a submission contains no files.
    
    This exception handles the edge case of empty ZIP files or directories.
    While technically valid ZIP files, empty submissions are rejected because
    they provide no content to validate.
    
    Common causes:
        - ZIP file with only directories (no actual files)
        - Corrupted ZIP that appears empty
        - User error (submitted wrong file)
    
    Recommended handling:
        - Return user-friendly error message
        - Suggest checking the ZIP contents
        - Log for analytics (common user mistake)
    
    Example:
        try:
            manifest = process_zip("empty.zip")
        except EmptySubmissionError:
            return {"error": "Please upload a ZIP file with at least one file"}
    """
    
    def __init__(self, message: str = "Submission contains no files"):
        """Initialize EmptySubmissionError with custom message.
        
        Args:
            message: Error message describing the empty submission.
                Default: "Submission contains no files"
        """
        super().__init__(message)


class InvalidZipError(IngestError):
    """Raised when a ZIP file is corrupted, invalid, or malformed.
    
    This exception is raised for various ZIP-related issues:
        - Corrupted ZIP archive (bad CRC, truncated data)
        - File is not actually a ZIP (wrong format)
        - ZIP too large (exceeds size limits)
        - Missing or unreadable ZIP file
    
    Implementation note:
        This wraps Python's zipfile.BadZipFile and adds context about what
        went wrong. Always include the original error message for debugging.
    
    Common scenarios:
        - User uploaded a non-ZIP file (e.g., RAR, TAR)
        - ZIP corrupted during upload/transfer
        - ZIP exceeds platform size limits
        - Malicious ZIP (zip bomb detection)
    
    Example:
        try:
            with zipfile.ZipFile("file.zip") as zf:
                zf.testzip()
        except zipfile.BadZipFile as e:
            raise InvalidZipError(f"Corrupted ZIP: {e}")
    """
    
    def __init__(self, message: str = "Invalid or corrupted zip file"):
        """Initialize InvalidZipError with descriptive message.
        
        Args:
            message: Detailed error message about what's wrong with the ZIP.
                Should include context (filename, error type) for debugging.
        """
        super().__init__(message)


class ManifestError(IngestError):
    """Raised when manifest generation or processing fails.
    
    This is a general exception for failures during the manifest generation
    process that don't fit into other specific categories. It typically wraps
    unexpected errors with additional context.
    
    Common causes:
        - Unexpected file system errors
        - Internal processing errors
        - Invalid manifest structure
        - Consistency check failures
    
    Best practice:
        When raising this exception, always include:
        - What operation failed
        - Which file/component caused the issue
        - The original error message
    
    Example:
        try:
            normalized = normalize_path(filename)
        except Exception as e:
            raise ManifestError(f"Failed to process '{filename}': {e}")
    
    Note:
        This is a catch-all exception. If you find yourself raising it
        frequently for a specific error type, consider creating a more
        specific exception class.
    """
    
    pass
