"""
TRINITY_M1 — Typed Models / Schema Contracts
Mirrors GOLDEN_IO_LOCK_TRINITY_M1.yaml exactly. No extra fields.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------

class BarItem:
    """Single OHLCV bar."""

    __slots__ = ("ts_utc", "o", "h", "l", "c", "v")

    def __init__(
        self,
        ts_utc: str,
        o: float,
        h: float,
        l: float,
        c: float,
        v: float,
    ) -> None:
        self.ts_utc: str = ts_utc
        self.o: float = float(o)
        self.h: float = float(h)
        self.l: float = float(l)
        self.c: float = float(c)
        self.v: float = float(v)


class MetaInput:
    """Input meta block."""

    __slots__ = ("source", "run_id")

    def __init__(self, source: str, run_id: str) -> None:
        self.source: str = source
        self.run_id: str = run_id


class InputPayload:
    """Validated input payload for run_trinity_m1."""

    __slots__ = ("symbol", "timeframe", "bars", "meta")

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        bars: List[BarItem],
        meta: MetaInput,
    ) -> None:
        self.symbol: str = symbol
        self.timeframe: str = timeframe
        self.bars: List[BarItem] = bars
        self.meta: MetaInput = meta


# ---------------------------------------------------------------------------
# Output models (typed dicts for serialization)
# ---------------------------------------------------------------------------

class KalmanStateLast:
    """Last Kalman filter state."""

    __slots__ = ("x", "p")

    def __init__(self, x: float, p: float) -> None:
        self.x: float = x
        self.p: float = p

    def to_dict(self) -> Dict[str, Any]:
        return {"x": self.x, "p": self.p}


class CleanedStructureSignal:
    """Output: cleaned_structure_signal block."""

    __slots__ = ("cleaned_close", "trend_component", "cycle_component", "kalman_state_last")

    def __init__(
        self,
        cleaned_close: List[float],
        trend_component: List[float],
        cycle_component: List[float],
        kalman_state_last: KalmanStateLast,
    ) -> None:
        self.cleaned_close: List[float] = cleaned_close
        self.trend_component: List[float] = trend_component
        self.cycle_component: List[float] = cycle_component
        self.kalman_state_last: KalmanStateLast = kalman_state_last

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cleaned_close": self.cleaned_close,
            "trend_component": self.trend_component,
            "cycle_component": self.cycle_component,
            "kalman_state_last": self.kalman_state_last.to_dict(),
        }


class NoiseResidual:
    """Output: noise_residual block."""

    __slots__ = ("residuals", "mean", "std")

    def __init__(self, residuals: List[float], mean: float, std: float) -> None:
        self.residuals: List[float] = residuals
        self.mean: float = mean
        self.std: float = std

    def to_dict(self) -> Dict[str, Any]:
        return {
            "residuals": self.residuals,
            "mean": self.mean,
            "std": self.std,
        }


class SpectralSignature:
    """Output: spectral_signature block."""

    __slots__ = ("dominant_frequencies", "amplitudes", "phases")

    def __init__(
        self,
        dominant_frequencies: List[float],
        amplitudes: List[float],
        phases: List[float],
    ) -> None:
        self.dominant_frequencies: List[float] = dominant_frequencies
        self.amplitudes: List[float] = amplitudes
        self.phases: List[float] = phases

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dominant_frequencies": self.dominant_frequencies,
            "amplitudes": self.amplitudes,
            "phases": self.phases,
        }


class RawRefs:
    """Evidence log raw_refs block."""

    __slots__ = ("segment_hash", "residual_indices")

    def __init__(self, segment_hash: str, residual_indices: List[int]) -> None:
        self.segment_hash: str = segment_hash
        self.residual_indices: List[int] = residual_indices

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment_hash": self.segment_hash,
            "residual_indices": self.residual_indices,
        }


class EvidenceRecord:
    """Single evidence_log record."""

    __slots__ = (
        "timestamp_utc",
        "pattern_name",
        "confidence_0_1",
        "evidence_strength",
        "raw_refs",
    )

    def __init__(
        self,
        timestamp_utc: str,
        pattern_name: str,
        confidence_0_1: float,
        evidence_strength: float,
        raw_refs: RawRefs,
    ) -> None:
        self.timestamp_utc: str = timestamp_utc
        self.pattern_name: str = pattern_name
        self.confidence_0_1: float = confidence_0_1
        self.evidence_strength: float = evidence_strength
        self.raw_refs: RawRefs = raw_refs

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp_utc": self.timestamp_utc,
            "pattern_name": self.pattern_name,
            "confidence_0_1": self.confidence_0_1,
            "evidence_strength": self.evidence_strength,
            "raw_refs": self.raw_refs.to_dict(),
        }


class DeviationMetrics:
    """Deviation metrics block."""

    __slots__ = ("hl_spread_mean", "close_deviation_std", "volume_cv")

    def __init__(
        self,
        hl_spread_mean: float,
        close_deviation_std: float,
        volume_cv: float,
    ) -> None:
        self.hl_spread_mean: float = hl_spread_mean
        self.close_deviation_std: float = close_deviation_std
        self.volume_cv: float = volume_cv

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hl_spread_mean": self.hl_spread_mean,
            "close_deviation_std": self.close_deviation_std,
            "volume_cv": self.volume_cv,
        }


class EvidenceFeatures:
    """Evidence features block."""

    __slots__ = ("bar_count", "symbol", "timeframe", "run_id")

    def __init__(
        self,
        bar_count: int,
        symbol: str,
        timeframe: str,
        run_id: str,
    ) -> None:
        self.bar_count: int = bar_count
        self.symbol: str = symbol
        self.timeframe: str = timeframe
        self.run_id: str = run_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bar_count": self.bar_count,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "run_id": self.run_id,
        }


class BrokerAudit:
    """Output: broker_audit block."""

    __slots__ = (
        "trust_score",
        "trust_state",
        "deviation_metrics",
        "evidence_features",
        "patterns_detected",
        "evidence_log",
    )

    def __init__(
        self,
        trust_score: float,
        trust_state: str,
        deviation_metrics: DeviationMetrics,
        evidence_features: EvidenceFeatures,
        patterns_detected: List[str],
        evidence_log: List[EvidenceRecord],
    ) -> None:
        self.trust_score: float = trust_score
        self.trust_state: str = trust_state
        self.deviation_metrics: DeviationMetrics = deviation_metrics
        self.evidence_features: EvidenceFeatures = evidence_features
        self.patterns_detected: List[str] = patterns_detected
        self.evidence_log: List[EvidenceRecord] = evidence_log

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trust_score": self.trust_score,
            "trust_state": self.trust_state,
            "deviation_metrics": self.deviation_metrics.to_dict(),
            "evidence_features": self.evidence_features.to_dict(),
            "patterns_detected": self.patterns_detected,
            "evidence_log": [r.to_dict() for r in self.evidence_log],
        }


class OutputMetadata:
    """Output: metadata block."""

    __slots__ = ("processing_time_ms", "audit_quality")

    def __init__(self, processing_time_ms: float, audit_quality: str) -> None:
        self.processing_time_ms: float = processing_time_ms
        self.audit_quality: str = audit_quality

    def to_dict(self) -> Dict[str, Any]:
        return {
            "processing_time_ms": self.processing_time_ms,
            "audit_quality": self.audit_quality,
        }


class OutputPayload:
    """Full output payload per GOLDEN_IO_LOCK_TRINITY_M1.yaml."""

    __slots__ = (
        "cleaned_structure_signal",
        "noise_residual",
        "spectral_signature",
        "broker_audit",
        "metadata",
    )

    def __init__(
        self,
        cleaned_structure_signal: CleanedStructureSignal,
        noise_residual: NoiseResidual,
        spectral_signature: SpectralSignature,
        broker_audit: BrokerAudit,
        metadata: OutputMetadata,
    ) -> None:
        self.cleaned_structure_signal: CleanedStructureSignal = cleaned_structure_signal
        self.noise_residual: NoiseResidual = noise_residual
        self.spectral_signature: SpectralSignature = spectral_signature
        self.broker_audit: BrokerAudit = broker_audit
        self.metadata: OutputMetadata = metadata

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cleaned_structure_signal": self.cleaned_structure_signal.to_dict(),
            "noise_residual": self.noise_residual.to_dict(),
            "spectral_signature": self.spectral_signature.to_dict(),
            "broker_audit": self.broker_audit.to_dict(),
            "metadata": self.metadata.to_dict(),
        }
