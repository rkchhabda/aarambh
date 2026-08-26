import os

import pandas as pd

RAW_PATH = os.path.join("data", "raw", "market_data.csv")
OUT_DIR = "data"

TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15


def main():
    df = pd.read_csv(RAW_PATH, parse_dates=["timestamps"])
    df = df.sort_values("timestamps").reset_index(drop=True)

    n = len(df)
    train_end = int(n * TRAIN_RATIO)
    val_end = int(n * (TRAIN_RATIO + VAL_RATIO))

    # Slicing guarantees disjoint, chronologically ordered splits
    train = df.iloc[:train_end].reset_index(drop=True)
    val = df.iloc[train_end:val_end].reset_index(drop=True)
    test = df.iloc[val_end:].reset_index(drop=True)

    assert len(train) + len(val) + len(test) == n
    assert train["timestamps"].max() < val["timestamps"].min()
    assert val["timestamps"].max() < test["timestamps"].min()

    os.makedirs(OUT_DIR, exist_ok=True)
    train.to_csv(os.path.join(OUT_DIR, "train.csv"), index=False)
    val.to_csv(os.path.join(OUT_DIR, "val.csv"), index=False)
    test.to_csv(os.path.join(OUT_DIR, "test.csv"), index=False)

    print(f"Total rows: {n}")
    for name, split in [("TRAIN", train), ("VAL", val), ("TEST", test)]:
        pct = len(split) / n * 100
        print(f"{name:>5}: {len(split):>5} rows ({pct:5.2f}%) | "
              f"{split['timestamps'].iloc[0].date()} -> {split['timestamps'].iloc[-1].date()}")

    # Overlap check across all pairs
    for a_name, b_name in [("train", "val"), ("val", "test"), ("train", "test")]:
        a = set(pd.read_csv(os.path.join(OUT_DIR, f"{a_name}.csv"))["timestamps"])
        b = set(pd.read_csv(os.path.join(OUT_DIR, f"{b_name}.csv"))["timestamps"])
        overlap = a & b
        status = "NO OVERLAP" if not overlap else f"OVERLAP: {len(overlap)} dates"
        print(f"Check {a_name}/{b_name}: {status}")

    gap_train_val = (val["timestamps"].iloc[0] - train["timestamps"].iloc[-1]).days
    gap_val_test = (test["timestamps"].iloc[0] - val["timestamps"].iloc[-1]).days
    print(f"Boundary gaps (calendar days): train->val = {gap_train_val}, "
          f"val->test = {gap_val_test} (adjacent trading days expected)")


if __name__ == "__main__":
    main()
