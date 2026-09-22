"""Schema validation for data structures.

This module provides schema validation for standardized data structures,
particularly ModuleDescriptor objects. It ensures data conforms to expected
formats and constraints defined in SMART_SPEC.

Note: This is a stub implementation for Module 2. In production, this would
be part of the actual Module 1 (core_contracts) package with comprehensive
schema definitions.

AIEL-3 Enhancements:
- Enhanced docstrings with validation details
- Usage examples for common scenarios
- Error message documentation
"""

import re
from typing import Any, Dict, List


def validate_module_descriptor(descriptor: Dict[str, Any]) -> bool:
    """Validate ModuleDescriptor schema compliance.
    
    This function validates that a ModuleDescriptor dictionary conforms to
    the schema defined in SMART_SPEC section 8. It performs structural and
    content validation to ensure the descriptor is well-formed.
    
    ModuleDescriptor schema:
        {
            "module_id": str,      # Required: Pattern ^mod_[0-9a-f]{12}$
            "root_path": str,      # Required: Non-empty string
            "language": str,       # Required: Must be "python"
            "file_count": int,     # Required: >= 0
            "manifests": list[str] # Optional: List of manifest file paths
        }
    
    Validation checks:
        1. Type check: descriptor must be a dict
        2. Required fields: module_id, root_path, language, file_count
        3. module_id format: Must match pattern ^mod_[0-9a-f]{12}$
        4. root_path: Must be non-empty string
        5. language: Must be "python" (v1 only supports Python)
        6. file_count: Must be non-negative integer
        7. manifests (if present): Must be list of strings
    
    Args:
        descriptor: ModuleDescriptor dictionary to validate.
        
    Returns:
        True if validation passes.
        
    Raises:
        ValueError: If validation fails. Error message describes what's wrong:
            - "must be a dictionary"
            - "missing required field 'X'"
            - "invalid module_id format"
            - "root_path must be non-empty"
            - "language must be 'python'"
            - "file_count must be non-negative integer"
            - "manifests must be a list of strings"
    
    Examples:
        Valid descriptor:
            >>> desc = {
            ...     "module_id": "mod_2c26b46b68ff",
            ...     "root_path": ".",
            ...     "language": "python",
            ...     "file_count": 5,
            ...     "manifests": ["pyproject.toml"]
            ... }
            >>> validate_module_descriptor(desc)
            True
        
        Invalid module_id:
            >>> desc = {"module_id": "invalid", ...}
            >>> validate_module_descriptor(desc)
            ValueError: Invalid module_id format: must match ^mod_[0-9a-f]{12}$
        
        Missing field:
            >>> desc = {"module_id": "mod_2c26b46b68ff"}
            >>> validate_module_descriptor(desc)
            ValueError: Missing required field 'root_path'
    
    Notes:
        - This is a stub implementation for Module 2 testing
        - Production version would use proper schema validation library
        - Validation is strict (fail fast on any violation)
    """
    # Check 1: Must be a dictionary
    if not isinstance(descriptor, dict):
        raise ValueError("ModuleDescriptor must be a dictionary")
    
    # Check 2: Required fields must be present
    required_fields = ["module_id", "root_path", "language", "file_count"]
    for field in required_fields:
        if field not in descriptor:
            raise ValueError(f"Missing required field '{field}'")
    
    # Check 3: module_id format validation
    # Pattern: "mod_" followed by exactly 12 hex characters [0-9a-f]
    module_id = descriptor["module_id"]
    if not isinstance(module_id, str):
        raise ValueError("module_id must be a string")
    
    # Regex pattern: ^mod_[0-9a-f]{12}$
    # ^ = start of string, $ = end of string (exact match)
    module_id_pattern = re.compile(r"^mod_[0-9a-f]{12}$")
    if not module_id_pattern.match(module_id):
        raise ValueError(
            f"Invalid module_id format: must match ^mod_[0-9a-f]{{12}}$, got '{module_id}'"
        )
    
    # Check 4: root_path must be non-empty string
    root_path = descriptor["root_path"]
    if not isinstance(root_path, str):
        raise ValueError("root_path must be a string")
    if not root_path:
        raise ValueError("root_path must be non-empty")
    
    # Check 5: language must be "python" (v1 only supports Python)
    language = descriptor["language"]
    if not isinstance(language, str):
        raise ValueError("language must be a string")
    if language != "python":
        raise ValueError(f"language must be 'python', got '{language}'")
    
    # Check 6: file_count must be non-negative integer
    file_count = descriptor["file_count"]
    if not isinstance(file_count, int):
        raise ValueError("file_count must be an integer")
    if file_count < 0:
        raise ValueError(f"file_count must be non-negative, got {file_count}")
    
    # Check 7: manifests (if present) must be list of strings
    if "manifests" in descriptor:
        manifests = descriptor["manifests"]
        if not isinstance(manifests, list):
            raise ValueError("manifests must be a list")
        # Verify all elements are strings
        for i, item in enumerate(manifests):
            if not isinstance(item, str):
                raise ValueError(
                    f"manifests[{i}] must be a string, got {type(item).__name__}"
                )
    
    # All checks passed
    return True
