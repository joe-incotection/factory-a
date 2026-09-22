"""
safe_stats — Deterministic numeric series summarizer.

Public API:
    run_safe_stats(input_payload: dict) -> dict

Usage:
    from safe_stats import run_safe_stats
    result = run_safe_stats({"values": [1, 2, 3], "meta": {"run_id": "RUN_001"}})
"""

from .engine import run_safe_stats

__all__ = ["run_safe_stats"]
__version__ = "1.0.0"
