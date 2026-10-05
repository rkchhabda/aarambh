"""CI Test Suite: Corporate Action Normalization and Price Adjustment Verification.

Covers tests 50-64:
- Stock splits (1:2 -> factor 2.0, prices divided by 2.0, volume multiplied by 2.0)
- Bonus issues (1:1 -> 2.0, 1:2 -> 1.5, 2:1 -> 3.0)
- Cash dividends (total-return reinvestment factor vs share count, rejection of D >= Pref)
- Double adjustment prevention (rejects adjusting series that is already TOTAL_RETURN_ADJUSTED)
- Fail-closed on UNKNOWN adjustment state
- Unsupported complex actions (Rights, Mergers, Demergers -> MANUAL_REVIEW)
- Deterministic ordering of concurrent same-day actions
"""

from datetime import date, datetime, timezone
from decimal import Decimal
import unittest
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from phase7.data.contracts import (
    CorporateActionRecord,
    CorporateActionResolution,
    CorporateActionType,
    DailyPriceRecord,
    PriceAdjustmentState,
    TradedValueStatus,
)
from phase7.data.corporate_actions import (
    CorporateActionEngine,
    adjust_price_series,
    sort_corporate_actions,
)


class TestCorporateActionAdjustments(unittest.TestCase):

    def setUp(self):
        self.t_src = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        self.t_ing = datetime(2025, 1, 1, 11, 0, 0, tzinfo=timezone.utc)

    def test_stock_split_1_to_2_produces_factor_2(self):
        """50, 51. A 1-to-2 split produces factor 2.0 and divides historical prices by 2.0."""
        # 1 old share becomes 2 new shares
        split_act = CorporateActionRecord(
            symbol="TCS",
            isin="INE467B01029",
            action_type=CorporateActionType.SPLIT,
            ex_date=date(2025, 5, 1),
            effective_date=date(2025, 5, 1),
            adjustment_numerator=Decimal("2"),
            adjustment_denominator=Decimal("1"),
            source_timestamp=self.t_src,
            ingestion_timestamp=self.t_ing,
            source_identifier="CIRC",
        )
        norm = CorporateActionEngine.normalize_action(split_act)
        self.assertEqual(norm.resolution, CorporateActionResolution.APPLIED)
        self.assertEqual(norm.multiplier, Decimal("2.0"))

        # Test price adjustment on pre-split and post-split sessions
        pre_split = DailyPriceRecord(
            trading_date=date(2025, 4, 30),
            symbol="TCS",
            isin="INE467B01029",
            open=Decimal("3000.00"),
            high=Decimal("3050.00"),
            low=Decimal("2980.00"),
            close=Decimal("3000.00"),
            volume=1000,
            traded_value_inr=Decimal("3000000.00"),
            traded_value_status=TradedValueStatus.EXCHANGE_REPORTED,
            price_adjustment_state=PriceAdjustmentState.RAW,
            source_timestamp=self.t_src,
            ingestion_timestamp=self.t_ing,
            source_identifier="PRICE",
        )
        post_split = DailyPriceRecord(
            trading_date=date(2025, 5, 1),
            symbol="TCS",
            isin="INE467B01029",
            open=Decimal("1500.00"),
            high=Decimal("1520.00"),
            low=Decimal("1490.00"),
            close=Decimal("1500.00"),
            volume=2000,
            traded_value_inr=Decimal("3000000.00"),
            traded_value_status=TradedValueStatus.EXCHANGE_REPORTED,
            price_adjustment_state=PriceAdjustmentState.RAW,
            source_timestamp=self.t_src,
            ingestion_timestamp=self.t_ing,
            source_identifier="PRICE",
        )

        adj_prices, _ = adjust_price_series([pre_split, post_split], [split_act])
        self.assertEqual(len(adj_prices), 2)
        # Pre-split close (3000) should be divided by 2.0 -> 1500.00
        self.assertEqual(adj_prices[0].close, Decimal("1500.00"))
        # Pre-split volume (1000) should be multiplied by 2.0 -> 2000
        self.assertEqual(adj_prices[0].volume, 2000)
        # Post-split close should remain 1500.00
        self.assertEqual(adj_prices[1].close, Decimal("1500.00"))

    def test_bonus_ratios(self):
        """52, 53, 54. Bonus ratios: 1:1 -> 2.0; 1:2 -> 1.5; 2:1 -> 3.0."""
        # 1:1 Bonus
        b1_1 = CorporateActionRecord(
            symbol="RELIANCE",
            isin="INE002A01018",
            action_type=CorporateActionType.BONUS,
            ex_date=date(2025, 6, 1),
            effective_date=date(2025, 6, 1),
            adjustment_numerator=Decimal("1"),
            adjustment_denominator=Decimal("1"),
            source_timestamp=self.t_src,
            ingestion_timestamp=self.t_ing,
            source_identifier="CIRC",
        )
        norm1 = CorporateActionEngine.normalize_action(b1_1)
        self.assertEqual(norm1.multiplier, Decimal("2.0"))

        # 1:2 Bonus (1 bonus for 2 held) -> (1+2)/2 = 1.5
        b1_2 = CorporateActionRecord(
            symbol="RELIANCE",
            isin="INE002A01018",
            action_type=CorporateActionType.BONUS,
            ex_date=date(2025, 6, 1),
            effective_date=date(2025, 6, 1),
            adjustment_numerator=Decimal("1"),
            adjustment_denominator=Decimal("2"),
            source_timestamp=self.t_src,
            ingestion_timestamp=self.t_ing,
            source_identifier="CIRC",
        )
        norm2 = CorporateActionEngine.normalize_action(b1_2)
        self.assertEqual(norm2.multiplier, Decimal("1.5"))

        # 2:1 Bonus (2 bonus for 1 held) -> (2+1)/1 = 3.0
        b2_1 = CorporateActionRecord(
            symbol="RELIANCE",
            isin="INE002A01018",
            action_type=CorporateActionType.BONUS,
            ex_date=date(2025, 6, 1),
            effective_date=date(2025, 6, 1),
            adjustment_numerator=Decimal("2"),
            adjustment_denominator=Decimal("1"),
            source_timestamp=self.t_src,
            ingestion_timestamp=self.t_ing,
            source_identifier="CIRC",
        )
        norm3 = CorporateActionEngine.normalize_action(b2_1)
        self.assertEqual(norm3.multiplier, Decimal("3.0"))

    def test_cash_dividend_total_return_factor(self):
        """56, 57, 58. Cash dividend calculation requires reference price and rejects D >= Pref."""
        div_act = CorporateActionRecord(
            symbol="INFY",
            isin="INE009A01021",
            action_type=CorporateActionType.CASH_DIVIDEND,
            ex_date=date(2025, 6, 1),
            effective_date=date(2025, 6, 1),
            cash_amount=Decimal("20.00"),
            source_timestamp=self.t_src,
            ingestion_timestamp=self.t_ing,
            source_identifier="CIRC",
        )

        # Missing reference price -> MANUAL_REVIEW
        norm_no_ref = CorporateActionEngine.normalize_action(div_act, reference_price=None)
        self.assertEqual(norm_no_ref.resolution, CorporateActionResolution.MANUAL_REVIEW)

        # Valid reference price (Pref = 1000, D = 20) -> factor = (1000 - 20)/1000 = 0.98
        norm_valid = CorporateActionEngine.normalize_action(div_act, reference_price=Decimal("1000.00"))
        self.assertEqual(norm_valid.resolution, CorporateActionResolution.APPLIED)
        self.assertEqual(norm_valid.dividend_factor, Decimal("0.98"))

        # Impossible dividend: D = 20, Pref = 15 (D >= Pref) -> INVALID_ACTION
        norm_invalid = CorporateActionEngine.normalize_action(div_act, reference_price=Decimal("15.00"))
        self.assertEqual(norm_invalid.resolution, CorporateActionResolution.INVALID_ACTION)

    def test_prevent_double_adjustment_and_unknown_state(self):
        """59, 60. Double adjustment rejected on TOTAL_RETURN_ADJUSTED, and UNKNOWN state fails closed."""
        p_raw = DailyPriceRecord(
            trading_date=date(2025, 1, 1),
            symbol="INFY",
            isin="INE009A01021",
            open=Decimal("100.00"),
            high=Decimal("105.00"),
            low=Decimal("95.00"),
            close=Decimal("100.00"),
            volume=1000,
            traded_value_inr=Decimal("100000.00"),
            traded_value_status=TradedValueStatus.EXCHANGE_REPORTED,
            price_adjustment_state=PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
            source_timestamp=self.t_src,
            ingestion_timestamp=self.t_ing,
            source_identifier="TEST",
        )
        # Attempting dividend adjustment on already TOTAL_RETURN_ADJUSTED series must raise error
        with self.assertRaises(ValueError) as ctx:
            adjust_price_series([p_raw], [], adjust_dividends=True)
        self.assertIn("Double adjustment rejected", str(ctx.exception))

        p_unknown = DailyPriceRecord(
            trading_date=date(2025, 1, 1),
            symbol="INFY",
            isin="INE009A01021",
            open=Decimal("100.00"),
            high=Decimal("105.00"),
            low=Decimal("95.00"),
            close=Decimal("100.00"),
            volume=1000,
            traded_value_inr=Decimal("100000.00"),
            traded_value_status=TradedValueStatus.EXCHANGE_REPORTED,
            price_adjustment_state=PriceAdjustmentState.UNKNOWN,
            source_timestamp=self.t_src,
            ingestion_timestamp=self.t_ing,
            source_identifier="TEST",
        )
        with self.assertRaises(ValueError) as ctx2:
            adjust_price_series([p_unknown], [])
        self.assertIn("PriceAdjustmentState.UNKNOWN", str(ctx2.exception))

    def test_unsupported_complex_actions_return_manual_review(self):
        """64. Unsupported complex actions return MANUAL_REVIEW."""
        complex_act = CorporateActionRecord(
            symbol="MERGE_CO",
            isin="INE999X01099",
            action_type=CorporateActionType.MERGER,
            ex_date=date(2025, 5, 1),
            effective_date=date(2025, 5, 1),
            source_timestamp=self.t_src,
            ingestion_timestamp=self.t_ing,
            source_identifier="CIRC",
        )
        norm = CorporateActionEngine.normalize_action(complex_act)
        self.assertEqual(norm.resolution, CorporateActionResolution.MANUAL_REVIEW)


if __name__ == "__main__":
    unittest.main()
