"""
TRINITY_M1 — Public API
Feature generator + audit producer for raw OHLCV bar stream.
"""
from .engine import run_trinity_m1
from .exceptions import TrinityM1Error

__all__ = ["run_trinity_m1", "TrinityM1Error"]
__version__ = "1.0.0"