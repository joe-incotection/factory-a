"""
TRINITY_M1 — Fourier Spectral Analysis
Pure deterministic spectral feature extraction.
No wall-clock. No randomness. Uses only input data.
"""

from __future__ import annotations

import cmath
import math
from typing import List, Tuple

from trinity_m1.constants import (
    FOURIER_TOP_N_COMPONENTS,
    RC_FOURIER_COMPUTE_FAIL,
    RC_FOURIER_SPECTRAL_SIGNATURE_INVALID,
    RC_NAN_INF_DETECTED,
)
from trinity_m1.exceptions import TrinityM1Error
from trinity_m1.models import SpectralSignature


def _dft(signal: List[float]) -> List[complex]:  # noqa: N802
    """Compute Discrete Fourier Transform (DFT) without numpy.

    Pure Python implementation for determinism.
    Used as fallback for non-power-of-2 lengths.

    Args:
        signal: Input float signal values.

    Returns:
        List of complex DFT coefficients (length == len(signal)).
    """
    n = len(signal)
    result: List[complex] = []
    for k in range(n):
        total = complex(0.0, 0.0)
        for t in range(n):
            angle = -2.0 * math.pi * k * t / n
            total += signal[t] * cmath.exp(complex(0.0, angle))
        result.append(total)
    return result


def _fft_recursive(signal: List[complex]) -> List[complex]:
    """Cooley-Tukey FFT (recursive). Works on power-of-2 lengths.

    Args:
        signal: Complex input signal.

    Returns:
        FFT coefficients.
    """
    n = len(signal)
    if n <= 1:
        return list(signal)
    if n % 2 != 0:
        # Fall back to DFT for non-power-of-2
        return _dft([x.real for x in signal])

    even = _fft_recursive(signal[0::2])
    odd = _fft_recursive(signal[1::2])

    result: List[complex] = [complex(0.0, 0.0)] * n
    for k in range(n // 2):
        angle = -2.0 * math.pi * k / n
        twiddle = cmath.exp(complex(0.0, angle)) * odd[k]
        result[k] = even[k] + twiddle
        result[k + n // 2] = even[k] - twiddle
    return result


def _next_power_of_2(n: int) -> int:
    """Return smallest power of 2 >= n."""
    p = 1
    while p < n:
        p <<= 1
    return p


def compute_spectral_signature(
    signal: List[float],
    top_n: int = FOURIER_TOP_N_COMPONENTS,
) -> SpectralSignature:
    """Compute spectral signature from a signal using FFT.

    Args:
        signal: Input float signal (e.g. close prices or residuals).
        top_n: Number of dominant frequency components to extract.

    Returns:
        SpectralSignature with dominant_frequencies, amplitudes, phases.

    Raises:
        TrinityM1Error: On computation failure or NaN/Inf detected.
    """
    if not signal:
        raise TrinityM1Error(
            reason_codes=[RC_FOURIER_COMPUTE_FAIL],
            message="compute_spectral_signature: signal is empty",
        )

    n = len(signal)

    # Validate no NaN/Inf in input
    for i, v in enumerate(signal):
        if math.isnan(v) or math.isinf(v):
            raise TrinityM1Error(
                reason_codes=[RC_NAN_INF_DETECTED],
                message=f"compute_spectral_signature: NaN/Inf at index {i}",
            )

    try:
        # Zero-pad to next power of 2 for FFT efficiency
        padded_n = _next_power_of_2(n)
        padded: List[complex] = [complex(v, 0.0) for v in signal]
        padded += [complex(0.0, 0.0)] * (padded_n - n)

        fft_result = _fft_recursive(padded)

        # Only use first half (positive frequencies)
        half = padded_n // 2
        amplitudes_all: List[float] = []
        phases_all: List[float] = []
        freqs_all: List[float] = []

        for k in range(half):
            coeff = fft_result[k]
            amp = abs(coeff) / padded_n
            phase = cmath.phase(coeff)
            freq = k / padded_n  # normalized frequency [0, 0.5)

            # Validate
            if math.isnan(amp) or math.isinf(amp):
                raise TrinityM1Error(
                    reason_codes=[RC_FOURIER_SPECTRAL_SIGNATURE_INVALID],
                    message=f"NaN/Inf amplitude at freq index {k}",
                )

            amplitudes_all.append(amp)
            phases_all.append(phase)
            freqs_all.append(freq)

        # Sort by amplitude descending, take top_n
        indexed = sorted(
            range(len(amplitudes_all)),
            key=lambda i: amplitudes_all[i],
            reverse=True,
        )
        top_indices = indexed[:top_n]
        # Sort top_indices by frequency (ascending) for determinism
        top_indices_sorted = sorted(top_indices, key=lambda i: freqs_all[i])

        dominant_frequencies = [freqs_all[i] for i in top_indices_sorted]
        amplitudes = [amplitudes_all[i] for i in top_indices_sorted]
        phases = [phases_all[i] for i in top_indices_sorted]

    except TrinityM1Error:
        raise
    except Exception as exc:
        raise TrinityM1Error(
            reason_codes=[RC_FOURIER_COMPUTE_FAIL],
            message=f"compute_spectral_signature failed: {exc}",
        ) from exc

    return SpectralSignature(
        dominant_frequencies=dominant_frequencies,
        amplitudes=amplitudes,
        phases=phases,
    )
