"""Single source of truth for feature engineering.

Both the training pipeline (prepare_enhanced_data.py) and the live service
(rebuild_cache_v2.py -> ticker_cache.json -> service/app.py) MUST use the
functions defined here so that features fed to the model at inference time are
identical to those used during training.

Never redefine indicators in another script — import from here instead.
"""
import numpy as np
import pandas as pd
import ta

# The full candidate feature set (27). Final models use a subset of these
# (selected via Optuna / feature selection and stored in best_params.json).
ALL_FEATURES = [
    "ret_1", "ret_5", "ret_10", "log_vol_chg", "rsi_14", "macd",
    "bb_pos", "atr_14", "obv_slope", "sma_ratio", "rvol_5", "rvol_20",
    "stoch_k", "stoch_d", "cci", "williams_r", "roc_10",
    "adx", "aroon_up", "aroon_down", "sma_5_20_cross",
    "mfi", "volume_sma_ratio",
    "price_vs_high20", "price_vs_low20",
    "ret_20", "rvol_10",
]


def compute_features(df, index_returns=None):
    """Compute the full feature set from a single-ticker OHLCV DataFrame.

    Expected columns: Date/date, Open, High, Low, Close, Volume.
    Returns a DataFrame indexed like ``df`` with ``date``, ``Close`` and all
    ``ALL_FEATURES`` columns. Early rows may contain NaN (indicator warm-up).
    """
    c = df["Close"].values
    h = df["High"].values
    l = df["Low"].values
    v = df["Volume"].values
    cs = pd.Series(c, index=df.index)
    hs = pd.Series(h, index=df.index)
    ls = pd.Series(l, index=df.index)
    vs = pd.Series(v, index=df.index)
    dates = df["date"].values

    feat = {}
    # Original 12
    feat["ret_1"] = cs.pct_change(1).values
    feat["ret_5"] = cs.pct_change(5).values
    feat["ret_10"] = cs.pct_change(10).values
    feat["log_vol_chg"] = np.log(vs + 1).diff().values
    feat["rsi_14"] = ta.momentum.RSIIndicator(cs, window=14).rsi().values
    macd_ind = ta.trend.MACD(cs)
    feat["macd"] = macd_ind.macd_diff().values
    bb = ta.volatility.BollingerBands(cs, window=20)
    feat["bb_pos"] = ((cs - bb.bollinger_mavg()) / (bb.bollinger_wband() + 1e-10)).values
    atr = ta.volatility.AverageTrueRange(hs, ls, cs, window=14)
    feat["atr_14"] = (atr.average_true_range() / cs).values
    obv = ta.volume.OnBalanceVolumeIndicator(cs, vs).on_balance_volume()
    feat["obv_slope"] = obv.diff(5).values  # OBV[t] - OBV[t-5]  (MUST match training)
    sma_20 = ta.trend.SMAIndicator(cs, window=20).sma_indicator()
    feat["sma_ratio"] = (cs / sma_20 - 1).values
    feat["rvol_5"] = cs.pct_change().rolling(5).std().values
    feat["rvol_20"] = cs.pct_change().rolling(20).std().values

    # New momentum
    stoch = ta.momentum.StochasticOscillator(hs, ls, cs, window=14, smooth_window=3)
    feat["stoch_k"] = stoch.stoch().values
    feat["stoch_d"] = stoch.stoch_signal().values
    feat["cci"] = ta.trend.CCIIndicator(hs, ls, cs, window=20).cci().values
    feat["williams_r"] = ta.momentum.WilliamsRIndicator(hs, ls, cs, lbp=14).williams_r().values
    feat["roc_10"] = ta.momentum.ROCIndicator(cs, window=10).roc().values

    # New trend
    adx_ind = ta.trend.ADXIndicator(hs, ls, cs, window=14)
    feat["adx"] = adx_ind.adx().values
    aroon = ta.trend.AroonIndicator(hs, ls, window=25)
    feat["aroon_up"] = aroon.aroon_up().values
    feat["aroon_down"] = aroon.aroon_down().values
    sma_5 = cs.rolling(5).mean()
    feat["sma_5_20_cross"] = ((sma_5 - sma_20) / (sma_20 + 1e-10)).values

    # New volume
    feat["mfi"] = ta.volume.MFIIndicator(hs, ls, cs, vs, window=14).money_flow_index().values
    vol_sma_20 = vs.rolling(20).mean()
    feat["volume_sma_ratio"] = (vs / (vol_sma_20 + 1)).values

    # New regime
    high_20 = hs.rolling(20).max()
    low_20 = ls.rolling(20).min()
    feat["price_vs_high20"] = ((cs - high_20) / (high_20 + 1e-10)).values
    feat["price_vs_low20"] = ((cs - low_20) / (low_20 + 1e-10)).values

    # Multi-timeframe
    feat["ret_20"] = cs.pct_change(20).values
    feat["rvol_10"] = cs.pct_change().rolling(10).std().values

    # Sector-relative (optional)
    if index_returns is not None:
        ir = pd.Series(index_returns).reindex(pd.Series(dates)).values
        ret5 = feat["ret_5"]
        ret20 = feat["ret_20"]
        ir5 = pd.Series(ir).rolling(5).sum().values
        ir20 = pd.Series(ir).rolling(20).sum().values
        feat["relative_ret_5"] = ret5 - ir5
        feat["relative_ret_20"] = ret20 - ir20
    else:
        feat["relative_ret_5"] = np.zeros(len(df))
        feat["relative_ret_20"] = np.zeros(len(df))

    out = pd.DataFrame(feat, index=df.index)
    out["date"] = dates
    out["Close"] = c
    return out


def compute_inference_features(df, features, index_returns=None):
    """Compute the requested ``features`` for the latest row of ``df``.

    Returns ``(features_dict, close, sma_200)`` in the exact same manner the
    model was trained on (NaN -> 0, matching the training ``.fillna(0)``).
    """
    out = compute_features(df, index_returns)
    last = out.iloc[-1]
    fdict = {f: float(last[f]) if pd.notna(last[f]) else 0.0 for f in features}
    close = float(last["Close"])
    sma_200 = float(pd.Series(df["Close"]).rolling(200).mean().iloc[-1])
    return fdict, close, sma_200
