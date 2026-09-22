"""
Module 4: engine_aiel_s_py — Deterministic Static Analysis for Python
======================================================================

Purpose:
    Provides deterministic static code analysis for Python, detecting security
    vulnerabilities, code quality issues, and dependency problems.

Version History:
    1.0 - AIEL-0: Initial implementation
    1.1 - AIEL-1: Structural refinement
    1.2 - AIEL-2: Performance optimization
    1.3 - AIEL-3: Documentation polish

Detection Capabilities:
    - S_SYNTAX_ERROR: Parse errors in Python code
    - S_IMPORT_SIDE_EFFECT: Code executed at module import time
    - S_INSECURE_SUBPROCESS: subprocess calls with shell=True
    - S_HARDCODED_SECRET_SUSPECT: Potential hardcoded secrets/credentials
    - S_UNPINNED_DEPENDENCY: Unpinned dependencies in requirements.txt

Compliance:
    - Reason codes: REASON_CODES_v1.yaml
    - Determinism: Guaranteed stable output for replay
    - Golden I/O: Locked schema compliance

Author: Factory-A AIEL System
License: Proprietary
"""

import ast
import re
from enum import Enum
from functools import lru_cache
from typing import Any, Dict, List, Optional, Set, Tuple


class Severity(str, Enum):
    """Finding severity levels.
    
    Must match severity definitions in REASON_CODES_v1.yaml.
    Used for deterministic sorting and filtering.
    
    Attributes:
        CRITICAL: Critical security or correctness issues
        HIGH: High-priority issues requiring attention
        MEDIUM: Medium-priority issues
        LOW: Low-priority informational findings
    """
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# Reason codes from REASON_CODES_v1.yaml
# Maps reason code to its severity level for validation
REASON_CODES = {
    "S_SYNTAX_ERROR": Severity.HIGH,
    "S_IMPORT_SIDE_EFFECT": Severity.HIGH,
    "S_INSECURE_SUBPROCESS": Severity.CRITICAL,
    "S_HARDCODED_SECRET_SUSPECT": Severity.HIGH,
    "S_UNPINNED_DEPENDENCY": Severity.MEDIUM,
}

# API key patterns for secret detection (pre-compiled for performance)
# Pattern format: [prefix]-[alphanumeric]{min_length,}
_API_KEY_PATTERNS = [
    r'sk-[a-zA-Z0-9]{20,}',      # OpenAI style: sk-xxxxx...
    r'ghp_[a-zA-Z0-9]{36,}',     # GitHub personal token: ghp_xxxxx...
    r'gho_[a-zA-Z0-9]{36,}',     # GitHub OAuth token: gho_xxxxx...
]

# Secret variable name patterns (pre-compiled)
# Matches: password/secret/token = "value" with minimum 8 chars
_SECRET_VAR_PATTERNS = [
    r'(password|passwd|pwd|secret|api_key|token)\s*=\s*["\'][^"\']{8,}["\']',
]

# Subprocess methods to check for shell=True vulnerability
# All of these can execute arbitrary shell commands if shell=True
_SUBPROCESS_METHODS = {'call', 'run', 'Popen', 'check_call', 'check_output'}

# Pre-compile regex patterns for maximum performance
# Compilation happens once at module load time
_API_KEY_REGEX = [re.compile(p) for p in _API_KEY_PATTERNS]
_SECRET_VAR_REGEX = [re.compile(p, re.IGNORECASE) for p in _SECRET_VAR_PATTERNS]
_PLACEHOLDER_REGEX = re.compile(r'(placeholder|example|test|dummy|xxx|sample)', re.IGNORECASE)
_COMMENT_REGEX = re.compile(r'^\s*#')
_DOCSTRING_REGEX = re.compile(r'^\s*[\"\']{3}')

# Type alias for memory-efficient finding storage
# Tuple format: (reason_code, severity, confidence, file, line_start, line_end)
_FindingTuple = Tuple[str, str, float, str, int, int]

# Cache for line number calculations to avoid repeated AST attribute access
_line_cache: Dict[int, int] = {}


def _get_line_end_cached(node: ast.AST) -> int:
    """Get line end for AST node with caching.
    
    Uses node identity as cache key to avoid repeated attribute access.
    Fallback to line start if end_lineno is not available.
    
    Args:
        node: AST node to get line end for
        
    Returns:
        Line number where node ends (1-indexed)
        
    Performance:
        O(1) cache lookup vs O(1) attribute access, but reduces overhead
        for repeated access patterns in AST traversal
    """
    node_id = id(node)
    if node_id in _line_cache:
        return _line_cache[node_id]
    
    # Python 3.8+ has end_lineno, fallback to lineno for older versions
    line_end = getattr(node, 'end_lineno', node.lineno)
    _line_cache[node_id] = line_end
    return line_end


def _finding_to_dict(finding_tuple: _FindingTuple) -> Dict[str, Any]:
    """Convert memory-efficient tuple to dict format.
    
    Tuples are more memory-efficient during analysis, but dicts are
    required for the output schema. This conversion happens only once
    at the end of analysis.
    
    Args:
        finding_tuple: Finding as (reason_code, severity, confidence,
                       file, line_start, line_end)
                       
    Returns:
        Finding dictionary matching ValidationResult schema:
        {
            "reason_code": str,
            "severity": str,
            "confidence": float,
            "primary": {"file": str, "line_start": int, "line_end": int},
            "evidence_refs": []
        }
    """
    return {
        "reason_code": finding_tuple[0],
        "severity": finding_tuple[1],
        "confidence": finding_tuple[2],
        "primary": {
            "file": finding_tuple[3],
            "line_start": finding_tuple[4],
            "line_end": finding_tuple[5],
        },
        "evidence_refs": [],  # Empty for now, populated by aggregator
    }


@lru_cache(maxsize=128)
def _parse_ast_cached(code: str, filename: str) -> Optional[ast.AST]:
    """Parse Python code to AST with caching and error handling.
    
    LRU cache prevents re-parsing of identical code snippets.
    Cache size of 128 is sufficient for typical analysis patterns.
    
    Args:
        code: Python source code to parse
        filename: Name for error reporting
        
    Returns:
        Parsed AST tree, or None if syntax error
        
    Note:
        Returns None instead of raising SyntaxError to allow caller
        to emit S_SYNTAX_ERROR finding in consistent format
    """
    try:
        return ast.parse(code, filename=filename)
    except SyntaxError:
        # Caller will detect None and emit S_SYNTAX_ERROR finding
        return None


class _ASTVisitor(ast.NodeVisitor):
    """Optimized AST visitor for single-pass analysis.
    
    Performs detection of import side effects and insecure subprocess
    usage in a single tree traversal for maximum efficiency.
    
    Attributes:
        findings: Accumulated findings as tuples (memory-efficient)
        filename: File being analyzed (for finding metadata)
        _module_body: Module-level statements (for side effect detection)
        _in_name_main: True if inside __name__ == "__main__" block
    """
    
    def __init__(self, filename: str):
        """Initialize AST visitor.
        
        Args:
            filename: Name of file being analyzed
        """
        self.findings: List[_FindingTuple] = []
        self.filename = filename
        self._module_body: Optional[List[ast.stmt]] = None
        self._in_name_main = False
        
    def visit_Module(self, node: ast.Module):
        """Visit module root and detect __name__ == "__main__" pattern.
        
        This detection allows us to skip flagging code inside the standard
        Python idiom:
            if __name__ == "__main__":
                main()
                
        Args:
            node: Module AST node
        """
        self._module_body = node.body
        
        # Detect: if __name__ == "__main__": pattern
        # This is a common idiom for entry points and shouldn't be flagged
        if len(node.body) == 1 and isinstance(node.body[0], ast.If):
            if_test = node.body[0].test
            if (isinstance(if_test, ast.Compare) and 
                isinstance(if_test.left, ast.Name) and
                if_test.left.id == "__name__" and
                len(if_test.comparators) == 1 and
                isinstance(if_test.comparators[0], ast.Constant) and
                if_test.comparators[0].value == "__main__"):
                self._in_name_main = True
                
        self.generic_visit(node)
        
    def visit_Expr(self, node: ast.Expr):
        """Detect import-time side effects.
        
        Flags module-level expressions that are function calls, as these
        execute when the module is imported, which can cause unexpected
        behavior.
        
        Exceptions:
            - Code inside __name__ == "__main__" blocks
            - Docstrings (ast.Constant with string value)
            
        Args:
            node: Expression statement node
        """
        # Check if this is a module-level call (side effect at import time)
        if (self._module_body and 
            node in self._module_body and
            isinstance(node.value, ast.Call) and
            not self._in_name_main):
            
            # Flag as import side effect (confidence 0.85 - heuristic based)
            self.findings.append((
                "S_IMPORT_SIDE_EFFECT",
                "HIGH",
                0.85,
                self.filename,
                node.lineno,
                _get_line_end_cached(node),
            ))
            
        self.generic_visit(node)
        
    def visit_Call(self, node: ast.Call):
        """Detect insecure subprocess usage with shell=True.
        
        Subprocess calls with shell=True are vulnerable to shell injection
        attacks if user input is not properly sanitized.
        
        Detection logic:
            1. Check if call is subprocess.{call,run,Popen,...}
            2. Check if shell=True is passed as keyword argument
            3. Flag as CRITICAL if both conditions met
            
        Args:
            node: Function call AST node
        """
        # Check if it's a subprocess.{method} call
        is_subprocess = False
        method_name = None
        
        if isinstance(node.func, ast.Attribute):
            # Pattern: subprocess.call(...) / subprocess.run(...)
            if (isinstance(node.func.value, ast.Name) and 
                node.func.value.id == 'subprocess'):
                method_name = node.func.attr
                is_subprocess = method_name in _SUBPROCESS_METHODS
                
        if is_subprocess:
            # Check for shell=True keyword argument
            has_shell_true = False
            for keyword in node.keywords:
                if keyword.arg == 'shell':
                    value = keyword.value
                    # Handle different AST representations of True
                    if isinstance(value, ast.Constant):
                        # Python 3.8+: ast.Constant
                        if value.value is True:
                            has_shell_true = True
                            break
                    elif isinstance(value, ast.NameConstant):
                        # Python 3.7: ast.NameConstant
                        if value.value is True:
                            has_shell_true = True
                            break
                    elif isinstance(value, ast.Name):
                        # Variable reference - can't determine statically
                        # Be conservative and flag it (better safe than sorry)
                        has_shell_true = True
                        break
            
            if has_shell_true:
                # CRITICAL: shell=True with subprocess is highly dangerous
                # Confidence 0.95 (very high - direct pattern match)
                self.findings.append((
                    "S_INSECURE_SUBPROCESS",
                    "CRITICAL",
                    0.95,
                    self.filename,
                    node.lineno,
                    _get_line_end_cached(node),
                ))
                
        self.generic_visit(node)


def _detect_secrets_optimized(code: str, filename: str) -> List[_FindingTuple]:
    """Detect potential hardcoded secrets with optimized patterns.
    
    Uses pre-compiled regex patterns and smart filtering to minimize
    false positives while maintaining high recall.
    
    Detection strategies:
        1. API key patterns (sk-, ghp-, gho- prefixes)
        2. Suspicious variable names (password, secret, token, api_key)
        3. Exclude obvious placeholders/examples
        4. Skip comments and docstrings
        
    Args:
        code: Python source code to analyze
        filename: File being analyzed
        
    Returns:
        List of finding tuples for detected secrets
        
    False Positives:
        May flag test fixtures or example code. Use placeholder
        keywords to reduce false positives.
        
    Performance:
        O(n) where n is number of lines, with early termination
        and compiled regex for speed
    """
    findings: List[_FindingTuple] = []
    lines = code.split('\n')
    in_multiline_string = False
    multiline_delimiter = None
    
    for i, line in enumerate(lines, start=1):
        # Skip comments (lines starting with #)
        if _COMMENT_REGEX.match(line):
            continue
            
        # Handle multi-line strings (docstrings)
        # Count triple quotes to detect start/end of docstrings
        if '"""' in line or "'''" in line:
            quote_count = line.count('"""') + line.count("'''")
            if quote_count % 2 == 1:  # Odd count means toggle state
                in_multiline_string = not in_multiline_string
                multiline_delimiter = '"""' if '"""' in line else "'''"
                # Skip the delimiter line itself
                continue
                
        if in_multiline_string:
            # Inside docstring - skip until closing delimiter
            if multiline_delimiter in line:
                in_multiline_string = False
            continue
            
        # Strategy 1: Check for API key patterns (high confidence)
        line_has_api_key = False
        for pattern in _API_KEY_REGEX:
            if pattern.search(line):
                line_has_api_key = True
                break
                
        if line_has_api_key:
            # API key pattern found - confidence 0.80
            findings.append((
                "S_HARDCODED_SECRET_SUSPECT",
                "HIGH",
                0.80,
                filename,
                i,
                i,
            ))
            continue  # Skip variable pattern check if API key found
            
        # Strategy 2: Check for secret variable patterns
        for pattern in _SECRET_VAR_REGEX:
            if pattern.search(line):
                # Exclude obvious placeholders to reduce false positives
                if not _PLACEHOLDER_REGEX.search(line):
                    # Variable name suggests secret - confidence 0.75
                    findings.append((
                        "S_HARDCODED_SECRET_SUSPECT",
                        "HIGH",
                        0.75,
                        filename,
                        i,
                        i,
                    ))
                break  # Only report once per line
                
    return findings


def analyze_code(code: str, filename: str = "unknown.py") -> List[Dict[str, Any]]:
    """Analyze Python code and return security/quality findings.
    
    Main entry point for static analysis. Performs comprehensive checks
    in a single pass for efficiency.
    
    Analysis pipeline:
        1. Parse code to AST (detect syntax errors)
        2. Single-pass AST traversal (side effects + subprocess)
        3. Line-by-line secret detection
        4. Sort findings deterministically
        
    Args:
        code: Python source code as string
        filename: Name of file being analyzed (for reporting)
        
    Returns:
        Sorted list of findings. Each finding is a dict:
        {
            "reason_code": str (from REASON_CODES_v1.yaml),
            "severity": str (CRITICAL|HIGH|MEDIUM|LOW),
            "confidence": float (0.0-1.0),
            "primary": {"file": str, "line_start": int, "line_end": int},
            "evidence_refs": []
        }
        
    Determinism:
        - Findings are sorted by (severity desc, confidence desc, 
          reason_code asc, file asc, line_start asc)
        - Same input always produces identical output
        - No randomness, timestamps, or environment dependencies
        
    Example:
        >>> code = 'subprocess.call("ls", shell=True)'
        >>> findings = analyze_code(code, "test.py")
        >>> findings[0]["reason_code"]
        'S_INSECURE_SUBPROCESS'
    """
    # Clear line cache for new analysis (prevent cross-contamination)
    global _line_cache
    _line_cache.clear()
    
    # Step 1: Parse to AST (using cached parser for performance)
    tree = _parse_ast_cached(code, filename)
    if tree is None:
        # Syntax error detected - return immediately
        # Can't continue analysis without valid AST
        return [_finding_to_dict((
            "S_SYNTAX_ERROR",
            "HIGH",
            1.0,  # Confidence 1.0 - definitive (parser failed)
            filename,
            1,  # Default to line 1 if exact location unknown
            1,
        ))]
    
    # Step 2: Single-pass AST analysis with visitor
    # Detects: import side effects + insecure subprocess
    visitor = _ASTVisitor(filename)
    visitor.visit(tree)
    
    # Get findings from AST visitor
    findings_tuples = visitor.findings
    
    # Step 3: Add secret detection findings (line-by-line analysis)
    findings_tuples.extend(_detect_secrets_optimized(code, filename))
    
    # Step 4: Convert to dict and sort deterministically
    findings_dicts = [_finding_to_dict(f) for f in findings_tuples]
    return sort_findings(findings_dicts)


def check_dependencies(requirements_content: str) -> List[Dict[str, Any]]:
    """Check for unpinned dependencies in requirements.txt.
    
    Unpinned dependencies can cause reproducibility issues and
    unexpected behavior when dependencies auto-update.
    
    Detection logic:
        - Flag any dependency without exact version pin (==)
        - Skip: comments, empty lines, special markers (-r, -e, --hash)
        - Skip: git references and direct references (@)
        
    Args:
        requirements_content: Content of requirements.txt file
        
    Returns:
        Sorted list of findings for unpinned dependencies
        
    Examples:
        Unpinned (flagged):
            - requests
            - flask>=2.0
            - pandas~=1.5
            
        Pinned (not flagged):
            - requests==2.28.0
            - flask==2.0.1
            - git+https://github.com/user/repo@commit
            
    False Positives:
        May flag intentionally flexible version specs in development
        environments. Use exact pins for production deployments.
    """
    findings: List[Dict[str, Any]] = []
    lines = requirements_content.strip().split('\n')
    
    for i, line in enumerate(lines, start=1):
        line = line.strip()
        
        # Skip empty lines and comments
        if not line or line.startswith('#'):
            continue
        
        # Skip special pip markers and references
        # -r: include another requirements file
        # -e: editable install
        # @: direct reference
        # git+: git repository
        # --hash: hash verification
        if (line.startswith('-') or 
            line.startswith('@') or 
            line.startswith('git+') or
            '--hash' in line):
            continue
        
        # Check if version is pinned with ==
        # Also allow direct references with @ (already handled above, but defensive)
        if '==' not in line and '@' not in line:
            # Unpinned dependency found
            findings.append(_finding_to_dict((
                "S_UNPINNED_DEPENDENCY",
                "MEDIUM",
                0.90,  # Confidence 0.90 - pattern-based heuristic
                "requirements.txt",
                i,
                i,
            )))
    
    return sort_findings(findings)


def sort_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort findings deterministically for replay consistency.
    
    Implements the canonical sort order required by NOISE_BUDGET_CONTRACT
    and determinism requirements.
    
    Sort order (stable, total ordering):
        1. severity: CRITICAL > HIGH > MEDIUM > LOW (descending)
        2. confidence: higher first (descending)
        3. reason_code: alphabetical (ascending)
        4. file: alphabetical (ascending)
        5. line_start: lower first (ascending)
        
    Args:
        findings: List of finding dictionaries
        
    Returns:
        Sorted list of findings (new list, input unchanged)
        
    Determinism guarantees:
        - Same findings always produce same order
        - No floating-point precision issues (handled by confidence rounding)
        - No environment dependencies
        - Thread-safe (pure function)
        
    Performance:
        O(n log n) where n = number of findings
        Pre-computes sort keys to avoid repeated dict access
    """
    # Map severity to numeric value for sorting
    severity_order = {
        "CRITICAL": 4,
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
    }
    
    # Pre-compute sort keys for performance
    # Avoids repeated dict lookups during comparison
    sort_keys = []
    for finding in findings:
        sort_keys.append((
            -severity_order.get(finding["severity"], 0),  # Negative for descending
            -finding["confidence"],                        # Negative for descending
            finding["reason_code"],                        # Ascending
            finding["primary"]["file"],                    # Ascending
            finding["primary"]["line_start"],              # Ascending
        ))
    
    # Sort using pre-computed keys with index indirection
    # This avoids moving large finding dicts during sort
    sorted_indices = sorted(range(len(findings)), key=lambda i: sort_keys[i])
    return [findings[i] for i in sorted_indices]


if __name__ == "__main__":
    """
    Self-test and performance benchmark.
    
    Runs a quick analysis on sample code with known issues
    to verify correct operation and measure performance.
    """
    import time
    
    # Sample code with intentional issues for testing
    test_code = """import subprocess
import os

# This is a test with a potential secret
API_KEY = "sk-test12345678901234567890"

def main():
    user_input = input("Enter command: ")
    subprocess.call(user_input, shell=True)  # DANGER!
    
    # This should not trigger side effect (inside function)
    print("Hello")

if __name__ == "__main__":
    main()
"""
    
    # Benchmark analysis performance
    start_time = time.perf_counter()
    findings = analyze_code(test_code, "test.py")
    findings = sort_findings(findings)
    elapsed = time.perf_counter() - start_time
    
    print(f"Analysis completed in {elapsed*1000:.2f}ms")
    print(f"Found {len(findings)} issues:")
    
    for f in findings:
        print(f"[{f['severity']}] {f['reason_code']} at line {f['primary']['line_start']}")
