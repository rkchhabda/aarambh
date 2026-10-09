"""Unit tests for Phase 7 target audit reporting and zero investment performance invariance.

Verifies:
1. Valid targets increment accepted_target_count.
2. Invalid targets increment rejected_target_count.
3. Blocked targets increment blocked_target_count.
4. Records are never silently discarded (input_record_count == accepted + rejected + blocked).
5. Future beta detection increments BOTH future_data_count AND invalid_beta_count.
6. Missing entry price and missing exit price are counted in distinct buckets.
7. Suspension and delisting are counted in distinct buckets.
8. Manual review corporate actions are counted (corporate_action_review_count).
9. Missing benchmarks are counted (missing_benchmark_count).
10. Forward window overlaps are accurately counted (overlap_count).
11. Deterministic SHA-256 audit_hash generation.
12. Material count alterations change audit_hash.
13. Strict absence of investment performance or alpha metrics in audit dictionary.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
import unittest

from phase7.data.contracts import PriceAdjustmentState
from phase7.targets.audit import audit_target_results
from phase7.targets.contracts import (
    TargetAuditRecord,
    TargetReasonCode,
    TargetResultRecord,
    TargetSpecificationRecord,
    TargetStatus,
)


class TestTargetAudit(unittest.TestCase):

    def setUp(self):
        self.t_create = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
        self.t_pred = datetime(2025, 1, 15, 16, 0, tzinfo=timezone.utc)
        self.spec = TargetSpecificationRecord(
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

    def _make_result(
        self,
        status: TargetStatus,
        reasons=None,
        entry_d=None,
        exit_d=None,
        val=None,
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
            stock_total_return=val if status == TargetStatus.VALID else None,
            benchmark_total_return=Decimal("0.01") if status == TargetStatus.VALID else None,
            beta_used=None,
            target_value=val if status == TargetStatus.VALID else None,
            target_status=status,
            invalid_reason_codes=list(reasons or []),
            universe_hash="u" * 64,
        )

    def test_accepted_rejected_blocked_counts_and_conservation(self):
        """Input records are conserved across accepted, rejected, and blocked counts."""
        r_valid = self._make_result(TargetStatus.VALID, entry_d=date(2025, 1, 16), exit_d=date(2025, 2, 13), val=Decimal("0.05"))
        r_invalid = self._make_result(TargetStatus.INVALID, reasons=[TargetReasonCode.MISSING_ENTRY_PRICE])
        r_blocked = self._make_result(TargetStatus.BLOCKED, reasons=[TargetReasonCode.MISSING_PIT_SECTOR])

        audit = audit_target_results(
            specification=self.spec,
            results=[r_valid, r_invalid, r_blocked],
            input_record_count=3,
        )

        self.assertEqual(audit.input_record_count, 3)
        self.assertEqual(audit.accepted_target_count, 1)
        self.assertEqual(audit.rejected_target_count, 1)
        self.assertEqual(audit.blocked_target_count, 1)
        # Verify no silent discard
        self.assertEqual(
            audit.accepted_target_count + audit.rejected_target_count + audit.blocked_target_count,
            audit.input_record_count,
        )

    def test_future_beta_dual_counting(self):
        """FUTURE_BETA_DETECTED increments both future_data_count and invalid_beta_count."""
        r_future_beta = self._make_result(TargetStatus.INVALID, reasons=[TargetReasonCode.FUTURE_BETA_DETECTED])

        audit = audit_target_results(
            specification=self.spec,
            results=[r_future_beta],
            input_record_count=1,
        )

        self.assertEqual(audit.future_data_count, 1)
        self.assertEqual(audit.invalid_beta_count, 1)

    def test_missing_entry_and_exit_are_separate(self):
        """Missing entry and missing exit are tracked in distinct count fields."""
        r_entry = self._make_result(TargetStatus.INVALID, reasons=[TargetReasonCode.MISSING_ENTRY_PRICE])
        r_exit = self._make_result(TargetStatus.INVALID, reasons=[TargetReasonCode.MISSING_EXIT_PRICE])

        audit = audit_target_results(
            specification=self.spec,
            results=[r_entry, r_exit],
            input_record_count=2,
        )

        self.assertEqual(audit.missing_entry_count, 1)
        self.assertEqual(audit.missing_exit_count, 1)

    def test_suspension_and_delisting_are_separate(self):
        """Suspension and delisting are tracked in distinct count fields."""
        r_susp = self._make_result(TargetStatus.INVALID, reasons=[TargetReasonCode.SUSPENDED_DURING_HORIZON])
        r_delist = self._make_result(TargetStatus.INVALID, reasons=[TargetReasonCode.DELISTED_DURING_HORIZON])

        audit = audit_target_results(
            specification=self.spec,
            results=[r_susp, r_delist],
            input_record_count=2,
        )

        self.assertEqual(audit.suspension_count, 1)
        self.assertEqual(audit.delisting_count, 1)

    def test_corporate_action_review_and_missing_benchmark_counted(self):
        """Manual corporate action reviews and missing benchmarks are accurately aggregated."""
        r_corp = self._make_result(TargetStatus.INVALID, reasons=[TargetReasonCode.CORPORATE_ACTION_REVIEW_REQUIRED])
        r_bench = self._make_result(TargetStatus.INVALID, reasons=[TargetReasonCode.MISSING_BENCHMARK])

        audit = audit_target_results(
            specification=self.spec,
            results=[r_corp, r_bench],
            input_record_count=2,
        )

        self.assertEqual(audit.corporate_action_review_count, 1)
        self.assertEqual(audit.missing_benchmark_count, 1)

    def test_overlap_counting(self):
        """Overlapping forward holding intervals increment overlap_count."""
        r1 = self._make_result(TargetStatus.VALID, entry_d=date(2025, 1, 2), exit_d=date(2025, 1, 25), val=Decimal("0.05"))
        r2 = self._make_result(TargetStatus.VALID, entry_d=date(2025, 1, 15), exit_d=date(2025, 2, 5), val=Decimal("0.03"))

        audit = audit_target_results(
            specification=self.spec,
            results=[r1, r2],
            input_record_count=2,
        )

        self.assertEqual(audit.overlap_count, 1)

    def test_audit_hash_deterministic_and_sensitive_to_count_changes(self):
        """Audit hash is deterministic and changes upon material count differences."""
        r1 = self._make_result(TargetStatus.VALID, entry_d=date(2025, 1, 2), exit_d=date(2025, 1, 25), val=Decimal("0.05"))
        r2 = self._make_result(TargetStatus.INVALID, reasons=[TargetReasonCode.MISSING_ENTRY_PRICE])

        audit_a = audit_target_results(self.spec, [r1], input_record_count=1)
        audit_b = audit_target_results(self.spec, [r1], input_record_count=1)
        audit_c = audit_target_results(self.spec, [r1, r2], input_record_count=2)

        self.assertEqual(audit_a.audit_hash, audit_b.audit_hash)
        self.assertEqual(len(audit_a.audit_hash), 64)
        self.assertNotEqual(audit_a.audit_hash, audit_c.audit_hash)

    def test_strict_zero_investment_performance_metrics(self):
        """TargetAuditRecord to_dict contains zero alpha or performance metrics."""
        audit = audit_target_results(self.spec, [], input_record_count=0)
        report = audit.to_dict()

        forbidden_metrics = {
            "sharpe", "sortino", "alpha", "drawdown", "max_drawdown",
            "ic", "rank_ic", "calmar", "win_rate", "hit_rate", "pnl", "cagr"
        }
        for k in report.keys():
            k_lower = k.lower()
            tokens = set(k_lower.split("_"))
            for f in forbidden_metrics:
                self.assertNotIn(f, tokens, f"Forbidden metric token '{f}' found in audit key '{k}'!")
                if f in ("sharpe", "sortino", "alpha", "drawdown", "calmar", "cagr"):
                    self.assertNotIn(f, k_lower, f"Forbidden metric substring '{f}' found in audit key '{k}'!")


if __name__ == "__main__":
    unittest.main()
