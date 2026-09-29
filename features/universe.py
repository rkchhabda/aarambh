"""Canonical tradable universe (Nifty 100, de-listed/invalid names removed).

Imported by the serving layer (service/app.py, rebuild_cache_v2.py) AND the
training pipeline (prepare_enhanced_data.py) so the model is always trained and
served on exactly the same tickers. Do NOT redefine TICKERS in multiple files.
"""
TICKERS = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS",
    "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BPCL.NS", "BHARTIARTL.NS",
    "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DIVISLAB.NS", "DRREDDY.NS",
    "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
    "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS",
    "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS",
    "M&M.NS", "MARUTI.NS", "NESTLEIND.NS", "NTPC.NS", "ONGC.NS",
    "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SBIN.NS", "SUNPHARMA.NS",
    "TCS.NS", "TATACONSUM.NS", "TATASTEEL.NS", "TECHM.NS",
    "TITAN.NS", "ULTRACEMCO.NS", "UPL.NS", "WIPRO.NS", "ADANIGREEN.NS",
    "AMBUJACEM.NS", "APOLLOTYRE.NS", "ASHOKLEY.NS", "ASTRAL.NS",
    "AUROPHARMA.NS", "BALKRISIND.NS", "BANDHANBNK.NS", "BANKBARODA.NS", "BEL.NS",
    "BHEL.NS", "BIOCON.NS", "BOSCHLTD.NS", "CANBK.NS", "CHOLAFIN.NS",
    "COLPAL.NS", "CONCOR.NS", "CROMPTON.NS", "CUMMINSIND.NS", "DABUR.NS",
    "DALBHARAT.NS", "DEEPAKNTR.NS", "DLF.NS", "EDELWEISS.NS", "EMAMILTD.NS",
    "ENDURANCE.NS", "ESCORTS.NS", "EXIDEIND.NS", "FEDERALBNK.NS", "GAIL.NS",
    "GLENMARK.NS", "GODREJCP.NS", "GODREJPROP.NS", "GRANULES.NS",
    "HAVELLS.NS", "HINDPETRO.NS", "ICICIGI.NS", "ICICIPRULI.NS", "IDEA.NS",
    "IDFCFIRSTB.NS", "IGL.NS", "INDIGO.NS", "INDUSTOWER.NS", "JINDALSTEL.NS",
    "JUBLFOOD.NS", "LICHSGFIN.NS", "LUPIN.NS", "MARICO.NS",
    "MAXHEALTH.NS", "MFSL.NS", "MOTHERSON.NS", "MPHASIS.NS",
    "MRF.NS", "MUTHOOTFIN.NS", "NAUKRI.NS", "NAVINFLUOR.NS", "NBCC.NS",
    "NMDC.NS", "OBEROIRLTY.NS", "PAGEIND.NS", "PERSISTENT.NS",
    "PETRONET.NS", "PFC.NS", "PIDILITIND.NS", "PIIND.NS", "PNB.NS",
    "POLYCAB.NS", "PVRINOX.NS", "RAMCOCEM.NS", "RBLBANK.NS", "RECLTD.NS",
    "SAIL.NS", "SHREECEM.NS", "SIEMENS.NS", "SRF.NS", "SYNGENE.NS",
    "TATACHEM.NS", "TATACOMM.NS", "TATAPOWER.NS", "TORNTPHARM.NS", "TORNTPOWER.NS",
    "TRENT.NS", "TVSMOTOR.NS", "UBL.NS", "UNIONBANK.NS", "VBL.NS",
    "VEDL.NS", "VOLTAS.NS", "WHIRLPOOL.NS", "ZYDUSLIFE.NS",
]

# ── Sector Groupings & Mapping ────────────────────────────────────────────────
# Canonical sector classification for cross-sectional & relative feature generation
SECTOR_MAP = {
    # Basic Materials (20)
    "AMBUJACEM.NS": "Basic Materials",
    "ASIANPAINT.NS": "Basic Materials",
    "DALBHARAT.NS": "Basic Materials",
    "DEEPAKNTR.NS": "Basic Materials",
    "GRASIM.NS": "Basic Materials",
    "HINDALCO.NS": "Basic Materials",
    "JINDALSTEL.NS": "Basic Materials",
    "JSWSTEEL.NS": "Basic Materials",
    "NAVINFLUOR.NS": "Basic Materials",
    "NMDC.NS": "Basic Materials",
    "PIDILITIND.NS": "Basic Materials",
    "PIIND.NS": "Basic Materials",
    "RAMCOCEM.NS": "Basic Materials",
    "SAIL.NS": "Basic Materials",
    "SHREECEM.NS": "Basic Materials",
    "TATACHEM.NS": "Basic Materials",
    "TATASTEEL.NS": "Basic Materials",
    "ULTRACEMCO.NS": "Basic Materials",
    "UPL.NS": "Basic Materials",
    "VEDL.NS": "Basic Materials",

    # Communication Services (6)
    "BHARTIARTL.NS": "Communication Services",
    "IDEA.NS": "Communication Services",
    "INDUSTOWER.NS": "Communication Services",
    "NAUKRI.NS": "Communication Services",
    "PVRINOX.NS": "Communication Services",
    "TATACOMM.NS": "Communication Services",

    # Consumer Cyclical (20)
    "APOLLOTYRE.NS": "Consumer Cyclical",
    "BAJAJ-AUTO.NS": "Consumer Cyclical",
    "BALKRISIND.NS": "Consumer Cyclical",
    "BOSCHLTD.NS": "Consumer Cyclical",
    "CROMPTON.NS": "Consumer Cyclical",
    "EICHERMOT.NS": "Consumer Cyclical",
    "ENDURANCE.NS": "Consumer Cyclical",
    "EXIDEIND.NS": "Consumer Cyclical",
    "HEROMOTOCO.NS": "Consumer Cyclical",
    "JUBLFOOD.NS": "Consumer Cyclical",
    "M&M.NS": "Consumer Cyclical",
    "MARUTI.NS": "Consumer Cyclical",
    "MOTHERSON.NS": "Consumer Cyclical",
    "MRF.NS": "Consumer Cyclical",
    "PAGEIND.NS": "Consumer Cyclical",
    "TITAN.NS": "Consumer Cyclical",
    "TRENT.NS": "Consumer Cyclical",
    "TVSMOTOR.NS": "Consumer Cyclical",
    "VOLTAS.NS": "Consumer Cyclical",
    "WHIRLPOOL.NS": "Consumer Cyclical",

    # Consumer Defensive (12)
    "BRITANNIA.NS": "Consumer Defensive",
    "COLPAL.NS": "Consumer Defensive",
    "DABUR.NS": "Consumer Defensive",
    "EMAMILTD.NS": "Consumer Defensive",
    "GODREJCP.NS": "Consumer Defensive",
    "HINDUNILVR.NS": "Consumer Defensive",
    "ITC.NS": "Consumer Defensive",
    "MARICO.NS": "Consumer Defensive",
    "NESTLEIND.NS": "Consumer Defensive",
    "TATACONSUM.NS": "Consumer Defensive",
    "UBL.NS": "Consumer Defensive",
    "VBL.NS": "Consumer Defensive",

    # Energy (7)
    "ADANIENT.NS": "Energy",
    "BPCL.NS": "Energy",
    "COALINDIA.NS": "Energy",
    "HINDPETRO.NS": "Energy",
    "ONGC.NS": "Energy",
    "PETRONET.NS": "Energy",
    "RELIANCE.NS": "Energy",

    # Financial Services (27)
    "AXISBANK.NS": "Financial Services",
    "BAJAJFINSV.NS": "Financial Services",
    "BAJFINANCE.NS": "Financial Services",
    "BANDHANBNK.NS": "Financial Services",
    "BANKBARODA.NS": "Financial Services",
    "CANBK.NS": "Financial Services",
    "CHOLAFIN.NS": "Financial Services",
    "EDELWEISS.NS": "Financial Services",
    "FEDERALBNK.NS": "Financial Services",
    "HDFCBANK.NS": "Financial Services",
    "HDFCLIFE.NS": "Financial Services",
    "ICICIBANK.NS": "Financial Services",
    "ICICIGI.NS": "Financial Services",
    "ICICIPRULI.NS": "Financial Services",
    "IDFCFIRSTB.NS": "Financial Services",
    "INDUSINDBK.NS": "Financial Services",
    "KOTAKBANK.NS": "Financial Services",
    "LICHSGFIN.NS": "Financial Services",
    "MFSL.NS": "Financial Services",
    "MUTHOOTFIN.NS": "Financial Services",
    "PFC.NS": "Financial Services",
    "PNB.NS": "Financial Services",
    "RBLBANK.NS": "Financial Services",
    "RECLTD.NS": "Financial Services",
    "SBILIFE.NS": "Financial Services",
    "SBIN.NS": "Financial Services",
    "UNIONBANK.NS": "Financial Services",

    # Healthcare (14)
    "APOLLOHOSP.NS": "Healthcare",
    "AUROPHARMA.NS": "Healthcare",
    "BIOCON.NS": "Healthcare",
    "CIPLA.NS": "Healthcare",
    "DIVISLAB.NS": "Healthcare",
    "DRREDDY.NS": "Healthcare",
    "GLENMARK.NS": "Healthcare",
    "GRANULES.NS": "Healthcare",
    "LUPIN.NS": "Healthcare",
    "MAXHEALTH.NS": "Healthcare",
    "SUNPHARMA.NS": "Healthcare",
    "SYNGENE.NS": "Healthcare",
    "TORNTPHARM.NS": "Healthcare",
    "ZYDUSLIFE.NS": "Healthcare",

    # Industrials (15)
    "ADANIPORTS.NS": "Industrials",
    "ASHOKLEY.NS": "Industrials",
    "ASTRAL.NS": "Industrials",
    "BEL.NS": "Industrials",
    "BHEL.NS": "Industrials",
    "CONCOR.NS": "Industrials",
    "CUMMINSIND.NS": "Industrials",
    "ESCORTS.NS": "Industrials",
    "HAVELLS.NS": "Industrials",
    "INDIGO.NS": "Industrials",
    "LT.NS": "Industrials",
    "NBCC.NS": "Industrials",
    "POLYCAB.NS": "Industrials",
    "SIEMENS.NS": "Industrials",
    "SRF.NS": "Industrials",

    # Real Estate (3)
    "DLF.NS": "Real Estate",
    "GODREJPROP.NS": "Real Estate",
    "OBEROIRLTY.NS": "Real Estate",

    # Technology (7)
    "HCLTECH.NS": "Technology",
    "INFY.NS": "Technology",
    "MPHASIS.NS": "Technology",
    "PERSISTENT.NS": "Technology",
    "TCS.NS": "Technology",
    "TECHM.NS": "Technology",
    "WIPRO.NS": "Technology",

    # Utilities (7)
    "ADANIGREEN.NS": "Utilities",
    "GAIL.NS": "Utilities",
    "IGL.NS": "Utilities",
    "NTPC.NS": "Utilities",
    "POWERGRID.NS": "Utilities",
    "TATAPOWER.NS": "Utilities",
    "TORNTPOWER.NS": "Utilities",
}

# ── Sector Groupings for Modeling / Relative Features ─────────────────────────
# POINT-IN-TIME CLASSIFICATION DISCLOSURE & KNOWN LIMITATION:
# SECTOR_MAP and SECTOR_MAP_MODELING reflect each stock's sector classification
# as established in 2026. This classification is applied uniformly backward across
# the 10-year dataset (2016-2026). While broad sector memberships for these mature
# large-cap equities are historically stable, this is a known limitation: historical
# corporate restructurings or classification revisions over the 10-year span are
# not dynamically re-classified day-by-day.
#
# REAL ESTATE SPARSITY RESOLUTION:
# Real Estate contains only 3 tickers (DLF, GODREJPROP, OBEROIRLTY; only 2 active
# prior to 2018). In SECTOR_MAP_MODELING, Real Estate is merged with Industrials into
# "Industrials & Real Estate" (18 tickers total). This ensures:
#   1. Every sector has at least 6 members across history for robust cross-sectional means.
#   2. Retains the 3 tickers in the tradable universe so the model and portfolio
#      coverage remains 100% (138/138 names) without excluding assets.
#   3. Aligns with standard Indian capital market industry clustering (Infrastructure,
#      Construction, Engineering, and Property development).
SECTOR_MAP_MODELING = dict(SECTOR_MAP)
for _re_ticker in ["DLF.NS", "GODREJPROP.NS", "OBEROIRLTY.NS"]:
    SECTOR_MAP_MODELING[_re_ticker] = "Industrials & Real Estate"
for _ind_ticker in [
    "ADANIPORTS.NS", "ASHOKLEY.NS", "ASTRAL.NS", "BEL.NS", "BHEL.NS",
    "CONCOR.NS", "CUMMINSIND.NS", "ESCORTS.NS", "HAVELLS.NS", "INDIGO.NS",
    "LT.NS", "NBCC.NS", "POLYCAB.NS", "SIEMENS.NS", "SRF.NS"
]:
    SECTOR_MAP_MODELING[_ind_ticker] = "Industrials & Real Estate"

SECTOR_GROUPS_MODELING = {}
for _ticker, _sector in SECTOR_MAP_MODELING.items():
    SECTOR_GROUPS_MODELING.setdefault(_sector, []).append(_ticker)

SECTOR_GROUPS = {}
for _ticker, _sector in SECTOR_MAP.items():
    SECTOR_GROUPS.setdefault(_sector, []).append(_ticker)

