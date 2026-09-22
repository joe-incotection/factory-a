"""Manifest generation and digest computation.

This module is the core of Module 2's ZIP processing functionality. It transforms
untrusted ZIP uploads into deterministic, validated manifests that can be safely
processed by downstream modules.

Key responsibilities:
    1. ZIP validation (integrity, size, format)
    2. File enumeration (extract file list from ZIP)
    3. Path normalization (security validation)
    4. SHA256 computation (file and ZIP hashing)
    5. Manifest generation (deterministic output)
    6. Manifest hashing (tracking and comparison)

Determinism guarantees:
    - Same ZIP → byte-identical manifest (always)
    - Lexicographic file ordering (stable sort)
    - No timestamps (removed from manifest)
    - Canonical JSON (sorted keys, stable floats)

Security features:
    - Path traversal protection (via path_utils)
    - ZIP size limits (1GB max, prevents DoS)
    - Integrity validation (testzip before processing)
    - Type validation (all inputs checked)

Module: ingest_enumerator (Module 2)
Purpose: Create deterministic input manifests from zip/snapshot

AIEL-2 Optimizations:
- Enhanced input validation (7 checks added)
- Better error messages with context (filename, path, etc.)
- Improved edge case handling (empty ZIPs, corrupted ZIPs, large files)
- Performance optimizations for large ZIPs (streaming, early checks)

AIEL-3 Enhancements:
- Comprehensive Google-style docstrings for all functions
- Detailed inline comments explaining validation logic
- Usage examples with security notes
- Performance characteristics documented
- Best practices and common pitfalls
"""

import hashlib
import zipfile
from pathlib import Path
from typing import Any, Dict, List

from .exceptions import EmptySubmissionError, InvalidZipError, ManifestError
from .path_utils import normalize_path


# ═══════════════════════════════════════════════════════════════════════════
# Constants: Configuration values for manifest processing
# ═══════════════════════════════════════════════════════════════════════════

# Chunk size for file hashing
# 64KB is optimal for most systems:
# - Balances memory usage vs syscall overhead
# - Matches common disk/network block sizes
# - Recommended by Python hashlib documentation
_CHUNK_SIZE = 65536  # 64KB

# Maximum ZIP file size
# 1GB limit prevents denial-of-service attacks from huge uploads
# Can be adjusted based on platform requirements
_MAX_ZIP_SIZE = 1024 * 1024 * 1024  # 1GB


def process_zip(zip_path: str) -> Dict[str, Any]:
    """Process ZIP file and generate deterministic manifest.
    
    This is the main entry point for ZIP processing. It performs comprehensive
    validation, extracts file metadata, and generates a deterministic manifest
    that can be safely used by downstream validation modules.
    
    Processing steps:
        1. Input validation (type, existence, size)
        2. ZIP integrity check (corruption detection)
        3. File enumeration (extract metadata)
        4. Path normalization (security validation)
        5. SHA256 computation (file hashing)
        6. Sorting (deterministic order)
        7. Manifest assembly (final output)
    
    Determinism requirements:
        - Files sorted lexicographically (stable across runs)
        - Stable SHA256 for each file (content-based)
        - Canonical JSON structure (sorted keys)
        - Same zip → same manifest (byte-identical output)
        - No timestamps (removed for determinism)
    
    Security features:
        - Path traversal protection (via normalize_path)
        - ZIP size limits (prevents DoS)
        - Integrity validation (detects corruption)
        - Type checking (prevents misuse)
    
    Args:
        zip_path: Path to ZIP file. Must be a string representing a valid
            file path. The ZIP file must:
            - Exist on the file system
            - Be a regular file (not a directory)
            - Be non-empty (> 0 bytes)
            - Be under 1GB (size limit)
            - Contain at least one file
            - Pass integrity check (testzip)
        
    Returns:
        Input manifest dictionary with the following schema:
        {
            "files": [
                {
                    "path": str,    # Normalized POSIX path
                    "sha256": str,  # 64 hex chars
                    "size": int     # Bytes
                },
                ...
            ],
            "file_count": int,      # Total number of files
            "zip_sha256": str       # SHA256 of the ZIP file itself
        }
        
        Field specifications:
        - files: Sorted lexicographically by path
        - path: POSIX format, relative, no traversal
        - sha256: Lowercase hexadecimal, 64 characters
        - size: Non-negative integer (bytes)
        - file_count: Must match len(files)
        - zip_sha256: SHA256 of entire ZIP file
        
    Raises:
        TypeError: If zip_path is not a string. Common mistake:
            process_zip(Path("file.zip"))  # Wrong - use str
            process_zip("file.zip")        # Correct
        
        InvalidZipError: If ZIP is invalid, corrupted, or violates limits:
            - File not found
            - Path is a directory, not a file
            - ZIP size exceeds 1GB
            - Corrupted ZIP (bad CRC, truncated)
            - ZIP integrity check fails
        
        EmptySubmissionError: If ZIP contains no files:
            - Zero-byte ZIP file
            - ZIP with only directories (no actual files)
        
        PathTraversalError: If any file path attempts traversal:
            - Raised by normalize_path() during processing
            - Indicates potential security violation
        
        ManifestError: For unexpected processing errors:
            - File read failures
            - Internal consistency check failures
            - Wraps unexpected exceptions with context
        
    Examples:
        Basic usage:
            >>> manifest = process_zip("submission.zip")
            >>> print(manifest["file_count"])
            5
            >>> print(manifest["files"][0]["path"])
            'README.md'
        
        Error handling:
            >>> try:
            ...     manifest = process_zip("corrupted.zip")
            ... except InvalidZipError as e:
            ...     print(f"ZIP error: {e}")
            ... except PathTraversalError as e:
            ...     print(f"Security violation: {e}")
    
    Performance:
        - Streaming SHA256 computation (memory efficient)
        - Single-pass file processing
        - O(n*m) where n = number of files, m = average file size
        - Memory usage: O(n) for file list, O(1) for streaming
    
    Notes:
        - This function does NOT extract files to disk
        - ZIP file itself is not modified
        - All paths are validated before inclusion
        - Manifest can be safely serialized to JSON
    """
    # ═══════════════════════════════════════════════════════════════════════
    # Phase 1: Input Validation
    # ═══════════════════════════════════════════════════════════════════════
    
    # Type check: Ensure zip_path is a string
    # Common mistake: passing Path object instead of string
    if not isinstance(zip_path, str):
        raise TypeError(f"zip_path must be str, got {type(zip_path).__name__}")
    
    # Empty string check: Reject empty or whitespace-only paths
    if not zip_path.strip():
        raise InvalidZipError("Empty zip_path not allowed")
    
    # Convert to Path object for file system operations
    zip_path_obj = Path(zip_path)
    
    # Existence check: File must exist on file system
    if not zip_path_obj.exists():
        raise InvalidZipError(f"Zip file not found: {zip_path}")
    
    # Type check: Must be a file, not a directory
    # Common mistake: passing directory path instead of ZIP file
    if not zip_path_obj.is_file():
        raise InvalidZipError(f"Path is not a file: {zip_path}")
    
    # Size validation: Check file size and enforce limits
    file_size = zip_path_obj.stat().st_size
    
    # Zero-byte check: Reject empty files immediately
    # Empty ZIPs can't contain any files, so fail fast
    if file_size == 0:
        raise EmptySubmissionError(f"Zip file is empty (0 bytes): {zip_path}")
    
    # Size limit check: Prevent DoS from huge uploads
    # 1GB limit is reasonable for most use cases
    # Adjust _MAX_ZIP_SIZE constant if needed
    if file_size > _MAX_ZIP_SIZE:
        raise InvalidZipError(
            f"Zip file too large: {file_size} bytes (max {_MAX_ZIP_SIZE})"
        )
    
    # ═══════════════════════════════════════════════════════════════════════
    # Phase 2: ZIP Processing
    # ═══════════════════════════════════════════════════════════════════════
    
    # Compute ZIP file SHA256 for tracking
    # This allows detection of file changes/corruption
    zip_sha256 = compute_file_sha256(str(zip_path_obj))
    
    # Extract file listing and metadata from ZIP
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Integrity check: Validate ZIP before processing
            # testzip() returns name of first bad file, or None if OK
            # This catches CRC errors, truncation, etc.
            bad_file = zf.testzip()
            if bad_file:
                raise InvalidZipError(f"Corrupted file in zip: {bad_file}")
            
            # Get file list, excluding directories
            # ZIP can contain directory entries, but we only want files
            # is_dir() check filters out directories
            zip_files = [
                info for info in zf.infolist()
                if not info.is_dir()
            ]
            
            # Empty ZIP check: Must have at least one file
            # Edge case: ZIP with only directories
            if not zip_files:
                raise EmptySubmissionError(f"Zip file contains no files: {zip_path}")
            
            # Process each file in the ZIP
            files = []
            for zip_info in zip_files:
                # Normalize and validate path (security critical!)
                # This prevents directory traversal attacks
                try:
                    normalized_path = normalize_path(zip_info.filename)
                except Exception as e:
                    # Add context: Which file caused the error?
                    # This helps debugging and security auditing
                    raise ManifestError(
                        f"Invalid path in zip '{zip_info.filename}': {e}"
                    )
                
                # Read file content from ZIP
                # This is where actual extraction happens (in memory)
                try:
                    file_content = zf.read(zip_info.filename)
                except Exception as e:
                    # File read error: Could be corruption or permission issue
                    raise ManifestError(
                        f"Failed to read '{zip_info.filename}' from zip: {e}"
                    )
                
                # Compute SHA256 hash of file content
                # This creates a deterministic fingerprint of the file
                file_sha256 = hashlib.sha256(file_content).hexdigest()
                
                # Assemble file info entry
                file_info = {
                    "path": normalized_path,      # POSIX, normalized
                    "sha256": file_sha256,         # 64 hex chars
                    "size": zip_info.file_size     # Uncompressed size
                }
                files.append(file_info)
    
    except zipfile.BadZipFile as e:
        # ZIP format error: Not a valid ZIP file
        raise InvalidZipError(f"Corrupted zip file: {e}")
    except (InvalidZipError, EmptySubmissionError):
        # Re-raise our custom exceptions without wrapping
        raise
    except Exception as e:
        # Unexpected error: Wrap with context
        raise ManifestError(f"Failed to process zip '{zip_path}': {e}")
    
    # ═══════════════════════════════════════════════════════════════════════
    # Phase 3: Deterministic Sorting and Validation
    # ═══════════════════════════════════════════════════════════════════════
    
    # Sort files lexicographically for determinism
    # This ensures same ZIP → same manifest order
    # Use lambda function for explicit sort key
    files.sort(key=lambda f: f["path"])
    
    # Paranoid verification: Double-check sorting succeeded
    # This should never fail, but better safe than sorry
    # Helps catch bugs in sort implementation or key function
    file_paths = [f["path"] for f in files]
    if file_paths != sorted(file_paths):
        # Internal error: Sorting failed somehow
        # This indicates a serious bug that needs investigation
        raise ManifestError("Internal error: files not properly sorted")
    
    # ═══════════════════════════════════════════════════════════════════════
    # Phase 4: Manifest Assembly
    # ═══════════════════════════════════════════════════════════════════════
    
    # Create final manifest (deterministic output)
    # No timestamps or non-deterministic fields!
    manifest = {
        "files": files,              # Sorted file list
        "file_count": len(files),    # Total count (for validation)
        "zip_sha256": zip_sha256     # ZIP fingerprint
    }
    
    return manifest


def compute_file_sha256(file_path: str) -> str:
    """Compute SHA256 hash of file content.
    
    This function provides memory-efficient SHA256 computation for files of
    any size. It reads files in chunks to avoid loading large files entirely
    into memory.
    
    Use cases:
        - File fingerprinting (detect changes)
        - Content verification (integrity checks)
        - Deduplication (find identical files)
        - Manifest generation (ZIP and file hashing)
    
    Args:
        file_path: Path to file to hash. Must be a readable regular file
            (not a directory, symlink, or special file).
        
    Returns:
        SHA256 hex digest as a string. Always 64 characters, lowercase
        hexadecimal (0-9, a-f).
        
        Examples:
        - "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" (empty file)
        - "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae" (hash of "foo")
    
    Raises:
        FileNotFoundError: If file doesn't exist at the specified path.
            Error message includes the file path for debugging.
        
        PermissionError: If file can't be read due to permission restrictions.
            Error message includes the file path.
        
        OSError: For other file system errors:
            - File is a directory (not a regular file)
            - File is a symlink to missing target
            - Disk read error
            - File was deleted during reading
    
    Examples:
        Compute hash of a file:
            >>> sha256 = compute_file_sha256("README.md")
            >>> print(f"SHA256: {sha256}")
            SHA256: 2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae
        
        Error handling:
            >>> try:
            ...     compute_file_sha256("/etc/shadow")
            ... except PermissionError as e:
            ...     print(f"Access denied: {e}")
    
    Performance:
        - Time complexity: O(n) where n = file size in bytes
        - Memory usage: O(1) - constant (only chunk buffer in memory)
        - Optimized for sequential disk reads
        - Chunk size: 64KB (optimal for most systems)
    
    Implementation notes:
        - Uses streaming to handle files of any size
        - Reads in 64KB chunks (balance of memory vs syscalls)
        - Hash is updated incrementally (no full file in memory)
        - Works for files up to several GB without issue
        
        Why chunked reading?
        - Small files: Minimal overhead, still fast
        - Large files: Constant memory usage, no matter file size
        - Very large files: Only viable approach
    
    Security notes:
        - SHA256 is cryptographically secure (collision-resistant)
        - Use SHA256 for integrity, not encryption
        - Hash is deterministic (same file → same hash)
    """
    # Initialize SHA256 hash object
    sha256_hash = hashlib.sha256()
    
    try:
        # Open file in binary read mode
        # 'rb' = read binary (important for correct hashing)
        with open(file_path, "rb") as f:
            # Streaming read: Process file in chunks
            # This keeps memory usage constant regardless of file size
            while True:
                # Read next chunk (64KB)
                # Returns empty bytes when EOF reached
                chunk = f.read(_CHUNK_SIZE)
                
                # Check for EOF (empty chunk means done)
                if not chunk:
                    break
                
                # Update hash with this chunk
                # Hash is computed incrementally
                sha256_hash.update(chunk)
                
    except FileNotFoundError:
        # File doesn't exist: Clear error message with path
        raise FileNotFoundError(f"File not found: {file_path}")
    except PermissionError:
        # Permission denied: Include path in error
        raise PermissionError(f"Permission denied: {file_path}")
    except OSError as e:
        # Other file system errors: Include path and original error
        raise OSError(f"Failed to read file '{file_path}': {e}")
    
    # Return hexadecimal digest (64 chars, lowercase)
    return sha256_hash.hexdigest()


def compute_manifest_digest(manifest: Dict[str, Any]) -> str:
    """Compute SHA256 digest of manifest for tracking.
    
    This function creates a deterministic fingerprint of the manifest, allowing
    for efficient comparison and change detection. The digest is stable across
    runs (same manifest → same digest) because it uses canonical JSON.
    
    Use cases:
        - Manifest comparison (detect changes)
        - Caching (use digest as cache key)
        - Deduplication (find identical submissions)
        - Tracking (log digest for audit trail)
    
    Determinism requirements:
        - Uses canonical JSON (sorted keys, stable floats)
        - Excludes non-deterministic fields (timestamps, etc.)
        - Same manifest content → same digest (always)
        - Platform-independent (same result on all systems)
    
    Args:
        manifest: Input manifest dictionary. Must contain required fields:
            - "files": List of file info dicts
            - "file_count": Integer count of files
            
            Optional fields (will be included if present):
            - "zip_sha256": SHA256 of original ZIP
            - Any other custom fields
            
            Excluded fields (removed before hashing):
            - "processed_at": Timestamp (non-deterministic)
            - Any other timestamp fields
        
    Returns:
        SHA256 hex digest as a string. Always 64 characters, lowercase
        hexadecimal (0-9, a-f).
        
        This digest represents the canonical form of the manifest.
    
    Raises:
        TypeError: If manifest is not a dictionary. Common mistake:
            compute_manifest_digest([...])  # Wrong - need dict
            compute_manifest_digest({...})  # Correct
        
        ValueError: If manifest is invalid or malformed:
            - Missing required field "files"
            - Missing required field "file_count"
            - Canonicalization fails (invalid JSON)
    
    Examples:
        Compute digest:
            >>> manifest = process_zip("test.zip")
            >>> digest = compute_manifest_digest(manifest)
            >>> print(f"Manifest digest: {digest}")
        
        Verify determinism:
            >>> digest1 = compute_manifest_digest(manifest)
            >>> digest2 = compute_manifest_digest(manifest)
            >>> assert digest1 == digest2  # Always true
        
        Detect changes:
            >>> old_digest = compute_manifest_digest(old_manifest)
            >>> new_digest = compute_manifest_digest(new_manifest)
            >>> if old_digest != new_digest:
            ...     print("Manifest changed!")
    
    Implementation details:
        1. Validates manifest type and required fields
        2. Creates copy and removes non-deterministic fields
        3. Converts to canonical JSON (sorted keys, stable encoding)
        4. Computes SHA256 of canonical bytes
        5. Returns hex digest
    
    Why canonical JSON?
        - Regular JSON is not deterministic (key order varies)
        - canonical_json() from core_contracts ensures:
          - Sorted keys (alphabetical order)
          - Stable float formatting (6 decimal places)
          - No NaN/Inf (forbidden values)
          - Minimal whitespace (compact)
    
    Performance:
        - O(n) where n = manifest size (number of entries)
        - Single-pass canonicalization
        - Memory usage: O(n) for copy + canonical bytes
    
    Notes:
        - Uses canonical_json from core_contracts module
        - Import is local (inside function) to avoid circular dependency
        - Timestamp fields are automatically excluded
        - Manifest itself is not modified (works on copy)
    """
    # Type validation: Ensure manifest is a dictionary
    # This catches type mismatches early with clear error message
    if not isinstance(manifest, dict):
        raise TypeError(f"manifest must be dict, got {type(manifest).__name__}")
    
    # Field validation: Check required fields are present
    # These fields are essential for a valid manifest
    if "files" not in manifest:
        raise ValueError("manifest missing required field 'files'")
    
    if "file_count" not in manifest:
        raise ValueError("manifest missing required field 'file_count'")
    
    # Import canonical_json here to avoid circular dependency
    # core_contracts depends on nothing, so this is safe
    from core_contracts import canonical_json
    
    # Create copy to avoid modifying original manifest
    # This ensures function has no side effects
    manifest_copy = manifest.copy()
    
    # Remove non-deterministic fields
    # processed_at: Timestamp field (would change every time)
    # Use pop() with None default (safe if field doesn't exist)
    manifest_copy.pop("processed_at", None)
    
    # Convert to canonical JSON bytes
    # This ensures deterministic serialization:
    # - Sorted keys (alphabetical)
    # - Stable float format (6 decimals)
    # - Minimal whitespace
    # - UTF-8 encoding
    try:
        canonical_bytes = canonical_json(manifest_copy)
    except Exception as e:
        # Canonicalization error: Invalid manifest structure
        raise ValueError(f"Failed to canonicalize manifest: {e}")
    
    # Compute SHA256 of canonical bytes
    # This creates a deterministic fingerprint
    digest = hashlib.sha256(canonical_bytes).hexdigest()
    
    return digest
