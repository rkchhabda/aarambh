"""Unit tests for feature engineering parity and schema validation."""

import os
import sys
import json
import pytest
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from features.indicators import compute_features, compute_inference_features, ALL_FEATURES


def create_sample_ohlcv(rows=250):
    """Generate deterministic sample OHLCV data for testing."""
    np.random.seed(42)
    dates = pd.date_range("2025-01-01", periods=rows, freq="B")
    close = 100.0 + np.cumsum(np.random.randn(rows) * 1.5)
    high = close + np.abs(np.random.randn(rows))
    low = close - np.abs(np.random.randn(rows))
    open_p = (high + low) / 2.0
    volume = np.random.randint(1000, 50000, size=rows)
    return pd.DataFrame({
        "date": dates,
        "Open": open_p,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })


def test_compute_features_shape_and_columns():
    df = create_sample_ohlcv(250)
    feat_df = compute_features(df)
    assert len(feat_df) == len(df)
    assert "date" in feat_df.columns
    assert "Close" in feat_df.columns
    for col in ALL_FEATURES:
        assert col in feat_df.columns, f"Missing feature {col}"


def test_obv_slope_parity():
    """Verify obv_slope uses OBV.diff(5) consistently across batch and inference."""
    df = create_sample_ohlcv(250)
    feat_df = compute_features(df)
    
    # Manual OBV check
    c = pd.Series(df["Close"])
    v = pd.Series(df["Volume"])
    direction = np.sign(c.diff()).fillna(0)
    obv_manual = (direction * v).cumsum()
    obv_slope_manual = obv_manual.diff(5)
    
    np.testing.assert_allclose(
        feat_df["obv_slope"].dropna().values,
        obv_slope_manual.dropna().values,
        rtol=1e-5,
        err_msg="obv_slope mismatch!"
    )


def test_inference_features_parity():
    """Verify compute_inference_features matches the last row of compute_features."""
    df = create_sample_ohlcv(250)
    target_features = ["bb_pos", "macd", "obv_slope", "sma_ratio", "cci", "ret_10", "williams_r", "rsi_14", "atr_14", "roc_10"]
    
    batch_df = compute_features(df)
    last_batch_row = batch_df.iloc[-1]
    
    inf_dict, close, sma200 = compute_inference_features(df, target_features)
    
    assert close == float(df["Close"].iloc[-1])
    assert abs(sma200 - df["Close"].rolling(200).mean().iloc[-1]) < 1e-5
    
    for f in target_features:
        expected_val = float(last_batch_row[f]) if pd.notna(last_batch_row[f]) else 0.0
        assert abs(inf_dict[f] - expected_val) < 1e-5, f"Feature {f} discrepancy: {inf_dict[f]} vs {expected_val}"


if __name__ == "__main__":
    test_compute_features_shape_and_columns()
    test_obv_slope_parity()
    test_inference_features_parity()
    print("[OK] All feature parity tests passed!")
