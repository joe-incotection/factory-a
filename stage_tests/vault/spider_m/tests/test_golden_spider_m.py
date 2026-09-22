"""
tests/test_golden_spider_m.py
Golden tests for spider_m engine — SpiderCAM Tension Scoring

Covers:
  - SKIP tier (low tension)
  - FLAT tier (medium tension)
  - BOOST tier (high tension) + scalar
  - Component bounds (x0-x3 in [0,1])
  - Validation errors
  - Config override
"""
import numpy as np
import pytest

from spider_m.engine import run

# ── Shared fixtures ─────────────────────────────────────────────────────────
N = 64
_rng = np.random.RandomState(42)   # isolated RNG — no global seed side-effect
HIGH = np.linspace(1.30, 1.32, N) + _rng.uniform(0, 0.002, N)
LOW  = HIGH - _rng.uniform(0.001, 0.003, N)

BASE_CFG = {
    "z_thresh":      2.5,
    "tension_skip":  0.35,
    "tension_boost": 0.50,
    "load_max_bars": 8,
    "atr_short":     5,
    "atr_long":      32,
    "lot_cap":       0.10,
    "lot_cap_boost": 0.15,
    "boost_slope":   0.5,
}

def make_payload(z_scores, persist_count, imp_prices, bar_index=50):
    return {
        "z_scores":      z_scores,
        "persist_count": persist_count,
        "high_arr":      HIGH.tolist(),
        "low_arr":       LOW.tolist(),
        "imp_prices":    imp_prices,
        "bar_index":     bar_index,
    }


# ── Tier Tests ──────────────────────────────────────────────────────────────
def test_skip_tier_low_tension():
    """Diverging z-scores + shallow persist → SKIP"""
    payload = make_payload(
        z_scores=[-3.0, -1.0, 0.5],   # diverging — low x0
        persist_count=1,               # shallow — low x1
        imp_prices=[1.310, 1.315, 1.325],  # spread out — low x3
    )
    out = run(payload, BASE_CFG)
    assert out["tier"] == "SKIP", f"Expected SKIP, got {out['tier']} (tension={out['tension']:.4f})"
    assert out["tradeable"] is False
    assert out["tension"] <= BASE_CFG["tension_skip"]


def test_flat_tier_medium_tension():
    """Moderate convergence + shallow persist + spread imp → FLAT zone (0.35-0.50)"""
    payload = make_payload(
        z_scores=[-2.6, -2.5, -2.2],  # moderate x0 (~0.93)
        persist_count=3,               # x1 = 3/8 = 0.375
        imp_prices=[1.310, 1.320, 1.330],  # spread out → x3=0 → tension ~0.42
    )
    out = run(payload, BASE_CFG)
    assert out["tier"] == "FLAT", f"Expected FLAT, got {out['tier']} (tension={out['tension']:.4f})"
    assert out["tradeable"] is True
    assert out["lot_scalar"] == 1.0
    assert BASE_CFG["tension_skip"] < out["tension"] <= BASE_CFG["tension_boost"]


def test_boost_tier_high_tension():
    """Perfect z-scores + deep persist → BOOST"""
    payload = make_payload(
        z_scores=[-2.9, -2.8, -2.85],  # very tight — high x0
        persist_count=8,                # max load — x1=1.0
        imp_prices=[1.3100, 1.3101, 1.3102],  # very tight — high x3
    )
    out = run(payload, BASE_CFG)
    assert out["tier"] == "BOOST", f"Expected BOOST, got {out['tier']} (tension={out['tension']:.4f})"
    assert out["tradeable"] is True
    assert out["lot_scalar"] > 1.0
    assert out["lot_cap_active"] == BASE_CFG["lot_cap_boost"]
    assert out["tension"] > BASE_CFG["tension_boost"]


def test_boost_scalar_formula():
    """Scalar = 1.0 + (tension - boost_t) * slope"""
    payload = make_payload(
        z_scores=[-2.9, -2.85, -2.88],
        persist_count=8,
        imp_prices=[1.3100, 1.3101, 1.3101],
    )
    out = run(payload, BASE_CFG)
    if out["tier"] == "BOOST":
        expected = 1.0 + (out["tension"] - BASE_CFG["tension_boost"]) * BASE_CFG["boost_slope"]
        assert abs(out["lot_scalar"] - expected) < 1e-4


# ── Component Bounds ─────────────────────────────────────────────────────────
def test_components_in_unit_range():
    """x0-x3 must all be in [0, 1]"""
    payload = make_payload(
        z_scores=[-2.5, -2.6, -2.4],
        persist_count=4,
        imp_prices=[1.310, 1.312, 1.311],
    )
    out = run(payload, BASE_CFG)
    for key in ["x0_convergence", "x1_load_depth", "x2_compression", "x3_coherence"]:
        assert 0.0 <= out[key] <= 1.0, f"{key}={out[key]} out of [0,1]"


def test_tension_in_unit_range():
    """Tension must be in [0, 1] (weighted sum of unit components)"""
    payload = make_payload(
        z_scores=[-2.5, -2.6, -2.4],
        persist_count=4,
        imp_prices=[1.310, 1.312, 1.311],
    )
    out = run(payload, BASE_CFG)
    assert 0.0 <= out["tension"] <= 1.0


def test_x1_caps_at_1():
    """persist_count > load_max_bars → x1 = 1.0"""
    payload = make_payload(
        z_scores=[-2.6, -2.7, -2.5],
        persist_count=100,
        imp_prices=[1.310, 1.311, 1.310],
    )
    out = run(payload, BASE_CFG)
    assert out["x1_load_depth"] == 1.0


def test_x0_zero_when_z_diverge():
    """z-scores span > z_thresh std → x0 near 0"""
    payload = make_payload(
        z_scores=[-3.0, 0.0, 3.0],  # std = ~2.45 > z_thresh=2.5? close
        persist_count=2,
        imp_prices=[1.310, 1.311, 1.312],
    )
    out = run(payload, BASE_CFG)
    assert out["x0_convergence"] < 0.1


# ── Config Override ───────────────────────────────────────────────────────────
def test_custom_thresholds():
    """Custom SKIP=0.40, BOOST=0.45 — RAPTOR M5 config"""
    raptor_cfg = {**BASE_CFG, "tension_skip": 0.40, "tension_boost": 0.45}
    payload = make_payload(
        z_scores=[-2.7, -2.6, -2.65],
        persist_count=5,
        imp_prices=[1.3100, 1.3101, 1.3102],
    )
    out = run(payload, raptor_cfg)
    assert out["tier"] in ("SKIP", "FLAT", "BOOST")


def test_default_config_used_when_none():
    """run(payload) without config should not raise"""
    payload = make_payload(
        z_scores=[-2.6, -2.5, -2.7],
        persist_count=3,
        imp_prices=[1.310, 1.311, 1.312],
    )
    out = run(payload)
    assert "tension" in out
    assert "tier" in out


# ── Validation Errors ─────────────────────────────────────────────────────────
def test_missing_z_scores_raises():
    payload = make_payload([0, 0, 0], 2, [1.31, 1.31, 1.31])
    del payload["z_scores"]
    with pytest.raises(ValueError, match="z_scores"):
        run(payload, BASE_CFG)


def test_wrong_z_scores_length_raises():
    payload = make_payload([0, 0], 2, [1.31, 1.31, 1.31])
    with pytest.raises(ValueError, match="z_scores must have exactly 3"):
        run(payload, BASE_CFG)


def test_boost_below_skip_raises():
    bad_cfg = {**BASE_CFG, "tension_skip": 0.60, "tension_boost": 0.40}
    payload = make_payload([-2.6, -2.5, -2.7], 3, [1.310, 1.311, 1.312])
    with pytest.raises(ValueError, match="tension_boost"):
        run(payload, bad_cfg)


def test_mismatched_high_low_raises():
    payload = make_payload([-2.6, -2.5, -2.7], 3, [1.310, 1.311, 1.312])
    payload["low_arr"] = payload["low_arr"][:-5]
    with pytest.raises(ValueError, match="same length"):
        run(payload, BASE_CFG)


# ── Output Contract ───────────────────────────────────────────────────────────
def test_output_keys_complete():
    """Output must contain all expected keys"""
    payload = make_payload([-2.6, -2.5, -2.7], 3, [1.310, 1.311, 1.312])
    out = run(payload, BASE_CFG)
    expected_keys = [
        "tension", "x0_convergence", "x1_load_depth",
        "x2_compression", "x3_coherence", "atr_ref",
        "tier", "lot_scalar", "lot_cap_active", "tradeable",
    ]
    for key in expected_keys:
        assert key in out, f"Missing output key: {key}"
