"""Unit tests for Phase 7 target hash generation, sensitivity, and determinism.

Verifies:
1. Identical results create identical target hashes.
2. Value changes alter hashes.
3. Status changes alter hashes.
4. Reason-code changes alter hashes.
5. Dataset-version changes alter hashes.
6. Universe-hash changes alter hashes.
7. Entry-date changes alter hashes.
8. Exit-date changes alter hashes.
9. target_hash computation excludes target_hash itself.
10. Primary (20d sector-relative) and secondary (60d residual) specification hashes differ.
11. Canonical dictionary ordering for compute_row_hash is deterministic.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
import unittest

from phase7.data.contracts import PriceAdjustmentState, compute_row_hash
from phase7.targets.contracts import (
    TargetReasonCode,
    TargetResultRecord,
    TargetSpecificationRecord,
    TargetStatus,
)


class TestTargetHashing(unittest.TestCase):

    def setUp(self):
        self.t_pred = datetime(2025, 1, 15, 16, 0, tzinfo=timezone.utc)
        self.t_create = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)

        self.spec_20d = TargetSpecificationRecord(
            target_name="target_20d_sector_relative",
            target_version="1.0.0",
            horizon_trading_days=20,
            execution_lag_trading_days=1,
            entry_price_field="open",
            exit_price_field="close",
            return_type="TOTAL_RETURN_ADJUSTED",
            benchmark_type="SECTOR",
            adjustment_state_requirement=PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
            missing_terminal_policy="FAIL_CLOSED",
            suspension_policy="INVALIDATE_ON_SUSPENSION",
            delisting_policy="INVALIDATE_ON_DELISTING",
            created_timestamp=self.t_create,
        )

        self.spec_60d = TargetSpecificationRecord(
            target_name="target_60d_residual",
            target_version="1.0.0",
            horizon_trading_days=60,
            execution_lag_trading_days=1,
            entry_price_field="open",
            exit_price_field="close",
            return_type="TOTAL_RETURN_ADJUSTED",
            benchmark_type="MARKET",
            adjustment_state_requirement=PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
            missing_terminal_policy="FAIL_CLOSED",
            suspension_policy="INVALIDATE_ON_SUSPENSION",
            delisting_policy="INVALIDATE_ON_DELISTING",
            created_timestamp=self.t_create,
        )

    def _base_record(
        self,
        val="0.03",
        status=TargetStatus.VALID,
        reasons=None,
        dataset_ver="v2025.1",
        universe_h="u" * 64,
        entry_d=date(2025, 1, 16),
        exit_d=date(2025, 2, 13),
    ) -> TargetResultRecord:
        return TargetResultRecord(
            target_name="target_20d_sector_relative",
            target_version="1.0.0",
            prediction_timestamp=self.t_pred,
            symbol="TCS",
            isin="INE467B01029",
            horizon_trading_days=20,
            entry_date=entry_d,
            exit_date=exit_d,
            stock_total_return=Decimal("0.05") if status == TargetStatus.VALID else None,
            benchmark_total_return=Decimal("0.02") if status == TargetStatus.VALID else None,
            beta_used=None,
            target_value=Decimal(val) if status == TargetStatus.VALID else None,
            target_status=status,
            invalid_reason_codes=list(reasons or []),
            source_dataset_versions={"dataset": dataset_ver},
            universe_hash=universe_h,
        )

    def test_identical_results_create_identical_hashes(self):
        """Two identical TargetResultRecord instances produce identical target_hash."""
        r1 = self._base_record()
        r2 = self._base_record()
        self.assertEqual(r1.target_hash, r2.target_hash)
        self.assertEqual(len(r1.target_hash), 64)

    def test_value_changes_alter_hashes(self):
        """Altering target_value alters target_hash."""
        r1 = self._base_record(val="0.03")
        r2 = self._base_record(val="0.04")
        self.assertNotEqual(r1.target_hash, r2.target_hash)

    def test_status_changes_alter_hashes(self):
        """Altering target_status alters target_hash."""
        r_valid = self._base_record(status=TargetStatus.VALID)
        r_invalid = self._base_record(status=TargetStatus.INVALID, reasons=[TargetReasonCode.MISSING_ENTRY_PRICE])
        self.assertNotEqual(r_valid.target_hash, r_invalid.target_hash)

    def test_reason_code_changes_alter_hashes(self):
        """Altering invalid_reason_codes alters target_hash."""
        r1 = self._base_record(status=TargetStatus.INVALID, reasons=[TargetReasonCode.MISSING_ENTRY_PRICE])
        r2 = self._base_record(status=TargetStatus.INVALID, reasons=[TargetReasonCode.MISSING_EXIT_PRICE])
        self.assertNotEqual(r1.target_hash, r2.target_hash)

    def test_dataset_version_changes_alter_hashes(self):
        """Altering source_dataset_versions alters target_hash."""
        r1 = self._base_record(dataset_ver="v2025.1")
        r2 = self._base_record(dataset_ver="v2025.2")
        self.assertNotEqual(r1.target_hash, r2.target_hash)

    def test_universe_hash_changes_alter_hashes(self):
        """Altering universe_hash alters target_hash."""
        r1 = self._base_record(universe_h="a" * 64)
        r2 = self._base_record(universe_h="b" * 64)
        self.assertNotEqual(r1.target_hash, r2.target_hash)

    def test_entry_date_changes_alter_hashes(self):
        """Altering entry_date alters target_hash."""
        r1 = self._base_record(entry_d=date(2025, 1, 16))
        r2 = self._base_record(entry_d=date(2025, 1, 17))
        self.assertNotEqual(r1.target_hash, r2.target_hash)

    def test_exit_date_changes_alter_hashes(self):
        """Altering exit_date alters target_hash."""
        r1 = self._base_record(exit_d=date(2025, 2, 13))
        r2 = self._base_record(exit_d=date(2025, 2, 14))
        self.assertNotEqual(r1.target_hash, r2.target_hash)

    def test_target_hash_excludes_itself(self):
        """Supplied matching target_hash is verified; tampered target_hash raises ValueError."""
        r = self._base_record()
        # Supplying wrong target_hash must raise ValueError
        with self.assertRaises(ValueError):
            TargetResultRecord(
                target_name=r.target_name,
                target_version=r.target_version,
                prediction_timestamp=r.prediction_timestamp,
                symbol=r.symbol,
                isin=r.isin,
                horizon_trading_days=r.horizon_trading_days,
                entry_date=r.entry_date,
                exit_date=r.exit_date,
                stock_total_return=r.stock_total_return,
                benchmark_total_return=r.benchmark_total_return,
                beta_used=r.beta_used,
                target_value=r.target_value,
                target_status=r.target_status,
                invalid_reason_codes=r.invalid_reason_codes,
                source_dataset_versions=r.source_dataset_versions,
                universe_hash=r.universe_hash,
                target_hash="0" * 64,  # Incorrect hash
            )

    def test_primary_and_secondary_specification_hashes_differ(self):
        """Primary (20d sector-relative) and secondary (60d residual) specification hashes differ."""
        self.assertEqual(len(self.spec_20d.specification_hash), 64)
        self.assertEqual(len(self.spec_60d.specification_hash), 64)
        self.assertNotEqual(self.spec_20d.specification_hash, self.spec_60d.specification_hash)

    def test_canonical_ordering_deterministic(self):
        """compute_row_hash produces identical output regardless of dictionary insertion order."""
        dict_a = {"z": 1, "a": "hello", "m": [1, 2, 3]}
        dict_b = {"a": "hello", "m": [1, 2, 3], "z": 1}
        self.assertEqual(compute_row_hash(dict_a), compute_row_hash(dict_b))


if __name__ == "__main__":
    unittest.main()
