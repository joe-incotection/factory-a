"""
Pytest configuration for VAPD_Signal Golden Edition.

This configuration ensures the project root is in sys.path
for proper module imports during testing.
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path for tests
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
