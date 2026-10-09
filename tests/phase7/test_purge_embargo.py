"""Unit tests for Phase 7 purge and embargo interval enforcement and label leakage validation."""

from datetime import date, timedelta
import pytest

from phase7.validation.contracts import (
    InvalidPurgeEmbargoConfigError,
    PurgeEmbargoInterval,
    ValidationLeakageError,
    WalkForwardConfig,
)
from phase7.validation.purge_embargo import (
    build_purge_embargo_interval,
    compute_embargo_interval,
    compute_purge_interval,
    validate_purge_embargo_days,
    verify_zero_label_leakage,
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


class TestPurgeEmbargo:
    """Test suite for purge and embargo interval logic and leakage protection."""

    def test_preregistered_minimum_thresholds_validation(self) -> None:
        """Verify that purge and embargo parameters enforce preregistered minimums."""
        # Primary target (20d): min 20 purge, min 5 embargo
        p, e = validate_purge_embargo_days("target_20d_sector_relative", 20, 5)
        assert p == 20
        assert e == 5

        # Secondary target (60d): min 60 purge, min 10 embargo
        p60, e60 = validate_purge_embargo_days("target_60d_residual", 60, 10)
        assert p60 == 60
        assert e60 == 10

        # Primary target violations fail closed
        with pytest.raises(InvalidPurgeEmbargoConfigError, match="must be >= 20"):
            validate_purge_embargo_days("target_20d_sector_relative", 19, 5)

        with pytest.raises(InvalidPurgeEmbargoConfigError, match="must be >= 5"):
            validate_purge_embargo_days("target_20d_sector_relative", 20, 4)

        # Secondary target violations fail closed
        with pytest.raises(InvalidPurgeEmbargoConfigError, match="must be >= 60"):
            validate_purge_embargo_days("target_60d_residual", 59, 10)

        with pytest.raises(InvalidPurgeEmbargoConfigError, match="must be >= 10"):
            validate_purge_embargo_days("target_60d_residual", 60, 9)

    def test_walk_forward_config_threshold_enforcement(self) -> None:
        """Verify that WalkForwardConfig validates thresholds in __post_init__."""
        cfg = WalkForwardConfig(
            min_expanding_windows=10,
            primary_target_purge_days=20,
            primary_target_embargo_days=5,
            secondary_target_purge_days=60,
            secondary_target_embargo_days=10,
        )
        assert cfg.get_purge_days() == 20
        assert cfg.get_embargo_days() == 5

        cfg60 = WalkForwardConfig(target_name="target_60d_residual")
        assert cfg60.get_purge_days() == 60
        assert cfg60.get_embargo_days() == 10

        with pytest.raises(InvalidPurgeEmbargoConfigError, match="min_expanding_windows must be >= 10"):
            WalkForwardConfig(min_expanding_windows=9)

    def test_purge_interval_calculation_skips_weekends(self) -> None:
        """Verify that purge interval calculation accurately steps forward in trading sessions."""
        cal = _generate_trading_calendar(date(2023, 1, 2), 100)  # Starts Mon Jan 2, 2023
        train_end_idx = 10  # 11th trading session

        purge_start, purge_end, purged_dates = compute_purge_interval(cal, train_end_idx, 20)
        assert len(purged_dates) == 20
        assert purge_start == cal[train_end_idx + 1]
        assert purge_end == cal[train_end_idx + 20]
        assert purged_dates == tuple(cal[train_end_idx + 1 : train_end_idx + 21])

        # Purged dates should strictly be weekdays
        for d in purged_dates:
            assert d.weekday() < 5

    def test_embargo_interval_calculation(self) -> None:
        """Verify that post-test embargo interval calculation spans required sessions."""
        cal = _generate_trading_calendar(date(2023, 1, 2), 100)
        test_end_idx = 50

        emb_start, emb_end, emb_dates = compute_embargo_interval(cal, test_end_idx, 5)
        assert len(emb_dates) == 5
        assert emb_start == cal[test_end_idx + 1]
        assert emb_end == cal[test_end_idx + 5]

        # Zero embargo returns empty
        zero_start, zero_end, zero_dates = compute_embargo_interval(cal, test_end_idx, 0)
        assert zero_start is None
        assert zero_end is None
        assert zero_dates == ()

    def test_mathematical_zero_label_leakage_verification_20d(self) -> None:
        """Verify mathematical assertion of zero label leakage for 20d target."""
        cal = _generate_trading_calendar(date(2023, 1, 2), 100)
        # Train: indices 0..20 (21 sessions)
        train_dates = cal[0:21]
        last_train_idx = 20

        # Exact boundary success: test starts at index 20 + 20 + 1 = 41
        valid_test_dates = cal[41:61]
        assert verify_zero_label_leakage(train_dates, valid_test_dates, 20, cal) is True

        # One session short (index 40) causes label leakage
        invalid_test_dates = cal[40:60]
        with pytest.raises(ValidationLeakageError, match=r"\[LABEL LEAKAGE\]"):
            verify_zero_label_leakage(train_dates, invalid_test_dates, 20, cal)

        # Same session or overlapping dates causes set leakage
        overlapping_test_dates = cal[20:40]
        with pytest.raises(ValidationLeakageError):
            verify_zero_label_leakage(train_dates, overlapping_test_dates, 20, cal)

    def test_mathematical_zero_label_leakage_verification_60d(self) -> None:
        """Verify mathematical assertion of zero label leakage for 60d target."""
        cal = _generate_trading_calendar(date(2023, 1, 2), 200)
        train_dates = cal[0:50]
        last_train_idx = 49

        # Exact boundary success: test starts at index 49 + 60 + 1 = 110
        valid_test_dates = cal[110:140]
        assert verify_zero_label_leakage(train_dates, valid_test_dates, 60, cal) is True

        # One session short (index 109) causes label leakage
        invalid_test_dates = cal[109:140]
        with pytest.raises(ValidationLeakageError, match=r"\[LABEL LEAKAGE\]"):
            verify_zero_label_leakage(train_dates, invalid_test_dates, 60, cal)

    def test_build_purge_embargo_interval_immutability_and_hash(self) -> None:
        """Verify that PurgeEmbargoInterval produces deterministic hash and immutable record."""
        cal = _generate_trading_calendar(date(2023, 1, 2), 100)
        interval = build_purge_embargo_interval(
            fold_index=0,
            trading_calendar=cal,
            train_end_idx=20,
            test_start_idx=41,
            test_end_idx=60,
            purge_days=20,
            embargo_days=5,
        )

        assert interval.fold_index == 0
        assert interval.purge_trading_days == 20
        assert interval.test_trading_days == 20
        assert interval.embargo_trading_days == 5
        assert interval.interval_hash != ""

        # Deterministic hashing: recreating identical interval produces identical hash
        interval2 = build_purge_embargo_interval(
            fold_index=0,
            trading_calendar=cal,
            train_end_idx=20,
            test_start_idx=41,
            test_end_idx=60,
            purge_days=20,
            embargo_days=5,
        )
        assert interval.interval_hash == interval2.interval_hash

        # Insufficient purge gap fails
        with pytest.raises(ValidationLeakageError, match="requires >= 20"):
            build_purge_embargo_interval(
                fold_index=0,
                trading_calendar=cal,
                train_end_idx=20,
                test_start_idx=40,  # gap is 19
                test_end_idx=60,
                purge_days=20,
                embargo_days=5,
            )
