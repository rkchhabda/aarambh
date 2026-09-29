"""Phase 6 Single Data-Loading Module with Hard Pre-Registration Safeguards.

Governing Pre-Registration:
- docs/RESEARCH_PREREGISTRATION_AMENDMENT_1.md (Signed 29.09.2026)
- docs/RESEARCH_PREREGISTRATION.md (Signed 27.09.2026)

Section E Requirement:
"All Phase 6 development code loads data through a single module that refuses
any row dated after the development cutoff."

Development Split (Section C):
- Start date: 2016-09-26
- End date: 2025-09-30 minus 10-trading-day purge gap = 2025-09-16
- Hard Cutoff: 2025-09-16 (any date > 2025-09-16 is strictly prohibited)
- Purge gap: 2025-09-17 to 2025-09-30 (10 trading days, excluded from training)
- Window A (sealed): 2025-10-01 to 2026-03-31
- Window B (sealed): 2026-04-01 to 2026-09-25
"""

import os
import sys
from typing import List, Optional, Union
import pandas as pd

# Hard boundary defined in Amendment 1 Section C
DEVELOPMENT_CUTOFF_DATE = "2025-09-16"
DEVELOPMENT_START_DATE = "2016-09-26"
WINDOW_A_START_DATE = "2025-10-01"
WINDOW_B_START_DATE = "2026-04-01"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DATA_PATH = os.path.join(BASE_DIR, "data", "multi", "historical_10y_raw.csv")
FEATURES_DATA_PATH = os.path.join(BASE_DIR, "data", "multi", "relative_features_v1.csv")


class PreRegistrationDataLeakError(ValueError):
    """Raised when an operation attempts to access data beyond the pre-registered development cutoff."""
    pass


def _validate_date_bounds(start_date: Optional[str], end_date: Optional[str]) -> None:
    """Validate that requested dates do not violate the Phase 6 development boundary."""
    if end_date is not None:
        clean_end = str(end_date).strip()[:10]
        if clean_end > DEVELOPMENT_CUTOFF_DATE:
            raise PreRegistrationDataLeakError(
                f"[PRE-REGISTRATION VIOLATION] Requested end_date '{clean_end}' exceeds the Phase 6 "
                f"development cutoff date '{DEVELOPMENT_CUTOFF_DATE}' (2025-09-30 minus 10-trading-day "
                f"purge gap). Phase 6 Amendment 1 Section C/E strictly prohibits accessing data after "
                f"{DEVELOPMENT_CUTOFF_DATE} during development. Holdout Windows A & B are sealed."
            )

    if start_date is not None:
        clean_start = str(start_date).strip()[:10]
        if clean_start > DEVELOPMENT_CUTOFF_DATE:
            raise PreRegistrationDataLeakError(
                f"[PRE-REGISTRATION VIOLATION] Requested start_date '{clean_start}' falls after the "
                f"development cutoff date '{DEVELOPMENT_CUTOFF_DATE}'. Phase 6 Amendment 1 Section C/E "
                f"strictly prohibits accessing holdout periods during development."
            )


def load_development_data(
    dataset_type: str = "features",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    tickers: Optional[Union[str, List[str]]] = None,
) -> pd.DataFrame:
    """Load development data (raw or features) strictly bounded by the development cutoff.
    
    Args:
        dataset_type: "features" for relative_features_v1, or "raw" for historical_10y_raw.
        start_date: Optional YYYY-MM-DD start filter (must be <= 2025-09-16).
        end_date: Optional YYYY-MM-DD end filter (must be <= 2025-09-16).
        tickers: Optional ticker or list of tickers to filter.
        
    Returns:
        pd.DataFrame containing development rows only (date <= 2025-09-16).
        
    Raises:
        PreRegistrationDataLeakError: If start_date or end_date exceeds 2025-09-16,
            or if any row in the loaded dataset exceeds the cutoff.
    """
    _validate_date_bounds(start_date, end_date)

    if dataset_type == "features":
        file_path = FEATURES_DATA_PATH
    elif dataset_type == "raw":
        file_path = RAW_DATA_PATH
    else:
        raise ValueError(f"Unknown dataset_type '{dataset_type}'. Must be 'features' or 'raw'.")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Dataset file not found at: {file_path}")

    df = pd.read_csv(file_path)

    # Hard invariant: refuse any row dated after DEVELOPMENT_CUTOFF_DATE
    if "date" not in df.columns:
        raise KeyError(f"'date' column missing from dataset {file_path}")

    # Convert/ensure string format for date comparison
    df = df.assign(date=df["date"].astype(str).str.strip().str[:10])

    # Pre-registration integrity check: refuse any rows post-cutoff
    post_cutoff_mask = df["date"] > DEVELOPMENT_CUTOFF_DATE
    if post_cutoff_mask.any():
        num_leaked = post_cutoff_mask.sum()
        max_leaked = df.loc[post_cutoff_mask, "date"].max()
        raise PreRegistrationDataLeakError(
            f"[PRE-REGISTRATION INTEGRITY FAILURE] Found {num_leaked} rows with date > "
            f"'{DEVELOPMENT_CUTOFF_DATE}' (max: {max_leaked}) in {file_path}. "
            f"All post-cutoff data must be sealed outside the repository per Amendment 1."
        )

    # Apply date filters within the safe development boundary
    if start_date is not None:
        clean_start = str(start_date).strip()[:10]
        df = df[df["date"] >= clean_start]

    if end_date is not None:
        clean_end = str(end_date).strip()[:10]
        df = df[df["date"] <= clean_end]

    # Apply ticker filter if specified
    if tickers is not None:
        if isinstance(tickers, str):
            tickers = [tickers]
        df = df[df["ticker"].isin(tickers)]

    # Final assertion safeguard
    if not df.empty and df["date"].max() > DEVELOPMENT_CUTOFF_DATE:
        raise PreRegistrationDataLeakError(
            f"[CRITICAL SAFEGUARD] Output contains date {df['date'].max()} > {DEVELOPMENT_CUTOFF_DATE}"
        )

    return df.reset_index(drop=True)


def load_development_features(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    tickers: Optional[Union[str, List[str]]] = None,
) -> pd.DataFrame:
    """Convenience wrapper to load cross-sectional relative features for development."""
    return load_data(dataset_type="features", start_date=start_date, end_date=end_date, tickers=tickers)


def load_development_raw(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    tickers: Optional[Union[str, List[str]]] = None,
) -> pd.DataFrame:
    """Convenience wrapper to load raw historical prices for development."""
    return load_data(dataset_type="raw", start_date=start_date, end_date=end_date, tickers=tickers)


# Primary alias matching Amendment 1 Section E specification
load_data = load_development_data


if __name__ == "__main__":
    print("=" * 60)
    print("PHASE 6 DATA LOADER SAFEGUARD SELF-TEST")
    print(f"Development Cutoff: {DEVELOPMENT_CUTOFF_DATE}")
    print("=" * 60)

    # 1. Test valid development load
    print("\n[Test 1] Loading valid development features...")
    dev_df = load_development_features(start_date="2025-01-01", end_date="2025-09-16")
    print(f"-> SUCCESS: Loaded {len(dev_df):,} rows. Date range: {dev_df['date'].min()} to {dev_df['date'].max()}")
    assert dev_df["date"].max() <= DEVELOPMENT_CUTOFF_DATE, "Cutoff exceeded!"

    # 2. Test refusal of Purge Gap date (2025-09-20)
    print("\n[Test 2] Testing refusal of Purge Gap date (2025-09-20)...")
    try:
        load_development_features(end_date="2025-09-20")
        print("-> FAILED: Expected PreRegistrationDataLeakError not raised!")
        sys.exit(1)
    except PreRegistrationDataLeakError as e:
        print(f"-> SUCCESS: Correctly refused purge gap request.\n   Error: {e}")

    # 3. Test refusal of Window A date (2025-10-01)
    print("\n[Test 3] Testing refusal of Window A start date (2025-10-01)...")
    try:
        load_development_features(start_date="2025-10-01")
        print("-> FAILED: Expected PreRegistrationDataLeakError not raised!")
        sys.exit(1)
    except PreRegistrationDataLeakError as e:
        print(f"-> SUCCESS: Correctly refused Window A request.\n   Error: {e}")

    # 4. Test refusal of Window B date (2026-04-01)
    print("\n[Test 4] Testing refusal of Window B start date (2026-04-01)...")
    try:
        load_development_features(start_date="2026-04-01")
        print("-> FAILED: Expected PreRegistrationDataLeakError not raised!")
        sys.exit(1)
    except PreRegistrationDataLeakError as e:
        print(f"-> SUCCESS: Correctly refused Window B request.\n   Error: {e}")

    print("\n" + "=" * 60)
    print("ALL DATA LOADER SAFEGUARD TESTS PASSED!")
    print("=" * 60)
