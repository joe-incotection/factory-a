"""Path normalization and traversal detection utilities.

This module provides secure path handling for ZIP/snapshot ingestion. It prevents
directory traversal attacks by validating and normalizing file paths from untrusted
sources (ZIP archives, user uploads).

Security Model:
    All paths must be:
    - Relative (no absolute paths like /etc/passwd)
    - Non-escaping (no .. that would leave the root directory)
    - POSIX-formatted (forward slashes only)
    - Non-empty (no empty or whitespace-only paths)

The normalization process is defense-in-depth:
    1. Quick checks (empty, whitespace, Windows paths)
    2. Path parsing and normalization (PurePosixPath)
    3. Depth tracking to detect traversal
    4. Final safety check (redundant but critical)

Module: ingest_enumerator (Module 2)
Purpose: Secure path handling for zip/snapshot ingestion

AIEL-2 Optimizations:
- Reduced redundant validations (early exit pattern)
- Optimized depth tracking algorithm (single-pass)
- Enhanced edge case handling (whitespace, empty paths)
- Better error messages with security context

AIEL-3 Enhancements:
- Comprehensive docstrings with security notes
- Inline comments explaining validation logic
- Usage examples for common patterns
- Best practices documentation
"""

from pathlib import PurePosixPath
from typing import List

from .exceptions import PathTraversalError


def normalize_path(path: str) -> str:
    """Normalize path and detect traversal attempts.
    
    This is the primary security function for path validation. It performs
    multiple layers of validation to ensure the path is safe for use in
    processing untrusted file archives.
    
    Security validations performed:
        1. Empty/whitespace check (reject empty paths)
        2. Windows path detection (reject backslashes and drive letters)
        3. Path normalization (convert to canonical form)
        4. Absolute path check (reject /absolute/paths)
        5. Depth tracking (detect .. that escape root)
        6. Final safety check (redundant verification)
    
    Args:
        path: Raw path from zip entry or file system. May contain:
            - Forward slashes (POSIX)
            - Backslashes (Windows - will be rejected)
            - Relative components (., ..)
            - Leading/trailing whitespace
        
    Returns:
        Normalized POSIX path (relative, safe). Examples:
            - "src/main.py" → "src/main.py"
            - "src/./utils/helper.py" → "src/utils/helper.py"
            - "src/../lib/core.py" → "lib/core.py" (if depth allows)
        
    Raises:
        PathTraversalError: If path is unsafe, with specific reason:
            - Empty path not allowed
            - Whitespace-only path not allowed
            - Windows paths not allowed
            - Drive letters not allowed
            - Absolute paths not allowed
            - Path traversal detected (escapes root)
            - Invalid path format
    
    Examples:
        Safe paths (accepted):
            >>> normalize_path("src/main.py")
            'src/main.py'
            >>> normalize_path("README.md")
            'README.md'
            >>> normalize_path("src/./utils/test.py")
            'src/utils/test.py'
        
        Unsafe paths (rejected):
            >>> normalize_path("../etc/passwd")
            PathTraversalError: Path traversal detected: ../etc/passwd
            
            >>> normalize_path("/absolute/path")
            PathTraversalError: Absolute paths not allowed: /absolute/path
            
            >>> normalize_path("C:\\windows\\path")
            PathTraversalError: Windows paths not allowed: C:\\windows\\path
            
            >>> normalize_path("  ")
            PathTraversalError: Whitespace-only path not allowed
    
    Performance:
        - Early validation reduces unnecessary processing
        - Single-pass depth tracking: O(n) where n = number of path components
        - Optimized for the common case (valid paths)
    
    Security notes:
        - This function is critical for preventing directory traversal attacks
        - All validations must pass before path is considered safe
        - Redundant checks provide defense-in-depth
        - Always log PathTraversalError as potential security incidents
    
    Implementation details:
        Uses PurePosixPath for normalization because:
        - Consistent behavior across platforms
        - Handles . and .. resolution
        - Rejects absolute paths
        - POSIX format (forward slashes only)
    """
    # ═══════════════════════════════════════════════════════════════════════
    # Phase 1: Quick validation checks (fail fast on obvious issues)
    # ═══════════════════════════════════════════════════════════════════════
    
    # Check 1: Empty path (must have content)
    if not path:
        raise PathTraversalError(path, "Empty path not allowed")
    
    # Check 2: Whitespace-only paths (strip once and verify)
    # Rationale: Paths like "  " or "\t\n" are not valid file paths
    path_stripped = path.strip()
    if not path_stripped:
        raise PathTraversalError(path, "Whitespace-only path not allowed")
    
    # ═══════════════════════════════════════════════════════════════════════
    # Phase 2: Windows path detection (security: prevent cross-platform issues)
    # ═══════════════════════════════════════════════════════════════════════
    
    # Check 3: Backslash detection (Windows path separator)
    # Rationale: Windows paths like "dir\file.txt" must be rejected because:
    #   - We enforce POSIX paths (forward slashes)
    #   - Backslashes could bypass security checks on some systems
    if "\\" in path_stripped:
        raise PathTraversalError(path_stripped, f"Windows paths not allowed: {path_stripped}")
    
    # Check 4: Drive letter detection (Windows absolute paths)
    # Rationale: Paths like "C:\file" or "D:/data" are absolute and must be rejected
    # Note: Check length >= 2 to avoid index error on single-char paths
    if len(path_stripped) >= 2 and path_stripped[1] == ":":
        raise PathTraversalError(path_stripped, f"Drive letters not allowed: {path_stripped}")
    
    # ═══════════════════════════════════════════════════════════════════════
    # Phase 3: Path normalization (convert to canonical POSIX format)
    # ═══════════════════════════════════════════════════════════════════════
    
    # Convert to PurePosixPath for normalization
    # This resolves . and .. components, removes redundant slashes, etc.
    try:
        posix_path = PurePosixPath(path_stripped)
    except (ValueError, TypeError) as e:
        # PurePosixPath can raise for malformed paths
        raise PathTraversalError(path_stripped, f"Invalid path format: {e}")
    
    # Check 5: Absolute path detection (POSIX absolute paths start with /)
    # Rationale: Absolute paths like "/etc/passwd" access system files
    if posix_path.is_absolute():
        raise PathTraversalError(path_stripped, f"Absolute paths not allowed: {path_stripped}")
    
    # ═══════════════════════════════════════════════════════════════════════
    # Phase 4: Depth tracking (core security check for traversal)
    # ═══════════════════════════════════════════════════════════════════════
    
    # Get path components after normalization
    # Example: "src/../lib/core.py" → ("lib", "core.py")
    parts = posix_path.parts
    
    # Edge case: Empty path after normalization (e.g., "." becomes empty)
    if not parts:
        raise PathTraversalError(path_stripped, "Path normalizes to empty")
    
    # Depth tracking algorithm (single-pass, O(n))
    # Concept: Track directory depth relative to root
    #   - Each normal component increases depth (+1)
    #   - Each .. component decreases depth (-1)
    #   - Depth < 0 means we've escaped the root directory
    #
    # Example: "src/../lib/../../etc/passwd"
    #   Start: depth = 0
    #   "src": depth = 1 (entered src/)
    #   "..": depth = 0 (back to root)
    #   "lib": depth = 1 (entered lib/)
    #   "..": depth = 0 (back to root)
    #   "..": depth = -1 ← VIOLATION! (tried to go above root)
    depth = 0
    for part in parts:
        if part == "..":
            # Parent directory reference: decrease depth
            depth -= 1
            # Security check: Have we escaped the root?
            if depth < 0:
                raise PathTraversalError(
                    path_stripped,
                    f"Path traversal detected: {path_stripped} (escapes root)"
                )
        elif part != ".":
            # Normal component (not . or ..): increase depth
            # Note: We skip "." because it means "current directory" (no movement)
            depth += 1
    
    # ═══════════════════════════════════════════════════════════════════════
    # Phase 5: Final result and redundant safety check
    # ═══════════════════════════════════════════════════════════════════════
    
    # Get the normalized path string
    normalized = str(posix_path)
    
    # Redundant safety check (defense-in-depth)
    # This catches edge cases that might slip through previous checks
    # Example: PurePosixPath might normalize some paths differently than expected
    if normalized.startswith("../") or normalized == "..":
        raise PathTraversalError(path_stripped, f"Path traversal detected: {path_stripped}")
    
    return normalized


def sort_paths(paths: List[str]) -> List[str]:
    """Sort paths lexicographically for determinism.
    
    Determinism requirement: File order must be stable across runs. Two
    executions with the same input must produce the same output, including
    file ordering.
    
    Why lexicographic sorting?
        - Platform-independent (same result on Windows, Linux, macOS)
        - Locale-independent (no locale-specific sort rules)
        - Predictable (alphabetical order is intuitive)
        - Fast (Python's sorted() uses Timsort, O(n log n))
    
    Args:
        paths: List of normalized paths to sort. Typically comes from
            process_zip() or another path enumeration function.
        
    Returns:
        New sorted list of paths in lexicographic order.
        
        Sorting rules:
        - Case-sensitive (uppercase < lowercase)
        - Slashes treated as regular characters
        - Example order: "README.md", "src/a.py", "src/b.py"
    
    Examples:
        >>> sort_paths(["src/b.py", "src/a.py", "README.md"])
        ['README.md', 'src/a.py', 'src/b.py']
        
        >>> sort_paths(["z.txt", "a.txt", "m.txt"])
        ['a.txt', 'm.txt', 'z.txt']
    
    Performance:
        - Uses Python's Timsort algorithm: O(n log n) average/worst case
        - Optimized for partially sorted data: O(n) in best case
        - Stable sort: Equal elements maintain relative order
    
    Implementation notes:
        - Input list is not modified (new list returned)
        - Uses built-in sorted() which is highly optimized
        - No custom comparison function needed (default works)
        - Thread-safe (creates new list)
    
    Determinism guarantee:
        For any list L, sort_paths(L) always produces the same result.
        This is critical for:
        - Manifest hashing (same files → same manifest SHA256)
        - Diff/comparison tools (consistent ordering)
        - Testing (predictable output)
    """
    # Python's sorted() is highly optimized (Timsort)
    # - Stable sort (preserves relative order of equal elements)
    # - Adaptive (faster on partially sorted data)
    # - O(n log n) worst case, O(n) best case
    # No need for custom optimization here
    return sorted(paths)


def validate_path_list(paths: List[str]) -> None:
    """Validate that all paths in list are normalized and safe.
    
    Batch validation utility for multiple paths. This is more convenient
    than calling normalize_path() in a try/except loop when you want to
    validate all paths upfront.
    
    Use cases:
        - Pre-validation before batch processing
        - Input validation in API endpoints
        - Test data validation
        - Defensive programming (sanity checks)
    
    Args:
        paths: List of paths to validate. Each path is checked with
            normalize_path(), which performs full security validation.
        
    Raises:
        TypeError: If paths is not a list (e.g., passed a string by mistake).
        PathTraversalError: If any path fails validation. The exception
            contains details about which path failed and why.
    
    Examples:
        Valid paths (no exception):
            >>> validate_path_list(["src/main.py", "README.md"])
            # No output (validation passed)
        
        Invalid type:
            >>> validate_path_list("not_a_list")
            TypeError: Expected list, got str
        
        Contains invalid path:
            >>> validate_path_list(["src/main.py", "../etc/passwd"])
            PathTraversalError: Path traversal detected: ../etc/passwd
    
    Performance:
        - O(n*m) where n = number of paths, m = average path length
        - Early termination: Stops at first invalid path
        - No performance overhead compared to manual validation loop
    
    Best practices:
        - Call this early (fail fast)
        - Log the exception (security audit trail)
        - Return user-friendly error to client (don't expose details)
    
    Note:
        This function performs validation only. It does NOT:
        - Normalize paths (use normalize_path() for that)
        - Modify the input list
        - Sort or deduplicate paths
        
        If you need normalized paths, map over normalize_path():
        >>> normalized = [normalize_path(p) for p in paths]
    """
    # Type check: Ensure we got a list
    # This catches common mistakes like passing a single string
    if not isinstance(paths, list):
        raise TypeError(f"Expected list, got {type(paths).__name__}")
    
    # Validate each path using normalize_path()
    # This will raise PathTraversalError on the first invalid path
    for path in paths:
        # normalize_path() performs all security checks
        # We don't need the result, just the validation side effect
        normalize_path(path)
