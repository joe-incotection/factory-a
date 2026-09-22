"""
TRINITY_M1 — Exceptions
Fail-closed typed exceptions mapped to reason codes allowlist.
"""

from __future__ import annotations

from typing import List


class TrinityM1Error(Exception):
    """Hard-fail exception for TRINITY_M1.

    Attributes:
        reason_codes: List of allowlisted reason codes (from TRINITY_M1_REASON_CODES.yaml).
        message: Human-readable message. NOT used for policy decisions.
    """

    def __init__(self, reason_codes: List[str], message: str = "") -> None:
        self.reason_codes: List[str] = reason_codes
        self.message: str = message
        super().__init__(message)

    def __repr__(self) -> str:
        return f"TrinityM1Error(reason_codes={self.reason_codes!r}, message={self.message!r})"
