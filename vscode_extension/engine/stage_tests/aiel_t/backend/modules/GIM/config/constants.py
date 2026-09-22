"""
Configuration constants for GIM_Monitor.

These values are aligned with Python Brain Master Spec Section 9.
"""

# === Thresholds ===
GIM_RISK_THRESHOLD: float = 1.5  # |composite_score| > this = risk
EQL_DELTA_THRESHOLD: float = 0.00030  # |delta| > this = anomaly
VAPD_ZSCORE_ENTRY: float = 2.0  # |z| > this = signal
EXECUTOR_CONFIDENCE_MIN: float = 0.70  # confidence < this = reject

# === Timeouts ===
MT5_TIMEOUT_SECONDS: int = 30
YF_TIMEOUT_SECONDS: int = 60
RETRY_ATTEMPTS: int = 3
COOLDOWN_SECONDS: int = 2

# === Risk/Reward ===
DEFAULT_RR_RATIO: float = 2.0
ATR_MULTIPLIER: float = 1.5

# === Contract Version ===
CONTRACT_VERSION: str = "1.0"

# === GIM Specific ===
GIM_DEFAULT_LOOKBACK_DAYS: int = 200
GIM_DEFAULT_INTERVAL: str = "1d"
GIM_DEFAULT_SYMBOLS: list = ["^VIX", "^TNX", "CL=F", "GC=F"]

# === Composite Score Weights ===
GIM_WEIGHTS: dict = {
    "VIX": 0.4,
    "TNX": 0.3,
    "OIL": 0.15,
    "GOLD": 0.15,
}
