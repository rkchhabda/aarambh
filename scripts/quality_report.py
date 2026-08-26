import os

import numpy as np
import pandas as pd

DATA_DIR = "data"
SPLITS = ["train", "val", "test"]
OHLCV = ["open", "high", "low", "close", "volume"]
OUT_PATH = os.path.join(DATA_DIR, "quality_report.txt")


def analyze_split(df: pd.DataFrame, name: str) -> list[str]:
    lines = []
    lines.append(f"=== {name.upper()} ===")
    lines.append(f"Total rows      : {len(df)}")
    lines.append(f"Date range      : {df['timestamps'].iloc[0].date()} -> "
                 f"{df['timestamps'].iloc[-1].date()}")
    lines.append(f"Duplicate dates : {int(df['timestamps'].duplicated().sum())}")
    lines.append(f"Sorted          : {bool(df['timestamps'].is_monotonic_increasing)}")

    missing = df.isna().sum()
    total_missing = int(missing.sum())
    lines.append(f"Missing values  : {total_missing} "
                 f"{'' if total_missing == 0 else '(' + ', '.join(f'{c}={v}' for c, v in missing.items() if v) + ')'}")

    # OHLC consistency violations
    bad_ohlc = int(((df["high"] < df[["open", "close", "low"]].max(axis=1)) |
                    (df["low"] > df[["open", "close", "low"]].min(axis=1)) |
                    (df[OHLCV] <= 0).any(axis=1)).sum())
    lines.append(f"OHLC violations : {bad_ohlc}")

    # Outliers beyond 5 std (per split, per column)
    outlier_lines = []
    for col in OHLCV:
        mean, std = df[col].mean(), df[col].std()
        z = (df[col] - mean).abs() / std
        count = int((z > 5).sum())
        if count:
            worst_idx = z.idxmax()
            outlier_lines.append(
                f"    {col:<7}: {count:>3} outliers (>5 sigma). "
                f"Worst: {df.loc[worst_idx, 'timestamps'].date()} "
                f"value={df.loc[worst_idx, col]:.2f} z={z.max():.2f}")
        else:
            outlier_lines.append(f"    {col:<7}: 0 outliers (>5 sigma)")
    lines.append("Outliers (>5 std):")
    lines.extend(outlier_lines)

    # Zero-volume days (market holidays / data glitches)
    zero_vol = int((df["volume"] == 0).sum())
    lines.append(f"Zero-volume rows: {zero_vol}")

    lines.append("Summary statistics (mean / std / min / max):")
    stats = df[OHLCV + ["amount"]].agg(["mean", "std", "min", "max"]).T
    for col, row in stats.iterrows():
        lines.append(f"    {col:<7}: mean={row['mean']:>16,.2f}  std={row['std']:>15,.2f}  "
                     f"min={row['min']:>16,.2f}  max={row['max']:>16,.2f}")
    return lines


def main():
    dfs = {s: pd.read_csv(os.path.join(DATA_DIR, f"{s}.csv"), parse_dates=["timestamps"])
           for s in SPLITS}

    all_dates = [set(dfs[s]["timestamps"]) for s in SPLITS]
    cross_overlap = all_dates[0] | all_dates[1] | all_dates[2]
    cross_overlap = len(all_dates[0]) + len(all_dates[1]) + len(all_dates[2]) - len(cross_overlap)

    lines = []
    lines.append("KRONOS PHASE 1 - DATA QUALITY REPORT (AAPL, daily)")
    lines.append("=" * 60)
    for s in SPLITS:
        lines.extend(analyze_split(dfs[s], s))
        lines.append("")
    lines.append(f"Cross-split timestamp overlap: {cross_overlap} "
                 f"({'PASS' if cross_overlap == 0 else 'FAIL'})")

    report = "\n".join(lines)
    print(report)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(report + "\n")
    print(f"\nReport saved -> {os.path.abspath(OUT_PATH)}")


if __name__ == "__main__":
    main()
