"""
TRINITY_M1 — Jacobian / Residual Helpers
Pure deterministic residual and coupling computation.
No wall-clock. No randomness.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import List, Tuple

from trinity_m1.constants import (
    RC_JACOBIAN_COMPUTE_FAIL,
    RC_NAN_INF_DETECTED,
)
from trinity_m1.exceptions import TrinityM1Error
from trinity_m1.models import NoiseResidual, RawRefs


def compute_residuals(
    original: List[float],
    smoothed: List[float],
) -> NoiseResidual:
    """Compute noise residuals: original - smoothed.

    Args:
        original: Original signal values.
        smoothed: Kalman-smoothed values.

    Returns:
        NoiseResidual with residuals, mean, std.

    Raises:
        TrinityM1Error: On NaN/Inf or computation failure.
    """
    if len(original) != len(smoothed):
        raise TrinityM1Error(
            reason_codes=[RC_JACOBIAN_COMPUTE_FAIL],
            message=(
                f"compute_residuals: length mismatch "
                f"original={len(original)} smoothed={len(smoothed)}"
            ),
        )

    try:
        residuals: List[float] = []
        for i, (o, s) in enumerate(zip(original, smoothed)):
            r = o - s
            if math.isnan(r) or math.isinf(r):
                raise TrinityM1Error(
                    reason_codes=[RC_NAN_INF_DETECTED],
                    message=f"compute_residuals: NaN/Inf at index {i}",
                )
            residuals.append(r)

        n = len(residuals)
        mean = sum(residuals) / n if n > 0 else 0.0
        variance = sum((r - mean) ** 2 for r in residuals) / n if n > 0 else 0.0
        std = math.sqrt(variance)

        if math.isnan(mean) or math.isinf(mean):
            raise TrinityM1Error(
                reason_codes=[RC_NAN_INF_DETECTED],
                message="compute_residuals: NaN/Inf in mean",
            )
        if math.isnan(std) or math.isinf(std):
            raise TrinityM1Error(
                reason_codes=[RC_NAN_INF_DETECTED],
                message="compute_residuals: NaN/Inf in std",
            )

    except TrinityM1Error:
        raise
    except Exception as exc:
        raise TrinityM1Error(
            reason_codes=[RC_JACOBIAN_COMPUTE_FAIL],
            message=f"compute_residuals failed: {exc}",
        ) from exc

    return NoiseResidual(residuals=residuals, mean=mean, std=std)


def compute_segment_hash(values: List[float], float_precision: int = 6) -> str:
    """Compute deterministic SHA-256 hash of a float segment.

    Args:
        values: List of float values.
        float_precision: Decimal precision for rounding before hashing.

    Returns:
        Hex SHA-256 string.
    """
    rounded = [round(v, float_precision) for v in values]
    canonical = json.dumps(rounded, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_raw_refs(
    residuals: List[float],
    float_precision: int = 6,
) -> RawRefs:
    """Build RawRefs from residuals for evidence_log.

    Args:
        residuals: Noise residual values.
        float_precision: Decimal precision for hashing.

    Returns:
        RawRefs with segment_hash and residual_indices.
    """
    segment_hash = compute_segment_hash(residuals, float_precision)
    residual_indices = list(range(len(residuals)))
    return RawRefs(segment_hash=segment_hash, residual_indices=residual_indices)


def compute_deviation_metrics(
    bars_h: List[float],
    bars_l: List[float],
    bars_c: List[float],
    bars_v: List[float],
) -> Tuple[float, float, float]:
    """Compute deviation metrics from bar data.

    Args:
        bars_h: High prices.
        bars_l: Low prices.
        bars_c: Close prices.
        bars_v: Volumes.

    Returns:
        Tuple of (hl_spread_mean, close_deviation_std, volume_cv).

    Raises:
        TrinityM1Error: On NaN/Inf or computation failure.
    """
    try:
        n = len(bars_c)
        if n == 0:
            raise TrinityM1Error(
                reason_codes=[RC_JACOBIAN_COMPUTE_FAIL],
                message="compute_deviation_metrics: empty bars",
            )

        # HL spread mean
        hl_spreads = [h - l for h, l in zip(bars_h, bars_l)]
        hl_spread_mean = sum(hl_spreads) / n

        # Close deviation std
        close_mean = sum(bars_c) / n
        close_variance = sum((c - close_mean) ** 2 for c in bars_c) / n
        close_deviation_std = math.sqrt(close_variance)

        # Volume coefficient of variation
        vol_mean = sum(bars_v) / n
        if vol_mean == 0.0:
            volume_cv = 0.0
        else:
            vol_variance = sum((v - vol_mean) ** 2 for v in bars_v) / n
            vol_std = math.sqrt(vol_variance)
            volume_cv = vol_std / vol_mean

        # Validate
        for name, val in [
            ("hl_spread_mean", hl_spread_mean),
            ("close_deviation_std", close_deviation_std),
            ("volume_cv", volume_cv),
        ]:
            if math.isnan(val) or math.isinf(val):
                raise TrinityM1Error(
                    reason_codes=[RC_NAN_INF_DETECTED],
                    message=f"compute_deviation_metrics: NaN/Inf in {name}",
                )

    except TrinityM1Error:
        raise
    except Exception as exc:
        raise TrinityM1Error(
            reason_codes=[RC_JACOBIAN_COMPUTE_FAIL],
            message=f"compute_deviation_metrics failed: {exc}",
        ) from exc

    return hl_spread_mean, close_deviation_std, volume_cv
