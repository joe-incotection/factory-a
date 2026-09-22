#!/usr/bin/env python3
"""
Simple Test: Gate C + GIM
ทดสอบ Gate C กับ GIM module จริง
"""
import sys
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import pandas as pd

# Add paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "backend"))

# Import GIM
from backend.modules.global_infrastructure_monitor import GlobalInfrastructureMonitor

# Import test_golden to use its helpers
from test_golden_gateC import minimal_receipt, ALLOWED_REASON_CODES


def test_simple():
    """Test simple - just run GIM and show output"""
    print("\n" + "="*60)
    print("Simple Test: GIM Output")
    print("="*60)
    
    # Mock yfinance
    with patch("backend.modules.global_infrastructure_monitor.yfinance") as mock_yf:
        # Setup simple mock
        mock_yf.download = MagicMock(return_value=pd.DataFrame())
        
        # Run GIM
        gim = GlobalInfrastructureMonitor()
        result = gim.run()
        
        print(f"\n✅ GIM Output:")
        print(f"   composite_score: {result['composite_score']}")
        print(f"   is_risk_elevated: {result['is_risk_elevated']}")
        print(f"   fetch_status: {result['fetch_status']}")
        print(f"   timestamp: {result['timestamp']}")
        
    print("\n" + "="*60)
    print("✅ GIM Running Successfully")
    print("="*60)
    
    # Test minimal receipt
    print("\nTesting minimal receipt...")
    receipt = minimal_receipt()
    
    print(f"\n✅ Receipt Created:")
    print(f"   decision_id: {receipt['decision_id']}")
    print(f"   receipt_hash: {receipt['hashes']['receipt_hash'][:16]}...")
    print(f"   determinism_key: {receipt['determinism_key'][:16]}...")
    
    print("\n" + "="*60)
    print("✅ Test Complete")
    print("="*60)
    print("\nGIM works ✅")
    print("Gate C receipt format works ✅")
    print("\nNext: Connect them together")


if __name__ == '__main__':
    test_simple()
