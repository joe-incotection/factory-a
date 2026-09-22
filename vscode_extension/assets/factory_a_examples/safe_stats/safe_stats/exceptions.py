"""
exceptions.py — SafeStatsError for SAFE_STATS module.
reason_codes MUST be from REASON_CODE_ALLOWLIST in constants.py.
"""

from __future__ import annotations


class SafeStatsError(Exception):
    """Hard-fail error raised by SAFE_STATS on any validation or internal fault.

    All reason codes must come from the REASON_CODE_ALLOWLIST defined in
    constants.py.  The ``message`` field is for human diagnostics only and
    must NOT be used to drive policy decisions.

    Attributes:
        reason_codes: Non-empty list of allowlisted reason-code strings.
        message: Human-readable description of the fault (diagnostic only).
    """

    def __init__(self, reason_codes: list[str], message: str) -> None:
        """Initialize SafeStatsError with reason codes and a diagnostic message.

        Args:
            reason_codes: Non-empty list of allowlisted reason-code strings.
                Each code must appear in REASON_CODE_ALLOWLIST.
            message: Human-readable description of the fault.  Not used for
                policy; callers should inspect ``reason_codes`` instead.

        Raises:
            ValueError: If ``reason_codes`` is not a list or is empty.
        """
        # Guard: reason_codes must be a non-empty list so callers always have
        # at least one machine-readable code to inspect.
        if not isinstance(reason_codes, list) or len(reason_codes) == 0:
            raise ValueError("reason_codes must be a non-empty list")
        super().__init__(message)
        self.reason_codes: list[str] = reason_codes
        self.message: str = message

    def __repr__(self) -> str:
        """Return unambiguous developer-facing representation.

        Returns:
            String of the form
            ``SafeStatsError(reason_codes=[...], message='...')``.
        """
        return (
            f"SafeStatsError(reason_codes={self.reason_codes!r}, "
            f"message={self.message!r})"
        )
