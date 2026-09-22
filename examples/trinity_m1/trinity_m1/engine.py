"""
TRINITY_M1 — Engine
Single public entry point: run_trinity_m1(input_payload: dict) -> dict

Orchestrates: validate → kalman → fourier → jacobian → audit → output
No wall-clock in core logic. No randomness. Deterministic.
processing_time_ms is always 0.0 to preserve determinism (INV_NO_WALL_CLOCK).
"""

from __future__ import annotations

from typing import List

from trinity_m1.audit import (
    build_broker_audit,
    classify_trust_state,
    compute_trust_score,
    detect_patterns,
)
from trinity_m1.constants import (
    AUDIT_QUALITY_NORMAL,
    RC_INTERNAL_ERROR,
)
from trinity_m1.exceptions import TrinityM1Error
from trinity_m1.fourier import compute_spectral_signature
from trinity_m1.jacobian import (
    compute_deviation_metrics,
    compute_residuals,
)
from trinity_m1.kalman import decompose_trend_cycle, kalman_filter
from trinity_m1.models import (
    CleanedStructureSignal,
    OutputMetadata,
    OutputPayload,
)
from trinity_m1.utils import validate_input


def run_trinity_m1(input_payload: dict) -> dict:
    """Run TRINITY_M1 feature generation pipeline.

    Converts raw OHLCV bar stream into clean, audited features.
    This module is a feature generator + audit producer only.
    It does NOT make trade decisions.

    Args:
        input_payload: Raw input dict per GOLDEN_IO_LOCK_TRINITY_M1.yaml input_contract.

    Returns:
        Output dict per GOLDEN_IO_LOCK_TRINITY_M1.yaml output_contract.

    Raises:
        TrinityM1Error: On hard-fail with allowlisted reason_codes.
    """
    try:
        # ----------------------------------------------------------------
        # Step 1: Validate input
        # ----------------------------------------------------------------
        payload = validate_input(input_payload)

        bars = payload.bars
        symbol = payload.symbol
        timeframe = payload.timeframe
        run_id = payload.meta.run_id

        # Extract close prices and other bar data
        closes: List[float] = [b.c for b in bars]
        highs: List[float] = [b.h for b in bars]
        lows: List[float] = [b.l for b in bars]
        volumes: List[float] = [b.v for b in bars]

        # Last bar timestamp (from input — not wall-clock)
        last_bar_ts: str = bars[-1].ts_utc

        # ----------------------------------------------------------------
        # Step 2: Kalman filter → cleaned_structure_signal
        # ----------------------------------------------------------------
        smoothed, kalman_state_last = kalman_filter(closes)
        trend_component, cycle_component = decompose_trend_cycle(smoothed, closes)

        cleaned_structure_signal = CleanedStructureSignal(
            cleaned_close=smoothed,
            trend_component=trend_component,
            cycle_component=cycle_component,
            kalman_state_last=kalman_state_last,
        )

        # ----------------------------------------------------------------
        # Step 3: Residuals → noise_residual
        # ----------------------------------------------------------------
        noise_residual = compute_residuals(closes, smoothed)

        # ----------------------------------------------------------------
        # Step 4: Fourier → spectral_signature
        # ----------------------------------------------------------------
        spectral_signature = compute_spectral_signature(closes)

        # ----------------------------------------------------------------
        # Step 5: Deviation metrics
        # ----------------------------------------------------------------
        hl_spread_mean, close_deviation_std, volume_cv = compute_deviation_metrics(
            bars_h=highs,
            bars_l=lows,
            bars_c=closes,
            bars_v=volumes,
        )

        # ----------------------------------------------------------------
        # Step 6: Trust score + state
        # ----------------------------------------------------------------
        trust_score = compute_trust_score(
            hl_spread_mean=hl_spread_mean,
            close_deviation_std=close_deviation_std,
            volume_cv=volume_cv,
        )
        trust_state = classify_trust_state(trust_score)

        # ----------------------------------------------------------------
        # Step 7: Pattern detection + evidence_log
        # ----------------------------------------------------------------
        patterns_detected, evidence_log = detect_patterns(
            residuals=noise_residual.residuals,
            close_deviation_std=close_deviation_std,
            hl_spread_mean=hl_spread_mean,
        )

        # ----------------------------------------------------------------
        # Step 8: Build broker_audit
        # ----------------------------------------------------------------
        evidence_features_data = {
            "bar_count": len(bars),
            "symbol": symbol,
            "timeframe": timeframe,
            "run_id": run_id,
        }

        broker_audit = build_broker_audit(
            trust_score=trust_score,
            trust_state=trust_state,
            hl_spread_mean=hl_spread_mean,
            close_deviation_std=close_deviation_std,
            volume_cv=volume_cv,
            evidence_features_data=evidence_features_data,
            patterns_detected=patterns_detected,
            evidence_log=evidence_log,
            last_bar_ts=last_bar_ts,
        )

        # ----------------------------------------------------------------
        # Step 9: Determine audit_quality
        # ----------------------------------------------------------------
        audit_quality = AUDIT_QUALITY_NORMAL

        # ----------------------------------------------------------------
        # Step 10: processing_time_ms = 0.0 (deterministic per INV_NO_WALL_CLOCK)
        # Wall-clock must not affect output hash. Schema requires number >= 0.
        # ----------------------------------------------------------------
        processing_time_ms: float = 0.0

        # ----------------------------------------------------------------
        # Step 11: Build output
        # ----------------------------------------------------------------
        output = OutputPayload(
            cleaned_structure_signal=cleaned_structure_signal,
            noise_residual=noise_residual,
            spectral_signature=spectral_signature,
            broker_audit=broker_audit,
            metadata=OutputMetadata(
                processing_time_ms=processing_time_ms,
                audit_quality=audit_quality,
            ),
        )

        return output.to_dict()

    except TrinityM1Error:
        # Re-raise hard-fail errors as-is
        raise
    except Exception as exc:
        # Wrap unexpected errors as INTERNAL_ERROR
        raise TrinityM1Error(
            reason_codes=[RC_INTERNAL_ERROR],
            message=f"run_trinity_m1 unexpected error: {exc}",
        ) from exc
