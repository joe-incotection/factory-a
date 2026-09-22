"""
TRINITY_M1 — Kalman Filter
Pure deterministic 1D Kalman filter for close price smoothing.
No wall-clock. No randomness. State only from inputs.
"""

from __future__ import annotations

from typing import List, Tuple

from trinity_m1.constants import (
    KALMAN_INITIAL_COVARIANCE,
    KALMAN_MEASUREMENT_NOISE,
    KALMAN_PROCESS_NOISE,
    RC_KALMAN_INIT_FAIL,
    RC_KALMAN_STEP_FAIL,
)
from trinity_m1.exceptions import TrinityM1Error
from trinity_m1.models import KalmanStateLast


def kalman_filter(
    observations: List[float],
    process_noise: float = KALMAN_PROCESS_NOISE,
    measurement_noise: float = KALMAN_MEASUREMENT_NOISE,
    initial_covariance: float = KALMAN_INITIAL_COVARIANCE,
) -> Tuple[List[float], KalmanStateLast]:
    """Run 1D Kalman filter over a list of observations.

    Args:
        observations: List of float values (e.g. close prices).
        process_noise: Q — process noise covariance.
        measurement_noise: R — measurement noise covariance.
        initial_covariance: P0 — initial estimate covariance.

    Returns:
        Tuple of (smoothed_values, last_state).

    Raises:
        TrinityM1Error: On init or step failure.
    """
    if not observations:
        raise TrinityM1Error(
            reason_codes=[RC_KALMAN_INIT_FAIL],
            message="kalman_filter: observations list is empty",
        )

    try:
        x: float = observations[0]  # initial state estimate
        p: float = initial_covariance  # initial covariance
    except Exception as exc:
        raise TrinityM1Error(
            reason_codes=[RC_KALMAN_INIT_FAIL],
            message=f"kalman_filter init failed: {exc}",
        ) from exc

    smoothed: List[float] = []

    for i, z in enumerate(observations):
        try:
            # Predict
            x_pred: float = x
            p_pred: float = p + process_noise

            # Update
            k: float = p_pred / (p_pred + measurement_noise)  # Kalman gain
            x = x_pred + k * (z - x_pred)
            p = (1.0 - k) * p_pred

            smoothed.append(x)
        except Exception as exc:
            raise TrinityM1Error(
                reason_codes=[RC_KALMAN_STEP_FAIL],
                message=f"kalman_filter step {i} failed: {exc}",
            ) from exc

    last_state = KalmanStateLast(x=x, p=p)
    return smoothed, last_state


def decompose_trend_cycle(
    smoothed: List[float],
    original: List[float],
) -> Tuple[List[float], List[float]]:
    """Decompose smoothed signal into trend and cycle components.

    Args:
        smoothed: Kalman-smoothed values (trend).
        original: Original observations.

    Returns:
        Tuple of (trend_component, cycle_component).
        cycle = original - trend.
    """
    trend: List[float] = list(smoothed)
    cycle: List[float] = [o - t for o, t in zip(original, smoothed)]
    return trend, cycle
