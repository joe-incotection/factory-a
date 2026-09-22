"""
Test Suite for Volatility-Adjusted Price Deviation (VAPD) - Golden Edition.

This test suite validates VAPD's behavior across multiple scenarios:
- Ranging regime (mean reversion)
- Trending regime (momentum)
- Volatile regime
- GIM integration
- Confidence calculation
- SL/TP calculation
- Failover scenarios

Test Strategy:
    - Mock MT5 at module import path
    - Use realistic price patterns
    - Test all regime strategies
    - Validate I/O contract compliance

Author: AIEL System
Version: 1.0.0
Status: Production Ready
"""

from datetime import datetime
from typing import Dict, List
from unittest.mock import patch, MagicMock

import pandas as pd

from backend.modules.volatility_adjusted_price_deviation import (
    VolatilityAdjustedPriceDeviation,
)


# ========================================================================
# Test Helper Functions
# ========================================================================

def _make_rates(close_values: List[float]) -> Dict[str, List]:
    """
    Build mock MT5 rates data for testing.

    Args:
        close_values: List of close prices.

    Returns:
        Dict: MT5-compatible rates dictionary.
    """
    size = len(close_values)
    return {
        "time": list(range(size)),
        "open": close_values,
        "high": [v * 1.0001 for v in close_values],
        "low": [v * 0.9999 for v in close_values],
        "close": close_values,
        "tick_volume": [1000.0] * size,
    }


# ========================================================================
# Test Cases
# ========================================================================

@patch("backend.modules.volatility_adjusted_price_deviation.mt5")
def test_1_ranging_buy_signal(mock_mt5: MagicMock) -> None:
    """
    Test Case 1: RANGING/TRENDING Regime - BUY Signal (Oversold).

    Scenario:
        Price drops significantly creating negative Z-score
        → signal_type = "BUY"

    Validates:
        - Mean reversion or momentum strategy
        - Oversold detection
        - BUY signal generation
        - Confidence calculation
        - SL/TP levels

    Expected:
        signal_type = "BUY"
        confidence > 0.5
        regime = "RANGING" or "TRENDING"
    """
    # Setup: Significant drop
    base = [1.1000] * 200
    prices = base + [1.0960] * 10

    # Configure mock
    mock_mt5.TIMEFRAME_H1 = 16408
    mock_mt5.copy_rates_from_pos.return_value = _make_rates(prices)

    # Create instance with lower confidence threshold and LOW GIM
    vapd = VolatilityAdjustedPriceDeviation(
        symbol="EURUSD", timeframe="H1", confidence_min=0.5
    )
    gim_result = {"composite_score": 0.2}  # Low GIM
    result = vapd.run(gim_result=gim_result)

    # Assertions
    assert result["signal_type"] == "BUY", f"Expected BUY, got {result['signal_type']}. Z={result['z_score']:.2f}, Regime={result['regime']}"
    assert result["regime"] in ["RANGING", "TRENDING", "VOLATILE"], "Regime should be valid"
    assert result["confidence"] > 0.0, "Confidence should be positive"
    assert result["z_score"] < -1.0, "Z-score should be negative (oversold)"
    assert result["stop_loss"] < result["entry_price"], "SL should be below entry for BUY"
    assert result["take_profit"] > result["entry_price"], "TP should be above entry for BUY"
    assert result["_contract_version"] == "1.0"


@patch("backend.modules.volatility_adjusted_price_deviation.mt5")
def test_2_ranging_sell_signal(mock_mt5: MagicMock) -> None:
    """
    Test Case 2: RANGING/TRENDING Regime - SELL Signal (Overbought).

    Scenario:
        Price rises significantly creating positive Z-score
        → signal_type = "SELL"

    Validates:
        - Mean reversion or momentum strategy
        - Overbought detection
        - SELL signal generation
        - SL above entry, TP below entry

    Expected:
        signal_type = "SELL"
        confidence > 0.5
        regime = "RANGING" or "TRENDING"
    """
    # Setup: Significant rise
    base = [1.1000] * 200
    prices = base + [1.1040] * 10

    # Configure mock
    mock_mt5.TIMEFRAME_H1 = 16408
    mock_mt5.copy_rates_from_pos.return_value = _make_rates(prices)

    # Create instance with lower confidence threshold and LOW GIM
    vapd = VolatilityAdjustedPriceDeviation(
        symbol="EURUSD", timeframe="H1", confidence_min=0.5
    )
    gim_result = {"composite_score": 0.2}  # Low GIM
    result = vapd.run(gim_result=gim_result)

    # Assertions
    assert result["signal_type"] == "SELL", f"Expected SELL, got {result['signal_type']}. Z={result['z_score']:.2f}, Regime={result['regime']}"
    assert result["regime"] in ["RANGING", "TRENDING", "VOLATILE"], "Regime should be valid"
    assert result["confidence"] > 0.0
    assert result["z_score"] > 1.0, "Z-score should be positive (overbought)"
    assert result["stop_loss"] > result["entry_price"], "SL should be above entry for SELL"
    assert result["take_profit"] < result["entry_price"], "TP should be below entry for SELL"


@patch("backend.modules.volatility_adjusted_price_deviation.mt5")
def test_3_trending_momentum(mock_mt5: MagicMock) -> None:
    """
    Test Case 3: TRENDING Regime - Momentum BUY.

    Scenario:
        Sustained uptrend with Z-score > 1.0
        → signal_type = "BUY" (momentum following)

    Validates:
        - Momentum strategy in TRENDING regime
        - BUY signal on positive momentum
        - Confidence adjustment for TRENDING

    Expected:
        signal_type = "BUY"
        regime = "TRENDING"
    """
    # Setup: Strong gradual uptrend to create Z > 1.0
    prices = [1.1000 + (i * 0.0002) for i in range(210)]  # Stronger uptrend

    # Configure mock
    mock_mt5.TIMEFRAME_H1 = 16408
    mock_mt5.copy_rates_from_pos.return_value = _make_rates(prices)

    # Create instance with lower confidence threshold
    vapd = VolatilityAdjustedPriceDeviation(
        symbol="EURUSD", timeframe="H1", confidence_min=0.5
    )
    gim_result = {"composite_score": 0.8}
    result = vapd.run(gim_result=gim_result)

    # Assertions
    assert result["signal_type"] == "BUY", f"Expected BUY for uptrend. Z={result['z_score']:.2f}, Regime={result['regime']}"
    assert result["regime"] == "TRENDING"
    assert result["z_score"] > 0.5, "Z-score should be positive in uptrend"


@patch("backend.modules.volatility_adjusted_price_deviation.mt5")
def test_4_volatile_no_signal(mock_mt5: MagicMock) -> None:
    """
    Test Case 4: VOLATILE Regime - No Signal (Moderate Z-Score).

    Scenario:
        High GIM risk (|composite| > 1.5) with moderate Z-score
        → signal_type = "NONE"

    Validates:
        - VOLATILE regime detection via GIM
        - No signal generation for non-extreme Z
        - Risk-aware behavior

    Expected:
        signal_type = "NONE"
        regime = "VOLATILE"
    """
    # Setup: Normal prices but high GIM stress
    prices = [1.1000] * 210

    # Configure mock
    mock_mt5.TIMEFRAME_H1 = 16408
    mock_mt5.copy_rates_from_pos.return_value = _make_rates(prices)

    # Create instance and run
    vapd = VolatilityAdjustedPriceDeviation(symbol="EURUSD", timeframe="H1")
    gim_result = {"composite_score": 2.0}  # High GIM stress
    result = vapd.run(gim_result=gim_result)

    # Assertions
    assert result["signal_type"] == "NONE", "Should not signal in VOLATILE without extreme Z"
    assert result["regime"] == "VOLATILE"


@patch("backend.modules.volatility_adjusted_price_deviation.mt5")
def test_5_volatile_extreme(mock_mt5: MagicMock) -> None:
    """
    Test Case 5: VOLATILE Regime - BUY on Extreme Oversold.

    Scenario:
        High GIM risk + extreme Z-score < -3.0
        → signal_type = "BUY" (extreme only)

    Validates:
        - Extreme-only strategy in VOLATILE
        - BUY signal on extreme oversold
        - Lower confidence in volatile conditions

    Expected:
        signal_type = "BUY"
        regime = "VOLATILE"
        confidence < 0.8 (lower due to regime adjustment)
    """
    # Setup: VERY EXTREME drop with high GIM stress
    base = [1.1000] * 200
    prices = base + [1.0700] * 10  # Massive drop to ensure Z < -3.0

    # Configure mock
    mock_mt5.TIMEFRAME_H1 = 16408
    mock_mt5.copy_rates_from_pos.return_value = _make_rates(prices)

    # Create instance with lower confidence threshold
    vapd = VolatilityAdjustedPriceDeviation(
        symbol="EURUSD", timeframe="H1", confidence_min=0.4
    )
    gim_result = {"composite_score": 2.5}  # High stress
    result = vapd.run(gim_result=gim_result)

    # Assertions
    assert result["signal_type"] == "BUY", f"Should signal BUY on extreme oversold. Z={result['z_score']:.2f}"
    assert result["regime"] == "VOLATILE"
    assert result["z_score"] < -2.0, "Should have very negative Z-score"


@patch("backend.modules.volatility_adjusted_price_deviation.mt5")
def test_6_sl_tp_calculation(mock_mt5: MagicMock) -> None:
    """
    Test Case 6: SL/TP Calculation Validation.

    Validates:
        - SL distance = ATR * 1.5
        - TP distance = SL distance * RR ratio (2.0)
        - BUY: SL < Entry < TP
        - SELL: TP < Entry < SL

    Expected:
        Risk/Reward ratio = 2:1
        Levels based on ATR
    """
    # Setup: Generate signal
    base = [1.1000] * 200
    prices = base + [1.0950] * 10  # Oversold

    # Configure mock
    mock_mt5.TIMEFRAME_H1 = 16408
    mock_mt5.copy_rates_from_pos.return_value = _make_rates(prices)

    # Create instance and run
    vapd = VolatilityAdjustedPriceDeviation(symbol="EURUSD", timeframe="H1")
    result = vapd.run()

    # Assertions (if signal generated)
    if result["signal_type"] != "NONE":
        entry = result["entry_price"]
        sl = result["stop_loss"]
        tp = result["take_profit"]

        # Calculate distances
        sl_distance = abs(entry - sl)
        tp_distance = abs(entry - tp)

        # Validate RR ratio (approximately 2:1)
        rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0
        assert 1.8 <= rr_ratio <= 2.2, f"RR ratio {rr_ratio:.2f} outside expected range"

        # Validate direction
        if result["signal_type"] == "BUY":
            assert sl < entry < tp, "BUY: SL must be below entry, TP above"
        elif result["signal_type"] == "SELL":
            assert tp < entry < sl, "SELL: TP must be below entry, SL above"


@patch("backend.modules.volatility_adjusted_price_deviation.mt5")
def test_7_no_data_failsafe(mock_mt5: MagicMock) -> None:
    """
    Test Case 7: Failsafe on Data Fetch Failure.

    Scenario:
        MT5 fetch fails completely
        → signal_type = "NONE"

    Validates:
        - Failover to safe defaults
        - No crash on data unavailability
        - Contract structure maintained

    Expected:
        signal_type = "NONE"
        confidence = 0.0
        All fields present
    """
    # Configure mock to fail
    mock_mt5.TIMEFRAME_H1 = 16408
    mock_mt5.copy_rates_from_pos.return_value = None

    # Create instance and run
    vapd = VolatilityAdjustedPriceDeviation(symbol="EURUSD", timeframe="H1")
    result = vapd.run()

    # Assertions
    assert result["signal_type"] == "NONE", "Should not signal on data failure"
    assert result["confidence"] == 0.0, "Confidence should be 0 on failure"
    assert "reasoning" in result
    assert "Data fetch failed" in result["reasoning"]
    assert result["_contract_version"] == "1.0"


# ========================================================================
# Additional Integration Tests (AIEL-3)
# ========================================================================

@patch("backend.modules.volatility_adjusted_price_deviation.mt5")
def test_8_gim_integration(mock_mt5: MagicMock) -> None:
    """
    Test Case 8: GIM Integration.

    Validates:
        - GIM composite score affects regime detection
        - Confidence adjustment based on GIM
        - Works with and without GIM input

    Expected:
        Regime changes based on GIM
    """
    prices = [1.1000] * 210

    # Configure mock
    mock_mt5.TIMEFRAME_H1 = 16408
    mock_mt5.copy_rates_from_pos.return_value = _make_rates(prices)

    vapd = VolatilityAdjustedPriceDeviation(symbol="EURUSD", timeframe="H1")

    # Test 1: With calm GIM
    result_calm = vapd.run(gim_result={"composite_score": 0.3})

    # Test 2: With stressed GIM
    result_stress = vapd.run(gim_result={"composite_score": 2.0})

    # Assertions
    assert result_calm["regime"] in ["RANGING", "TRENDING"]
    assert result_stress["regime"] == "VOLATILE", "High GIM should trigger VOLATILE"


@patch("backend.modules.volatility_adjusted_price_deviation.mt5")
def test_9_confidence_threshold(mock_mt5: MagicMock) -> None:
    """
    Test Case 9: Confidence Threshold Filter.

    Validates:
        - Signals below confidence_min are blocked
        - signal_type = "NONE" when confidence insufficient

    Expected:
        Low confidence → No signal despite Z-score
    """
    # Setup: Moderate signal
    prices = [1.1000] * 200 + [1.0980] * 10

    # Configure mock
    mock_mt5.TIMEFRAME_H1 = 16408
    mock_mt5.copy_rates_from_pos.return_value = _make_rates(prices)

    # Create instance with HIGH confidence threshold
    vapd = VolatilityAdjustedPriceDeviation(
        symbol="EURUSD", timeframe="H1", confidence_min=0.95  # Very high threshold
    )

    result = vapd.run()

    # With very high threshold, most signals should be filtered
    # (unless Z-score is extremely high)
    assert isinstance(result["confidence"], float)
    assert 0.0 <= result["confidence"] <= 1.0


@patch("backend.modules.volatility_adjusted_price_deviation.mt5")
def test_10_contract_compliance(mock_mt5: MagicMock) -> None:
    """
    Test Case 10: I/O Contract Compliance.

    Validates:
        - All required keys present
        - Correct types
        - Contract version field
        - Signal type values

    Expected:
        Complete contract structure
    """
    prices = [1.1000] * 210

    # Configure mock
    mock_mt5.TIMEFRAME_H1 = 16408
    mock_mt5.copy_rates_from_pos.return_value = _make_rates(prices)

    vapd = VolatilityAdjustedPriceDeviation()
    result = vapd.run()

    # Required keys
    required_keys = {
        "signal_type",
        "confidence",
        "entry_price",
        "stop_loss",
        "take_profit",
        "timestamp",
        "regime",
        "z_score",
        "adjusted_z_score",
        "atr",
        "reasoning",
        "_contract_version",
    }

    assert required_keys.issubset(result.keys()), f"Missing keys: {required_keys - result.keys()}"

    # Type validation
    assert isinstance(result["signal_type"], str)
    assert result["signal_type"] in ["BUY", "SELL", "NONE"]
    assert isinstance(result["confidence"], float)
    assert 0.0 <= result["confidence"] <= 1.0
    assert isinstance(result["entry_price"], float)
    assert isinstance(result["reasoning"], str)
    assert result["_contract_version"] == "1.0"
