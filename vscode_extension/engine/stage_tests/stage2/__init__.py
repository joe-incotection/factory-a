"""
Stage2 Validator — Complete 6-Module Pipeline
Version: 1.0 (AIEL-3 Certified)

M1: core_contracts - Schema validation + canonicalization
M2: ingest_enumerator - ZIP processing + manifest generation
M3: sandbox_runner - Secure command execution
M4: engine_aiel_s_py - Static code analysis
M5: engine_aiel_t_py - Runtime test execution + validation
M6: aggregate_and_report - Score aggregation + final verdict

All modules: 7/7 golden tests PASSED
Integration: 18/18 tests PASSED
Status: Production Ready
"""

# M1: Core Contracts
from .core_contracts import (
    canonical_json,
    validate_module_descriptor
)

# M2: Ingest Enumerator
from .ingest_enumerator.manifest import (
    process_zip,
    compute_file_sha256,
    compute_manifest_digest
)
from .ingest_enumerator.module_detection import (
    generate_module_descriptors,
    compute_module_id
)

# M3: Sandbox Runner
from .sandbox_runner.runner import (
    run_command,
    compute_evidence_ref
)
from .sandbox_runner.allowlist import (
    is_command_allowed,
    get_default_allowlist
)
from .sandbox_runner.toolchain import (
    get_toolchain_manifest,
    get_python_version
)

# M4: Static Analysis Engine
from .engine_aiel_s_py import (
    analyze_code,
    check_dependencies,
    sort_findings
)

# M5: Runtime Testing Engine
from .engine_aiel_t_py import (
    run_tests,
    compute_runtime_score,
    detect_flaky_tests,
    validate_test_results
)

# M6: Aggregation & Report
from .aggregate_and_report import (
    sort_findings as sort_findings_m6,
    deduplicate_findings,
    compute_module_g_score,
    compute_repo_score,
    apply_noise_budget,
    compute_final_verdict,
    generate_validation_result,
    aggregate_and_report
)

__all__ = [
    # M1
    "canonical_json",
    "validate_module_descriptor",
    
    # M2
    "process_zip",
    "compute_file_sha256",
    "compute_manifest_digest",
    "generate_module_descriptors",
    "compute_module_id",
    
    # M3
    "run_command",
    "compute_evidence_ref",
    "is_command_allowed",
    "get_default_allowlist",
    "get_toolchain_manifest",
    "get_python_version",
    
    # M4
    "analyze_code",
    "check_dependencies",
    "sort_findings",
    
    # M5
    "run_tests",
    "compute_runtime_score",
    "detect_flaky_tests",
    "validate_test_results",
    
    # M6
    "sort_findings_m6",
    "deduplicate_findings",
    "compute_module_g_score",
    "compute_repo_score",
    "apply_noise_budget",
    "compute_final_verdict",
    "generate_validation_result",
    "aggregate_and_report",
]

__version__ = "1.0.0"
