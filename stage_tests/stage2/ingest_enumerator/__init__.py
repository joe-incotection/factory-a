"""ingest_enumerator: ZIP/Snapshot → Deterministic Manifest + Module Descriptors.

This package (Module 2 of the KAMI validation system) transforms untrusted ZIP
uploads into deterministic, validated manifests and module descriptors for
downstream validation.

Core functionality:
    - ZIP processing with integrity validation
    - Path normalization and traversal protection  
    - SHA256-based file hashing (deterministic)
    - Lexicographic file sorting (stable ordering)
    - Module ID generation (SHA256-based)
    - Schema-compliant descriptor creation

Security features:
    - Path traversal prevention (blocks ../etc/passwd attacks)
    - ZIP size limits (1GB max, prevents DoS)
    - Integrity checks (detects corruption)
    - Type validation (all inputs checked)

Determinism guarantees:
    - Same ZIP → byte-identical manifest (always)
    - Same root path → same module ID (always)
    - Platform-independent (same on Windows/Linux/macOS)
    - Locale-independent (no locale-specific sorting)

Public API:
    Main functions:
        process_zip() - Process ZIP and generate manifest
        generate_module_descriptors() - Create module descriptors
    
    Utilities:
        normalize_path() - Validate and normalize paths
        compute_module_id() - Generate deterministic module IDs
        compute_manifest_digest() - Hash manifest for tracking
        compute_file_sha256() - Compute file SHA256
        sort_paths() - Sort paths lexicographically
        detect_multi_modules() - Detect multiple modules (v1: placeholder)
    
    Exceptions:
        IngestError - Base exception
        PathTraversalError - Security violation (path traversal)
        EmptySubmissionError - No files in submission
        InvalidZipError - Corrupted or invalid ZIP
        ManifestError - Manifest generation failure

Compliance:
    - SMART_SPEC section 8 (Module 2 requirements)
    - KAMI v2.0.1 coding standards
    - Golden I/O Lock (determinism verification)
    - ModuleDescriptor schema validation

Version history:
    1.0.0 (AIEL-0): Initial implementation
    1.0.1 (AIEL-1): Structural refinement
    1.0.2 (AIEL-2): Performance optimization
    1.0.3 (AIEL-3): Documentation polish

Usage example:
    >>> from ingest_enumerator import process_zip, generate_module_descriptors
    >>> 
    >>> # Process ZIP file
    >>> manifest = process_zip("submission.zip")
    >>> print(f"Files: {manifest['file_count']}")
    >>> 
    >>> # Generate module descriptors
    >>> descriptors = generate_module_descriptors("submission.zip")
    >>> print(f"Module ID: {descriptors[0]['module_id']}")
"""

# Import functions from submodules
from .manifest import (
    compute_file_sha256,
    compute_manifest_digest,
    process_zip,
)
from .module_detection import (
    compute_module_id,
    detect_multi_modules,
    generate_module_descriptors,
)
from .path_utils import (
    normalize_path,
    sort_paths,
)

# Import exceptions for easy access
from .exceptions import (
    EmptySubmissionError,
    IngestError,
    InvalidZipError,
    ManifestError,
    PathTraversalError,
)

# Public API: Define what's exported with "from ingest_enumerator import *"
__all__ = [
    # Main functions (most commonly used)
    "process_zip",
    "generate_module_descriptors",
    
    # Utility functions
    "normalize_path",
    "compute_module_id",
    "compute_manifest_digest",
    "compute_file_sha256",
    "sort_paths",
    "detect_multi_modules",
    
    # Exception classes (for error handling)
    "IngestError",
    "PathTraversalError",
    "EmptySubmissionError",
    "InvalidZipError",
    "ManifestError",
]

# Package metadata
__version__ = "1.0.3"  # AIEL-3: Documentation polish
__module__ = "ingest_enumerator"
__author__ = "KAMI Validation System"
__description__ = "ZIP/Snapshot → Deterministic Manifest + Module Descriptors"
