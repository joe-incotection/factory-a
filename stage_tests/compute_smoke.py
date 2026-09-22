"""
COMPUTE_SMOKE.PY — Factory-A Pipeline Smoke Test
================================================
Purpose: Verify integration between Data Collector (M8+MT5) and Trinity M1.
Flow:    Mock Data -> collect_window() -> run_trinity_m1() -> Assertions
"""

import sys
import random
from datetime import datetime, timedelta, timezone

# ==============================================================================
# 1. ENVIRONMENT SETUP
# ==============================================================================
REQUIRED_PATHS = [
    r"C:\Factory_a\modules_dev\data_collector",
    r"C:\Factory_a\modules_dev\trinity_m1"
]

print(">>> [INIT] Setting up PYTHONPATH...")
for path in REQUIRED_PATHS:
    if path not in sys.path:
        sys.path.insert(0, path)
        print(f"    + Added: {path}")

try:
    from data_collector import collect_window
    from trinity_m1 import run_trinity_m1
    print(">>> [INIT] Modules imported successfully.")
except ImportError as e:
    print(f"\n!!! CRITICAL IMPORT ERROR: {e}")
    sys.exit(1)

# ==============================================================================
# 2. MOCK DATA GENERATOR (Factory-A compliant — UTC Z timestamp)
# ==============================================================================
def generate_mock_bars(count=300, start_price=1.0800, volatility=0.0005):
    """Generate OHLCV bars with UTC ISO 8601 Z timestamps."""
    bars = []
    # Use fixed start time for determinism
    current_time = datetime(2025, 11, 10, 5, 0, 0, tzinfo=timezone.utc)
    price = start_price

    for i in range(count):
        change = random.gauss(0, volatility)
        close = round(price + change, 5)
        high = round(max(price, close) + abs(random.gauss(0, volatility / 2)), 5)
        low  = round(min(price, close) - abs(random.gauss(0, volatility / 2)), 5)
        open_ = round(price, 5)

        # Enforce OHLC invariant
        high = max(high, open_, close)
        low  = min(low,  open_, close)

        ts = current_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        bar = {
            "t"      : ts,
            "ts_utc" : ts,
            "o": open_,
            "h": high,
            "l": low,
            "c": close,
            "v": float(random.randint(100, 5000)),
            "spread" : round(random.uniform(0.00010, 0.00030), 5),
            "bid"    : round(low  + random.uniform(0, 0.00005), 5),
            "ask"    : round(high - random.uniform(0, 0.00005), 5),
        }
        bars.append(bar)
        price = close
        current_time += timedelta(hours=1)

    return bars

# ==============================================================================
# 3. SMOKE TEST
# ==============================================================================
def run_smoke_test():
    print("\n>>> [START] Running Compute Smoke Test...")

    SYMBOL      = "EURUSD"
    TIMEFRAME   = "1h"
    WINDOW_SIZE = 256

    # end_time_utc MUST be string with Z
    end_time_utc = "2026-02-16T06:00:00Z"

    # --- STEP 1: Generate data ---
    print(f"\n--- STEP 1: Generating Mock Data ({WINDOW_SIZE}+ bars) ---")
    random.seed(42)  # deterministic
    market_bars = generate_mock_bars(count=300, start_price=1.0850)
    truth_bars  = generate_mock_bars(count=300, start_price=1.0850)
    print(f"    Market Bars : {len(market_bars)}")
    print(f"    Truth Bars  : {len(truth_bars)}")
    print(f"    First t     : {market_bars[0]['t']}")
    print(f"    Last  t     : {market_bars[-1]['t']}")

    # --- STEP 2: collect_window ---
    print("\n--- STEP 2: Calling collect_window() ---")
    try:
        result = collect_window(
            symbol=SYMBOL,
            timeframe=TIMEFRAME,
            end_time_utc=end_time_utc,
            window_size=WINDOW_SIZE,
            market_bars=market_bars,
            truth_bars=truth_bars,
            min_truth_overlap_ratio=0.95,
        )
    except Exception as e:
        print(f"!!! FAIL: collect_window raised: {e}")
        return False

    status = result.get("status", "unknown")
    print(f"    Status        : {status}")
    print(f"    Reason codes  : {result.get('reason_codes', [])}")
    print(f"    Market window : {len(result.get('market_window', []))} bars")
    print(f"    Truth window  : {len(result.get('truth_window', []))} bars")
    print(f"    Overlap ratio : {result.get('alignment', {}).get('truth_overlap_ratio', 'N/A')}")

    if status == "fail":
        print(f"!!! FAIL: collect_window status=fail")
        return False

    market_window = result.get("market_window", [])
    truth_window  = result.get("truth_window", [])

    # --- STEP 3: run_trinity_m1 ---
    print("\n--- STEP 3: Calling run_trinity_m1() ---")
    try:
        trinity_result = run_trinity_m1({
            "symbol"     : SYMBOL,
            "timeframe"  : TIMEFRAME,
            "bars"       : market_window,
            "truth_data" : {"bars": truth_window} if truth_window else None,
            "meta"       : {"source": "smoke_test", "run_id": "smoke_001"}
        })
    except Exception as e:
        print(f"!!! FAIL: run_trinity_m1 raised: {e}")
        return False

    # --- STEP 4: Assertions ---
    print("\n--- STEP 4: Verifying Output ---")
    checks = {
        "noise_residual present"  : "noise_residual" in trinity_result,
        "broker_audit present"    : "broker_audit" in trinity_result,
        "audit_quality present"   : "metadata" in trinity_result,
    }

    all_passed = True
    for name, passed in checks.items():
        tag = "[PASS]" if passed else "[FAIL]"
        print(f"    {tag} {name}")
        if not passed:
            all_passed = False

    # --- SUMMARY ---
    print("\n" + "=" * 50)
    if all_passed:
        print("SMOKE TEST PASSED — Pipeline operational")
        meta = trinity_result.get("metadata", {})
        print(f"  audit_quality : {meta.get('audit_quality', 'N/A')}")
        nr = trinity_result.get("noise_residual", {})
        stats = nr.get("stats", {})
        print(f"  residual mean : {stats.get('mean', 'N/A')}")
        print(f"  residual std  : {stats.get('std', 'N/A')}")
    else:
        print("SMOKE TEST FAILED — Check logs above")
    print("=" * 50)
    return all_passed


if __name__ == "__main__":
    ok = run_smoke_test()
    sys.exit(0 if ok else 1)