"""
TRINITY_M1 — Audit Builder
Builds broker_audit block and evidence_log records.
Evidence logging is OUTPUT DATA, not runtime logging.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Dict, List, Tuple

from trinity_m1.constants import (
    DEVIATION_HIGH_THRESHOLD,
    TRUST_SCORE_TRUSTED,
    TRUST_SCORE_WATCH,
    TRUST_STATE_TRUSTED,
    TRUST_STATE_UNTRUSTED,
    TRUST_STATE_WATCH,
    RC_BROKER_DEVIATION_HIGH,
    RC_TRUST_SCORE_LOW,
)
from trinity_m1.models import (
    BrokerAudit,
    DeviationMetrics,
    EvidenceFeatures,
    EvidenceRecord,
    RawRefs,
)

# Sentinel timestamp replaced by engine with actual last bar ts
_TS_SENTINEL: str = "1970-01-01T00:00:00Z"


def _compute_segment_hash(residuals: List[float], float_precision: int = 6) -> str:
    """Compute deterministic SHA-256 hash of residuals list.

    Args:
        residuals: Noise residual values.
        float_precision: Decimal precision for rounding before hashing.

    Returns:
        Hex SHA-256 string.
    """
    rounded = [round(v, float_precision) for v in residuals]
    canonical = json.dumps(rounded, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_trust_score(
    hl_spread_mean: float,
    close_deviation_std: float,
    volume_cv: float,
) -> float:
    """Compute trust score [0.0, 1.0] from deviation metrics.

    Higher deviation → lower trust.
    Formula: trust = 1 / (1 + weighted_deviation)

    Args:
        hl_spread_mean: Mean HL spread.
        close_deviation_std: Close price std deviation.
        volume_cv: Volume coefficient of variation.

    Returns:
        Trust score clamped to [0.0, 1.0].
    """
    weighted = (
        abs(hl_spread_mean) * 0.4
        + abs(close_deviation_std) * 0.4
        + abs(volume_cv) * 0.2
    )
    trust = 1.0 / (1.0 + weighted)
    return max(0.0, min(1.0, trust))


def classify_trust_state(trust_score: float) -> str:
    """Classify trust state from trust score.

    Args:
        trust_score: Float in [0.0, 1.0].

    Returns:
        One of TRUSTED, WATCH, UNTRUSTED (from constants).
    """
    if trust_score >= TRUST_SCORE_TRUSTED:
        return TRUST_STATE_TRUSTED
    elif trust_score >= TRUST_SCORE_WATCH:
        return TRUST_STATE_WATCH
    else:
        return TRUST_STATE_UNTRUSTED


def detect_patterns(
    residuals: List[float],
    close_deviation_std: float,
    hl_spread_mean: float,
) -> Tuple[List[str], List[EvidenceRecord]]:
    """Detect patterns from residuals and deviation metrics.

    Patterns detected:
    - HIGH_VOLATILITY: if close_deviation_std > DEVIATION_HIGH_THRESHOLD
    - SPREAD_ANOMALY: if hl_spread_mean > DEVIATION_HIGH_THRESHOLD * 2
    - NONE: if no pattern detected (mandatory per spec)

    Args:
        residuals: Noise residual values.
        close_deviation_std: Close price std deviation.
        hl_spread_mean: Mean HL spread.

    Returns:
        Tuple of (patterns_detected, evidence_records).
        evidence_records always has at least 1 item.
    """
    patterns: List[str] = []
    records: List[EvidenceRecord] = []

    seg_hash = _compute_segment_hash(residuals)
    residual_indices: List[int] = list(range(len(residuals)))

    # Pattern 1: HIGH_VOLATILITY
    if close_deviation_std > DEVIATION_HIGH_THRESHOLD:
        patterns.append("HIGH_VOLATILITY")
        confidence = min(1.0, close_deviation_std / (DEVIATION_HIGH_THRESHOLD * 10))
        strength = min(1.0, close_deviation_std / (DEVIATION_HIGH_THRESHOLD * 5))
        records.append(
            EvidenceRecord(
                timestamp_utc=_TS_SENTINEL,
                pattern_name="HIGH_VOLATILITY",
                confidence_0_1=confidence,
                evidence_strength=strength,
                raw_refs=RawRefs(
                    segment_hash=seg_hash,
                    residual_indices=residual_indices,
                ),
            )
        )

    # Pattern 2: SPREAD_ANOMALY
    if hl_spread_mean > DEVIATION_HIGH_THRESHOLD * 2:
        patterns.append("SPREAD_ANOMALY")
        confidence = min(1.0, hl_spread_mean / (DEVIATION_HIGH_THRESHOLD * 20))
        strength = min(1.0, hl_spread_mean / (DEVIATION_HIGH_THRESHOLD * 10))
        records.append(
            EvidenceRecord(
                timestamp_utc=_TS_SENTINEL,
                pattern_name="SPREAD_ANOMALY",
                confidence_0_1=confidence,
                evidence_strength=strength,
                raw_refs=RawRefs(
                    segment_hash=seg_hash,
                    residual_indices=residual_indices,
                ),
            )
        )

    # If no pattern detected → emit NONE record (mandatory per spec + INV_EVIDENCE_LOG_MIN_1)
    if not records:
        records.append(
            EvidenceRecord(
                timestamp_utc=_TS_SENTINEL,
                pattern_name="NONE",
                confidence_0_1=0.0,
                evidence_strength=0.0,
                raw_refs=RawRefs(
                    segment_hash=seg_hash,
                    residual_indices=residual_indices,
                ),
            )
        )

    return patterns, records


def build_broker_audit(
    trust_score: float,
    trust_state: str,
    hl_spread_mean: float,
    close_deviation_std: float,
    volume_cv: float,
    evidence_features_data: Dict[str, object],
    patterns_detected: List[str],
    evidence_log: List[EvidenceRecord],
    last_bar_ts: str,
) -> BrokerAudit:
    """Build the full broker_audit block.

    Replaces sentinel timestamps in evidence_log with actual last bar timestamp.

    Args:
        trust_score: Computed trust score.
        trust_state: Classified trust state string.
        hl_spread_mean: Mean HL spread.
        close_deviation_std: Close std deviation.
        volume_cv: Volume CV.
        evidence_features_data: Dict with bar_count, symbol, timeframe, run_id.
        patterns_detected: List of pattern name strings.
        evidence_log: List of EvidenceRecord objects (sentinel ts will be replaced).
        last_bar_ts: ISO8601 timestamp from last bar (replaces sentinel).

    Returns:
        BrokerAudit object.
    """
    # Replace sentinel timestamps with actual last bar timestamp
    for rec in evidence_log:
        if rec.timestamp_utc == _TS_SENTINEL:
            rec.timestamp_utc = last_bar_ts

    deviation_metrics = DeviationMetrics(
        hl_spread_mean=hl_spread_mean,
        close_deviation_std=close_deviation_std,
        volume_cv=volume_cv,
    )

    evidence_features = EvidenceFeatures(
        bar_count=int(evidence_features_data["bar_count"]),
        symbol=str(evidence_features_data["symbol"]),
        timeframe=str(evidence_features_data["timeframe"]),
        run_id=str(evidence_features_data["run_id"]),
    )

    return BrokerAudit(
        trust_score=trust_score,
        trust_state=trust_state,
        deviation_metrics=deviation_metrics,
        evidence_features=evidence_features,
        patterns_detected=patterns_detected,
        evidence_log=evidence_log,
    )
