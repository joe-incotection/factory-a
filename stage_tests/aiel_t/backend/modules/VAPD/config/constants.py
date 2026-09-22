"""
Configuration constants for VAPD_Signal.

These values are aligned with Python Brain Master Spec.
"""

# === Contract Version ===
CONTRACT_VERSION: str = "1.0"

# === Risk/Reward ===
DEFAULT_RR_RATIO: float = 2.0
ATR_MULTIPLIER: float = 1.5

# === Thresholds ===
VAPD_ZSCORE_ENTRY: float = 2.0  # |z| > this = signal
VAPD_ZSCORE_EXIT: float = 0.5  # |z| < this = exit
EXECUTOR_CONFIDENCE_MIN: float = 0.70  # confidence < this = reject

# === Retry Logic ===
RETRY_ATTEMPTS: int = 3
COOLDOWN_SECONDS: int = 2

# === VAPD Defaults ===
VAPD_DEFAULT_SYMBOL: str = "EURUSD"
VAPD_DEFAULT_TIMEFRAME: str = "H1"
VAPD_DEFAULT_LOOKBACK: int = 200
VAPD_DEFAULT_ATR_PERIOD: int = 14

# === GIM Integration ===
GIM_RISK_THRESHOLD: float = 1.5  # |composite_score| > this = volatile regime
