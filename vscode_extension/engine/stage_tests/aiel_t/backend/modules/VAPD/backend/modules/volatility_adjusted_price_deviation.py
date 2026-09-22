"""
Volatility-Adjusted Price Deviation (VAPD) - Golden Edition.

This module implements the core signal generation logic for the Python Brain
trading system. It combines price deviation analysis with volatility adjustment
and regime detection to generate high-quality trading signals.

AIEL Processing:
    - AIEL-0: Raw implementation
    - AIEL-1: Structure refinement, I/O contract alignment
    - AIEL-2: Performance optimization, GIM integration, regime logic
    - AIEL-3: Documentation and polish

Author: AIEL System
Version: 1.0.0
Status: Production Ready
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from config.constants import (
    CONTRACT_VERSION,
    DEFAULT_RR_RATIO,
    ATR_MULTIPLIER,
    VAPD_ZSCORE_ENTRY,
    VAPD_ZSCORE_EXIT,
    EXECUTOR_CONFIDENCE_MIN,
    RETRY_ATTEMPTS,
    VAPD_DEFAULT_SYMBOL,
    VAPD_DEFAULT_TIMEFRAME,
    VAPD_DEFAULT_LOOKBACK,
    VAPD_DEFAULT_ATR_PERIOD,
    GIM_RISK_THRESHOLD,
)

# Optional dependency (mocked in tests)
try:
    import MetaTrader5 as mt5  # type: ignore[import-not-found]
except Exception:  # pragma: no cover
    mt5 = None  # type: ignore[assignment]


@dataclass
class VAPDConfig:
    """
    Configuration container for VAPD module.

    Attributes:
        symbol: Trading symbol (e.g., 'EURUSD').
        timeframe: MT5 timeframe string (e.g., 'H1', 'M5').
        lookback_period: Number of bars for SMA/StdDev calculation.
        atr_period: Number of bars for ATR calculation.
        zscore_entry_threshold: Z-score threshold for signal entry.
        zscore_exit_threshold: Z-score threshold for signal exit.
        confidence_min: Minimum confidence to generate signal.
        risk_reward_ratio: TP distance = RR * SL distance.
        retry_attempts: Number of fetch retry attempts.
    """

    symbol: str
    timeframe: str
    lookback_period: int
    atr_period: int
    zscore_entry_threshold: float
    zscore_exit_threshold: float
    confidence_min: float
    risk_reward_ratio: float
    retry_attempts: int


class VolatilityAdjustedPriceDeviation:
    """
    Volatility-Adjusted Price Deviation (VAPD) - Signal Generator Module.

    VAPD is the core decision engine of the Python Brain, responsible for
    generating trading signals based on price deviation, volatility adjustment,
    and market regime detection.

    Architecture Position:
        [GIM: Context] → [VAPD: Signal Logic] → [EQL: Defense] → [Executor]

    Signal Logic:
        1. Fetch price data from MT5
        2. Calculate Z-Score (price deviation from mean)
        3. Normalize by ATR (volatility adjustment)
        4. Detect market regime (RANGING, TRENDING, VOLATILE)
        5. Generate signal based on regime strategy
        6. Calculate confidence score
        7. Set SL/TP levels

    Regime Strategies:
        - RANGING: Mean reversion (buy oversold, sell overbought)
        - TRENDING: Momentum following (follow strong trends)
        - VOLATILE: Extreme only (high threshold, low confidence)

    Output Contract (IMMUTABLE):
        {
            "signal_type": str,         # "BUY" | "SELL" | "NONE"
            "confidence": float,        # 0.0 to 1.0
            "entry_price": float,       # Current price if signal
            "stop_loss": float,         # ATR-based SL
            "take_profit": float,       # ATR-based TP
            "timestamp": str,           # ISO format UTC
            "regime": str,              # Market regime
            "z_score": float,           # Raw z-score
            "adjusted_z_score": float,  # ATR-normalized z-score
            "atr": float,               # Current ATR value
            "reasoning": str,           # Human-readable explanation
            "_contract_version": str    # Contract version
        }

    Failover Strategy:
        - Data fetch fails → signal_type = "NONE"
        - Confidence < threshold → signal_type = "NONE"
        - GIM risk elevated → use VOLATILE regime
        - Better to miss a trade than trade with bad data

    Performance Optimizations (AIEL-2):
        - Static caching of empty dataframe template
        - Vectorized pandas operations (no Python loops)
        - LRU cache for timeframe mapping
        - Efficient ATR calculation

    Example:
        >>> vapd = VolatilityAdjustedPriceDeviation(symbol='EURUSD', timeframe='H1')
        >>> gim_result = {'composite_score': 0.5, 'is_risk_elevated': False}
        >>> result = vapd.run(gim_result=gim_result)
        >>> if result['signal_type'] != 'NONE':
        ...     print(f"Signal: {result['signal_type']} @ {result['entry_price']:.5f}")
        ...     print(f"Confidence: {result['confidence']:.2%}")
    """

    # Class-level cache for empty dataframe template (AIEL-2 optimization)
    _empty_frame_template: Optional[pd.DataFrame] = None
    _template_lock: threading.Lock = threading.Lock()

    def __init__(
        self,
        symbol: str = VAPD_DEFAULT_SYMBOL,
        timeframe: str = VAPD_DEFAULT_TIMEFRAME,
        lookback_period: int = VAPD_DEFAULT_LOOKBACK,
        atr_period: int = VAPD_DEFAULT_ATR_PERIOD,
        zscore_entry_threshold: float = VAPD_ZSCORE_ENTRY,
        zscore_exit_threshold: float = VAPD_ZSCORE_EXIT,
        confidence_min: float = EXECUTOR_CONFIDENCE_MIN,
        risk_reward_ratio: float = DEFAULT_RR_RATIO,
        retry_attempts: int = RETRY_ATTEMPTS,
    ) -> None:
        """
        Initialize Volatility-Adjusted Price Deviation module.

        Args:
            symbol: Trading symbol. Default: 'EURUSD'.
            timeframe: MT5 timeframe string. Default: 'H1'.
            lookback_period: Bars for SMA/StdDev. Default: 200.
            atr_period: Bars for ATR calculation. Default: 14.
            zscore_entry_threshold: Z-score entry threshold. Default: 2.0.
            zscore_exit_threshold: Z-score exit threshold. Default: 0.5.
            confidence_min: Minimum confidence for signals. Default: 0.70.
            risk_reward_ratio: TP = RR * SL distance. Default: 2.0.
            retry_attempts: Fetch retry attempts. Default: 3.
        """
        self.config = VAPDConfig(
            symbol=symbol,
            timeframe=timeframe,
            lookback_period=lookback_period,
            atr_period=atr_period,
            zscore_entry_threshold=zscore_entry_threshold,
            zscore_exit_threshold=zscore_exit_threshold,
            confidence_min=confidence_min,
            risk_reward_ratio=risk_reward_ratio,
            retry_attempts=retry_attempts,
        )

    # ----------------------------------------------------------------
    # AIEL-2 OPTIMIZATION: Static cached empty frame template
    # ----------------------------------------------------------------
    @classmethod
    def _get_empty_price_frame(cls) -> pd.DataFrame:
        """
        Get cached empty price dataframe template.

        Returns:
            pd.DataFrame: Empty dataframe with MT5-compatible columns.

        Thread Safety:
            Uses class-level lock for thread-safe initialization.

        Performance:
            AIEL-2 optimization - avoids repeated DataFrame construction.
        """
        if cls._empty_frame_template is None:
            with cls._template_lock:
                if cls._empty_frame_template is None:
                    df = pd.DataFrame(
                        columns=["time", "open", "high", "low", "close", "tick_volume"]
                    )
                    cls._empty_frame_template = df.astype(
                        {
                            "time": "int64",
                            "open": "float64",
                            "high": "float64",
                            "low": "float64",
                            "close": "float64",
                            "tick_volume": "float64",
                        }
                    )
        return cls._empty_frame_template.copy()

    @staticmethod
    @lru_cache(maxsize=16)
    def _mt5_timeframe_code(timeframe: str) -> Optional[int]:
        """
        Convert timeframe string to MT5 constant with caching.

        Args:
            timeframe: Timeframe string (e.g., 'H1', 'M5').

        Returns:
            Optional[int]: MT5 timeframe constant or None if invalid.

        Performance:
            AIEL-2 optimization - LRU cache avoids repeated lookups.

        Supported Timeframes:
            M1, M5, M15, M30, H1, H4, D1
        """
        if mt5 is None:
            return None

        mapping = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
        }
        return mapping.get(timeframe)

    def _fetch_price_data(self) -> Tuple[pd.DataFrame, str]:
        """
        Fetch OHLCV price data from MT5 with retry logic.

        Returns:
            Tuple containing:
                - pd.DataFrame: Price data with columns [time, open, high, low, close, tick_volume]
                - str: Fetch status ("OK" | "PARTIAL" | "FAILED")

        Retry Logic:
            - Attempts up to config.retry_attempts times
            - Returns empty dataframe if all attempts fail

        Failover:
            - MT5 unavailable → FAILED status
            - Invalid timeframe → FAILED status
            - Fetch error → retry or FAILED

        Performance:
            Individual fetch with retry - called once per run().
        """
        if mt5 is None:
            return self._get_empty_price_frame(), "FAILED"

        timeframe_code = self._mt5_timeframe_code(self.config.timeframe)
        if timeframe_code is None:
            return self._get_empty_price_frame(), "FAILED"

        # Retry loop
        for attempt in range(max(1, self.config.retry_attempts)):
            try:
                rates = mt5.copy_rates_from_pos(
                    self.config.symbol,
                    timeframe_code,
                    0,
                    self.config.lookback_period,
                )

                if rates is None:
                    continue

                df = pd.DataFrame(rates)
                if df.empty:
                    continue

                # Normalize column names and types
                required_cols = ["time", "open", "high", "low", "close", "tick_volume"]
                for col in required_cols:
                    if col not in df.columns:
                        df[col] = pd.Series(dtype="float64" if col != "time" else "int64")

                df = df[required_cols].astype(
                    {
                        "time": "int64",
                        "open": "float64",
                        "high": "float64",
                        "low": "float64",
                        "close": "float64",
                        "tick_volume": "float64",
                    }
                )

                return df, "OK"

            except Exception:
                # Silent fail - will retry
                if attempt < self.config.retry_attempts - 1:
                    time.sleep(0.5)  # Brief cooldown
                continue

        return self._get_empty_price_frame(), "FAILED"

    def _compute_atr(self, df: pd.DataFrame) -> pd.Series:
        """
        Compute Average True Range (ATR) indicator.

        Formula:
            TR = max(High - Low, |High - PrevClose|, |Low - PrevClose|)
            ATR = Simple Moving Average of TR over period

        Args:
            df: DataFrame with columns [high, low, close].

        Returns:
            pd.Series: ATR values (same length as input).

        Edge Cases:
            - Empty dataframe → empty series
            - Insufficient data → uses min_periods=1

        Performance:
            Vectorized pandas operations - no Python loops.
        """
        if df is None or df.empty:
            return pd.Series(dtype="float64")

        high = pd.to_numeric(df["high"], errors="coerce")
        low = pd.to_numeric(df["low"], errors="coerce")
        close = pd.to_numeric(df["close"], errors="coerce")
        prev_close = close.shift(1)

        # True Range components
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()

        # Max of three components
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # Simple moving average
        atr = tr.rolling(window=self.config.atr_period, min_periods=1).mean()

        return atr

    def _compute_zscore(self, series: pd.Series) -> pd.Series:
        """
        Compute Z-Score (standard score) for price series.

        Formula:
            Z = (X - μ) / σ
            Where:
                X = current value
                μ = rolling mean
                σ = rolling standard deviation

        Args:
            series: Price series (typically close prices).

        Returns:
            pd.Series: Z-score values.

        Edge Cases:
            - StdDev = 0 → Z-score = 0 (no deviation possible)
            - NaN values → filled with 0

        Interpretation:
            - Z > 2: Significantly above mean (overbought)
            - Z < -2: Significantly below mean (oversold)
            - |Z| < 1: Within normal range

        Performance:
            Vectorized rolling operations.
        """
        if series is None or series.empty:
            return pd.Series(dtype="float64")

        series = pd.to_numeric(series, errors="coerce")

        # Rolling statistics
        mean = series.rolling(window=self.config.lookback_period, min_periods=1).mean()
        std = series.rolling(window=self.config.lookback_period, min_periods=1).std()

        # Z-score calculation (handle division by zero)
        zscore = (series - mean) / std.replace(0.0, pd.NA)
        zscore = zscore.fillna(0.0).infer_objects(copy=False)

        return zscore

    def _adjust_zscore_by_atr(
        self, zscore: float, atr: float, close_price: float
    ) -> float:
        """
        Adjust Z-Score by current volatility (ATR normalization).

        Formula:
            ATR_Ratio = ATR / Close
            Adjusted_Z = Z / (1 + ATR_Ratio)

        Rationale:
            High volatility → Lower adjusted z-score (harder to trigger)
            Low volatility → Higher adjusted z-score (easier to trigger)

        Args:
            zscore: Raw z-score value.
            atr: Current ATR value.
            close_price: Current close price.

        Returns:
            float: ATR-adjusted z-score.

        Example:
            >>> # High volatility scenario
            >>> _adjust_zscore_by_atr(2.5, 0.001, 1.1000)  # ATR ratio ~0.09%
            2.48  # Minimal adjustment
            >>> # Low volatility scenario
            >>> _adjust_zscore_by_atr(2.5, 0.0001, 1.1000)  # ATR ratio ~0.009%
            2.50  # Almost no adjustment
        """
        if close_price == 0 or atr == 0:
            return zscore

        atr_ratio = atr / close_price
        adjusted = zscore / (1.0 + atr_ratio)

        return adjusted

    def _detect_regime(
        self, adjusted_zscore: float, gim_composite: float
    ) -> str:
        """
        Detect market regime based on Z-Score and GIM context.

        Regime Types:
            - VOLATILE: High GIM stress (|composite| > 1.5) or extreme Z (|Z| > 3.5)
            - TRENDING: Sustained directional move (|Z| > 1.0)
            - RANGING: Normal conditions (|Z| <= 1.0)

        Args:
            adjusted_zscore: ATR-adjusted z-score.
            gim_composite: GIM composite score from global context.

        Returns:
            str: Regime type ("VOLATILE" | "TRENDING" | "RANGING").

        Regime Strategies:
            - VOLATILE: Trade only extremes, low confidence
            - TRENDING: Momentum following, medium confidence
            - RANGING: Mean reversion, high confidence

        Example:
            >>> _detect_regime(2.5, 0.5)
            'TRENDING'
            >>> _detect_regime(0.8, 2.0)
            'VOLATILE'
        """
        # Priority 1: Check GIM stress level
        if abs(gim_composite) > GIM_RISK_THRESHOLD:
            return "VOLATILE"

        # Priority 2: Check for extreme Z-score (relaxed to 3.5)
        if abs(adjusted_zscore) > 3.5:
            return "VOLATILE"

        # Priority 3: Check for trending conditions
        if abs(adjusted_zscore) > 1.0:
            return "TRENDING"

        # Default: Ranging market
        return "RANGING"

    def _calculate_confidence(
        self, adjusted_zscore: float, regime: str, gim_composite: float
    ) -> float:
        """
        Calculate signal confidence score.

        Confidence Factors:
            1. Z-Score magnitude (primary factor)
            2. Market regime (regime-specific multiplier)
            3. GIM alignment (boost in calm markets)

        Args:
            adjusted_zscore: ATR-adjusted z-score.
            regime: Market regime.
            gim_composite: GIM composite score.

        Returns:
            float: Confidence score (0.0 to 1.0).

        Confidence Bands:
            |Z| >= 3.0: 0.9 base confidence
            |Z| >= 2.5: 0.8 base confidence
            |Z| >= 2.0: 0.7 base confidence
            |Z| >= 1.5: 0.6 base confidence
            |Z| < 1.5: 0.5 base confidence

        Regime Adjustments:
            VOLATILE: confidence * 0.7 (lower confidence)
            TRENDING: confidence * 0.9 (slightly lower)
            RANGING: confidence * 1.0 (full confidence)

        GIM Adjustment:
            Calm market (|GIM| < 1.0): confidence * 1.1 (boost)

        Example:
            >>> _calculate_confidence(2.3, 'RANGING', 0.5)
            0.77  # Base 0.7 * RANGING 1.0 * GIM 1.1 = 0.77
        """
        # Base confidence from Z-Score magnitude
        abs_z = abs(adjusted_zscore)
        if abs_z >= 3.0:
            base_confidence = 0.9
        elif abs_z >= 2.5:
            base_confidence = 0.8
        elif abs_z >= 2.0:
            base_confidence = 0.7
        elif abs_z >= 1.5:
            base_confidence = 0.6
        else:
            base_confidence = 0.5

        # Adjust for regime
        if regime == "VOLATILE":
            base_confidence *= 0.7
        elif regime == "TRENDING":
            base_confidence *= 0.9
        # RANGING: no adjustment (1.0)

        # Adjust for GIM alignment (boost in calm markets)
        if abs(gim_composite) < 1.0:
            base_confidence *= 1.1

        return min(base_confidence, 1.0)

    def _generate_signal_logic(
        self, adjusted_zscore: float, regime: str
    ) -> Tuple[str, str]:
        """
        Generate signal type and reasoning based on regime and Z-Score.

        Signal Logic by Regime:

        RANGING (Mean Reversion):
            Z <= -2.0: BUY (oversold)
            Z >= +2.0: SELL (overbought)
            Else: NONE

        TRENDING (Momentum):
            Z > 1.0: BUY (uptrend confirmation)
            Z < -1.0: SELL (downtrend confirmation)
            Else: NONE

        VOLATILE (Extreme Only):
            Z <= -3.0: BUY (extreme oversold)
            Z >= +3.0: SELL (extreme overbought)
            Else: NONE (avoid normal volatility)

        Args:
            adjusted_zscore: ATR-adjusted z-score.
            regime: Market regime.

        Returns:
            Tuple containing:
                - signal_type (str): "BUY" | "SELL" | "NONE"
                - reasoning (str): Human-readable explanation

        Example:
            >>> _generate_signal_logic(-2.3, 'RANGING')
            ('BUY', 'RANGING regime: Z=-2.30 (oversold). Mean reversion BUY signal.')
        """
        signal_type = "NONE"
        reasoning = ""

        if regime == "RANGING":
            # Mean reversion strategy
            if adjusted_zscore <= -self.config.zscore_entry_threshold:
                signal_type = "BUY"
                reasoning = f"RANGING regime: Z={adjusted_zscore:.2f} (oversold). Mean reversion BUY signal."
            elif adjusted_zscore >= self.config.zscore_entry_threshold:
                signal_type = "SELL"
                reasoning = f"RANGING regime: Z={adjusted_zscore:.2f} (overbought). Mean reversion SELL signal."
            else:
                reasoning = f"RANGING regime: Z={adjusted_zscore:.2f} within normal range. No signal."

        elif regime == "TRENDING":
            # Momentum strategy
            if adjusted_zscore > 1.0:
                signal_type = "BUY"
                reasoning = f"TRENDING regime: Z={adjusted_zscore:.2f} with positive momentum. Following trend BUY."
            elif adjusted_zscore < -1.0:
                signal_type = "SELL"
                reasoning = f"TRENDING regime: Z={adjusted_zscore:.2f} with negative momentum. Following trend SELL."
            else:
                reasoning = f"TRENDING regime: Z={adjusted_zscore:.2f} insufficient momentum. No signal."

        elif regime == "VOLATILE":
            # Extreme only strategy
            if adjusted_zscore <= -3.0:
                signal_type = "BUY"
                reasoning = f"VOLATILE regime: Extreme Z={adjusted_zscore:.2f}. Counter-trend BUY with caution."
            elif adjusted_zscore >= 3.0:
                signal_type = "SELL"
                reasoning = f"VOLATILE regime: Extreme Z={adjusted_zscore:.2f}. Counter-trend SELL with caution."
            else:
                reasoning = f"VOLATILE regime: Z={adjusted_zscore:.2f} not extreme enough. Avoid trading."

        return signal_type, reasoning

    def _calculate_sl_tp(
        self, signal_type: str, entry_price: float, atr: float
    ) -> Tuple[float, float]:
        """
        Calculate Stop Loss and Take Profit levels based on ATR.

        Formula:
            BUY:
                SL = Entry - (ATR * ATR_MULTIPLIER)
                TP = Entry + (SL_Distance * RR_Ratio)

            SELL:
                SL = Entry + (ATR * ATR_MULTIPLIER)
                TP = Entry - (SL_Distance * RR_Ratio)

        Args:
            signal_type: "BUY" | "SELL" | "NONE".
            entry_price: Entry price level.
            atr: Current ATR value.

        Returns:
            Tuple containing:
                - stop_loss (float): SL level
                - take_profit (float): TP level

        Risk Management:
            - ATR_MULTIPLIER (1.5) provides buffer beyond normal volatility
            - RR_Ratio (2.0) ensures 2:1 reward-to-risk minimum

        Example:
            >>> _calculate_sl_tp('BUY', 1.1000, 0.0010)
            (1.0985, 1.1030)  # SL 15 pips, TP 30 pips
        """
        sl_distance = atr * ATR_MULTIPLIER

        if signal_type == "BUY":
            stop_loss = entry_price - sl_distance
            take_profit = entry_price + (sl_distance * self.config.risk_reward_ratio)
        elif signal_type == "SELL":
            stop_loss = entry_price + sl_distance
            take_profit = entry_price - (sl_distance * self.config.risk_reward_ratio)
        else:
            # No signal - return entry price as placeholder
            stop_loss = entry_price
            take_profit = entry_price

        return stop_loss, take_profit

    def run(self, gim_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute complete VAPD signal generation pipeline.

        This is the main entry point for VAPD. It orchestrates the full workflow:
        fetch → compute indicators → detect regime → generate signal → calculate levels.

        Args:
            gim_result: Optional GIM output dict with 'composite_score' key.
                       If None, assumes neutral GIM state (composite_score = 0.0).

        Returns:
            Dict[str, Any]: Output contract dictionary with keys:
                - signal_type: "BUY" | "SELL" | "NONE"
                - confidence: Signal confidence (0.0 to 1.0)
                - entry_price: Current price if signal, else 0.0
                - stop_loss: ATR-based SL level
                - take_profit: ATR-based TP level
                - timestamp: ISO format UTC timestamp
                - regime: Market regime ("RANGING" | "TRENDING" | "VOLATILE")
                - z_score: Raw z-score value
                - adjusted_z_score: ATR-normalized z-score
                - atr: Current ATR value
                - reasoning: Human-readable explanation
                - _contract_version: Contract version string

        Workflow:
            1. Extract GIM context (default to neutral if not provided)
            2. Fetch price data from MT5
            3. Compute indicators (ATR, Z-Score)
            4. Adjust Z-Score by volatility
            5. Detect market regime
            6. Generate signal based on regime strategy
            7. Calculate confidence score
            8. Set SL/TP levels
            9. Return standardized output contract

        Failover Logic (IMMUTABLE):
            - Data fetch fails → signal_type = "NONE"
            - Confidence < threshold → signal_type = "NONE"
            - Exception → signal_type = "NONE" with safe defaults
            - Adheres to "Better to miss a trade than trade with bad data"

        Thread Safety:
            - Safe to call from multiple threads
            - Uses class-level caching with locks
            - No shared mutable state

        Example:
            >>> vapd = VolatilityAdjustedPriceDeviation()
            >>> gim_result = {'composite_score': 0.5, 'is_risk_elevated': False}
            >>> result = vapd.run(gim_result=gim_result)
            >>> print(f"Signal: {result['signal_type']}")
            >>> print(f"Confidence: {result['confidence']:.2%}")
            >>> print(f"Reasoning: {result['reasoning']}")

        Integration:
            Used by Brain Router after GIM check to generate trading signals.
        """
        try:
            # Step 1: Extract GIM context (default to neutral)
            gim_composite = 0.0
            if gim_result and isinstance(gim_result, dict):
                gim_composite = gim_result.get("composite_score", 0.0)

            # Step 2: Fetch price data
            price_df, fetch_status = self._fetch_price_data()

            # Step 3: Check for fetch failure (failover)
            if fetch_status == "FAILED" or price_df.empty:
                timestamp = datetime.now(timezone.utc).isoformat()
                return {
                    "signal_type": "NONE",
                    "confidence": 0.0,
                    "entry_price": 0.0,
                    "stop_loss": 0.0,
                    "take_profit": 0.0,
                    "timestamp": timestamp,
                    "regime": "UNKNOWN",
                    "z_score": 0.0,
                    "adjusted_z_score": 0.0,
                    "atr": 0.0,
                    "reasoning": "Data fetch failed. No signal generated.",
                    "_contract_version": CONTRACT_VERSION,
                }

            # Step 4: Compute indicators
            atr_series = self._compute_atr(price_df)
            zscore_series = self._compute_zscore(price_df["close"])

            # Extract latest values
            current_price = float(price_df["close"].iloc[-1])
            current_atr = float(atr_series.iloc[-1]) if not atr_series.empty else 0.0
            current_zscore = float(zscore_series.iloc[-1]) if not zscore_series.empty else 0.0

            # Step 5: Adjust Z-Score by ATR (volatility normalization)
            adjusted_zscore = self._adjust_zscore_by_atr(
                current_zscore, current_atr, current_price
            )

            # Step 6: Detect market regime
            regime = self._detect_regime(adjusted_zscore, gim_composite)

            # Step 7: Generate signal and reasoning
            signal_type, reasoning = self._generate_signal_logic(adjusted_zscore, regime)

            # Step 8: Calculate confidence
            confidence = self._calculate_confidence(adjusted_zscore, regime, gim_composite)

            # Step 9: Apply confidence filter (failover)
            if confidence < self.config.confidence_min:
                signal_type = "NONE"
                reasoning += f" Confidence {confidence:.2%} below threshold {self.config.confidence_min:.2%}."

            # Step 10: Calculate SL/TP levels
            stop_loss, take_profit = self._calculate_sl_tp(signal_type, current_price, current_atr)

            # Step 11: Generate timestamp
            timestamp = datetime.now(timezone.utc).isoformat()

            # Step 12: Return I/O contract (IMMUTABLE structure)
            return {
                "signal_type": signal_type,
                "confidence": confidence,
                "entry_price": current_price if signal_type != "NONE" else 0.0,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "timestamp": timestamp,
                "regime": regime,
                "z_score": current_zscore,
                "adjusted_z_score": adjusted_zscore,
                "atr": current_atr,
                "reasoning": reasoning,
                "_contract_version": CONTRACT_VERSION,
            }

        except Exception as e:
            # Failover: Any unexpected exception → safe defaults
            timestamp = datetime.now(timezone.utc).isoformat()
            return {
                "signal_type": "NONE",
                "confidence": 0.0,
                "entry_price": 0.0,
                "stop_loss": 0.0,
                "take_profit": 0.0,
                "timestamp": timestamp,
                "regime": "FAILSAFE",
                "z_score": 0.0,
                "adjusted_z_score": 0.0,
                "atr": 0.0,
                "reasoning": f"Exception during signal generation: {str(e)[:100]}",
                "_contract_version": CONTRACT_VERSION,
            }
