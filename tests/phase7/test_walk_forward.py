"""Unit tests for expanding walk-forward fold generator and validation governance."""

from datetime import date, timedelta
import pandas as pd
import pytest

from phase7.validation.contracts import (
    InsufficientDataForWalkForwardError,
    ValidationAuditRecord,
    ValidationLeakageError,
    WalkForwardConfig,
    WalkForwardFold,
)
from phase7.validation.walk_forward import (
    ExpandingWalkForwardSplitter,
)


def _generate_trading_calendar(start_date: date, count: int) -> list[date]:
    """Generate a synthetic calendar of trading dates skipping weekends."""
    calendar = []
    curr = start_date
    while len(calendar) < count:
        if curr.weekday() < 5:  # Monday to Friday
            calendar.append(curr)
        curr += timedelta(days=1)
    return calendar


class TestExpandingWalkForward:
    """Test suite for expanding walk-forward partitioning and fold governance."""

    def test_generate_10_expanding_folds_primary_target(self) -> None:
        """Verify generating at least 10 expanding folds with 20d purge and 5d embargo."""
        # 252 min_train + 20 purge + 10 * 30 test = 572 sessions
        cal = _generate_trading_calendar(date(2021, 1, 4), 600)
        config = WalkForwardConfig(
            min_expanding_windows=10,
            target_name="target_20d_sector_relative",
            min_train_trading_days=252,
            primary_target_purge_days=20,
            primary_target_embargo_days=5,
        )
        splitter = ExpandingWalkForwardSplitter(config)
        folds = splitter.generate_folds(cal, dataset_version="v1.0.0")

        assert len(folds) >= 10
        assert len(folds) == 10

        # Check fold properties
        for fold in folds:
            assert isinstance(fold, WalkForwardFold)
            assert fold.purge_trading_days == 20
            assert fold.embargo_trading_days == 5
            assert fold.fold_hash != ""

    def test_expanding_window_strictly_monotonic_training(self) -> None:
        """Verify train window expands monotonically across all folds."""
        cal = _generate_trading_calendar(date(2021, 1, 4), 600)
        splitter = ExpandingWalkForwardSplitter()
        folds = splitter.generate_folds(cal)

        # Initial train start is invariant
        initial_train_start = folds[0].train_start_date
        for k in range(len(folds)):
            assert folds[k].train_start_date == initial_train_start

        # Train end strictly increases
        for k in range(len(folds) - 1):
            curr_fold = folds[k]
            next_fold = folds[k + 1]
            assert curr_fold.train_end_date < next_fold.train_end_date
            assert curr_fold.train_trading_days < next_fold.train_trading_days

    def test_test_windows_are_sequential_and_non_overlapping(self) -> None:
        """Verify out-of-sample test windows are strictly non-overlapping."""
        cal = _generate_trading_calendar(date(2021, 1, 4), 600)
        splitter = ExpandingWalkForwardSplitter()
        folds = splitter.generate_folds(cal)

        for k in range(len(folds) - 1):
            curr_test_end = folds[k].test_end_date
            next_test_start = folds[k + 1].test_start_date
            assert curr_test_end < next_test_start

    def test_purge_gap_strictly_enforced_on_every_fold(self) -> None:
        """Verify purge gap between train_end and test_start is >= 20 on every fold."""
        cal = _generate_trading_calendar(date(2021, 1, 4), 600)
        splitter = ExpandingWalkForwardSplitter()
        folds = splitter.generate_folds(cal)

        cal_map = {d: idx for idx, d in enumerate(cal)}
        for fold in folds:
            train_idx = cal_map[fold.train_end_date]
            test_idx = cal_map[fold.test_start_date]
            gap = test_idx - train_idx - 1
            assert gap >= 20

    def test_secondary_target_60d_enforces_60d_purge_and_10d_embargo(self) -> None:
        """Verify secondary target enforces 60d purge gap and 10d embargo."""
        # 252 + 60 + 10 * 30 = 612 sessions
        cal = _generate_trading_calendar(date(2020, 1, 6), 650)
        config = WalkForwardConfig(
            min_expanding_windows=10,
            target_name="target_60d_residual",
            min_train_trading_days=252,
            secondary_target_purge_days=60,
            secondary_target_embargo_days=10,
        )
        splitter = ExpandingWalkForwardSplitter(config)
        folds = splitter.generate_folds(cal)

        assert len(folds) >= 10
        cal_map = {d: idx for idx, d in enumerate(cal)}

        for fold in folds:
            assert fold.purge_trading_days == 60
            assert fold.embargo_trading_days == 10
            train_idx = cal_map[fold.train_end_date]
            test_idx = cal_map[fold.test_start_date]
            gap = test_idx - train_idx - 1
            assert gap >= 60

    def test_insufficient_calendar_sessions_fails_closed(self) -> None:
        """Verify InsufficientDataForWalkForwardError is raised if sessions are insufficient."""
        # Only 200 sessions available (less than min_train 252)
        cal = _generate_trading_calendar(date(2023, 1, 2), 200)
        splitter = ExpandingWalkForwardSplitter()

        with pytest.raises(InsufficientDataForWalkForwardError, match="Trading calendar has 200 sessions"):
            splitter.generate_folds(cal)

    def test_deterministic_fold_hashes(self) -> None:
        """Verify fold hashes are strictly reproducible across runs."""
        cal = _generate_trading_calendar(date(2021, 1, 4), 600)
        splitter = ExpandingWalkForwardSplitter()

        run1 = splitter.generate_folds(cal, dataset_version="v1.0.0")
        run2 = splitter.generate_folds(cal, dataset_version="v1.0.0")

        for f1, f2 in zip(run1, run2):
            assert f1.fold_hash == f2.fold_hash
            assert f1.fold_hash != ""

    def test_split_dataframe_generator(self) -> None:
        """Verify splitting a pandas DataFrame into sequential train/test slices."""
        cal = _generate_trading_calendar(date(2021, 1, 4), 600)
        df_rows = []
        for d in cal:
            for s in ["TCS", "INFY"]:
                df_rows.append({"trading_date": d, "symbol": s, "val": 1.0})
        df = pd.DataFrame(df_rows)

        splitter = ExpandingWalkForwardSplitter()
        splits = list(splitter.split_dataframe(df, date_column="trading_date"))

        assert len(splits) >= 10
        for fold, train_df, test_df in splits:
            assert len(train_df) > 0
            assert len(test_df) > 0
            # Zero date overlap between train and test
            train_dates = set(train_df["trading_date"])
            test_dates = set(test_df["trading_date"])
            assert train_dates.isdisjoint(test_dates)

    def test_audit_walk_forward_record(self) -> None:
        """Verify audit_walk_forward produces valid ValidationAuditRecord."""
        cal = _generate_trading_calendar(date(2021, 1, 4), 600)
        splitter = ExpandingWalkForwardSplitter()
        folds = splitter.generate_folds(cal, dataset_version="v1.0.0")

        audit = splitter.audit_walk_forward(folds, cal, dataset_version="v1.0.0")
        assert isinstance(audit, ValidationAuditRecord)
        assert audit.total_folds == 10
        assert audit.min_expanding_windows == 10
        assert audit.expanding_property_verified is True
        assert audit.zero_label_leakage_verified is True
        assert audit.fold_local_preprocessing_verified is True
        assert audit.audit_hash != ""

        # Reproducibility
        audit2 = splitter.audit_walk_forward(folds, cal, dataset_version="v1.0.0")
        assert audit.audit_hash == audit2.audit_hash
