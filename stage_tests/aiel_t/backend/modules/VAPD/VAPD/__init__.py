"""
VAPD_Signal Golden Edition - AIEL-2 + AIEL-3 Optimized.

This module provides the Volatility-Adjusted Price Deviation (VAPD) component
for the Python Brain trading system - the core signal generation engine.
"""

from backend.modules.volatility_adjusted_price_deviation import (
    VolatilityAdjustedPriceDeviation,
)

__all__ = ["VolatilityAdjustedPriceDeviation"]
__version__ = "1.0.0"
