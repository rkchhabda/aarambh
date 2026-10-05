"""Corporate action normalization, validation, and price adjustment engine for Phase 7.

Implements deterministic corporate-action calculations for:
1. Stock Splits (share-count multiplier and backward price division).
2. Bonus Issues (e.g., 1:1 -> 2.0, 1:2 -> 1.5, 2:1 -> 3.0).
3. Cash Dividends (Total-Return adjustments requiring positive reference prices).
4. Deterministic ordering of concurrent same-day actions.
5. Explicit fail-closed routing for unsupported complex corporate actions (Rights, Mergers, Demergers).
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Sequence, Tuple

from phase7.data.contracts import (
    CorporateActionRecord,
    CorporateActionResolution,
    CorporateActionType,
    DailyPriceRecord,
    PriceAdjustmentState,
)


@dataclass(frozen=True)
class NormalizedCorporateAction:
    """Normalized corporate action with calculated multiplier and resolution status."""
    record: CorporateActionRecord
    resolution: CorporateActionResolution
    multiplier: Decimal
    dividend_factor: Optional[Decimal] = None
    note: str = ""


# Priority ordering for multiple same-date actions: SPLIT -> BONUS -> CASH_DIVIDEND
ACTION_EXECUTION_ORDER = {
    CorporateActionType.SPLIT: 1,
    CorporateActionType.BONUS: 2,
    CorporateActionType.CASH_DIVIDEND: 3,
    CorporateActionType.RIGHTS: 4,
    CorporateActionType.MERGER: 5,
    CorporateActionType.DEMERGER: 6,
    CorporateActionType.SYMBOL_CHANGE: 7,
    CorporateActionType.DELISTING: 8,
}


class CorporateActionEngine:
    """Deterministic corporate-action normalization and factor calculation engine."""

    @staticmethod
    def normalize_action(
        action: CorporateActionRecord,
        reference_price: Optional[Decimal] = None,
    ) -> NormalizedCorporateAction:
        """Normalize a single corporate action into a validated factor multiplier.

        Args:
            action: The canonical corporate action record.
            reference_price: The pre-ex-date reference price (mandatory for cash dividends).

        Returns:
            NormalizedCorporateAction containing resolved multiplier or manual review flag.
        """
        # Complex actions requiring manual review
        if action.action_type in (
            CorporateActionType.RIGHTS,
            CorporateActionType.MERGER,
            CorporateActionType.DEMERGER,
            CorporateActionType.SYMBOL_CHANGE,
            CorporateActionType.DELISTING,
        ):
            return NormalizedCorporateAction(
                record=action,
                resolution=CorporateActionResolution.MANUAL_REVIEW,
                multiplier=Decimal("1.0"),
                note=f"Complex action type '{action.action_type.value}' requires manual governance review.",
            )

        # 1. Stock Split: numerator new shares for denominator old shares
        if action.action_type == CorporateActionType.SPLIT:
            num = action.adjustment_numerator
            den = action.adjustment_denominator
            if num is None or den is None or num <= Decimal("0") or den <= Decimal("0"):
                return NormalizedCorporateAction(
                    record=action,
                    resolution=CorporateActionResolution.INVALID_ACTION,
                    multiplier=Decimal("1.0"),
                    note="Invalid split numerator or denominator.",
                )
            # Factor by which share count increases (e.g. 1-to-2 split: 2/1 = 2.0)
            factor = num / den
            return NormalizedCorporateAction(
                record=action,
                resolution=CorporateActionResolution.APPLIED,
                multiplier=factor,
                note=f"Stock split factor: {factor} (new/old = {num}/{den})",
            )

        # 2. Bonus Issue: numerator bonus shares issued for denominator held shares
        if action.action_type == CorporateActionType.BONUS:
            num = action.adjustment_numerator
            den = action.adjustment_denominator
            if num is None or den is None or num <= Decimal("0") or den <= Decimal("0"):
                return NormalizedCorporateAction(
                    record=action,
                    resolution=CorporateActionResolution.INVALID_ACTION,
                    multiplier=Decimal("1.0"),
                    note="Invalid bonus numerator or denominator.",
                )
            # Factor = (num + den) / den
            # e.g. 1:1 bonus -> (1+1)/1 = 2.0; 1:2 bonus -> (1+2)/2 = 1.5; 2:1 bonus -> (2+1)/1 = 3.0
            factor = (num + den) / den
            return NormalizedCorporateAction(
                record=action,
                resolution=CorporateActionResolution.APPLIED,
                multiplier=factor,
                note=f"Bonus issue factor: {factor} ((bonus+held)/held = ({num}+{den})/{den})",
            )

        # 3. Cash Dividend: Total return reinvestment factor
        if action.action_type == CorporateActionType.CASH_DIVIDEND:
            div_amount = action.cash_amount
            if div_amount is None or div_amount <= Decimal("0"):
                return NormalizedCorporateAction(
                    record=action,
                    resolution=CorporateActionResolution.INVALID_ACTION,
                    multiplier=Decimal("1.0"),
                    note="Invalid cash dividend amount.",
                )
            if reference_price is None or reference_price <= Decimal("0"):
                return NormalizedCorporateAction(
                    record=action,
                    resolution=CorporateActionResolution.MANUAL_REVIEW,
                    multiplier=Decimal("1.0"),
                    note="Cash dividend total return calculation requires positive pre-ex reference price.",
                )
            if div_amount >= reference_price:
                return NormalizedCorporateAction(
                    record=action,
                    resolution=CorporateActionResolution.INVALID_ACTION,
                    multiplier=Decimal("1.0"),
                    note=f"Dividend amount ({div_amount}) >= reference price ({reference_price}).",
                )
            # Total return price factor: (P_ref - D) / P_ref
            div_factor = (reference_price - div_amount) / reference_price
            return NormalizedCorporateAction(
                record=action,
                resolution=CorporateActionResolution.APPLIED,
                multiplier=Decimal("1.0"),
                dividend_factor=div_factor,
                note=f"Cash dividend total return factor: {div_factor} (D={div_amount}, Pref={reference_price})",
            )

        return NormalizedCorporateAction(
            record=action,
            resolution=CorporateActionResolution.UNSUPPORTED_ACTION,
            multiplier=Decimal("1.0"),
            note=f"Unsupported action: {action.action_type}",
        )


def sort_corporate_actions(actions: Sequence[CorporateActionRecord]) -> List[CorporateActionRecord]:
    """Sort corporate actions deterministically by ex_date ascending, then execution priority, then row_hash."""
    return sorted(
        actions,
        key=lambda a: (
            a.ex_date,
            ACTION_EXECUTION_ORDER.get(a.action_type, 99),
            a.row_hash,
        ),
    )


def adjust_price_series(
    prices: Sequence[DailyPriceRecord],
    actions: Sequence[CorporateActionRecord],
    adjust_dividends: bool = False,
) -> Tuple[List[DailyPriceRecord], List[NormalizedCorporateAction]]:
    """Compute backward-adjusted price and volume series using verified corporate actions.

    Rules:
    - Input series must be chronological.
    - If input series is already TOTAL_RETURN_ADJUSTED, further dividend adjustment is rejected.
    - If input series has UNKNOWN adjustment state, adjustment is rejected (fail closed).
    - Pre-ex prices are backward-adjusted:
      For splits/bonuses: P_adj = P_raw / factor, Volume_adj = Volume_raw * factor.
      For dividends: P_adj = P_raw * div_factor.
    """
    if not prices:
        return [], []

    # Verify input adjustment state
    sample_state = prices[0].price_adjustment_state
    if sample_state == PriceAdjustmentState.UNKNOWN:
        raise ValueError("Cannot adjust price series with PriceAdjustmentState.UNKNOWN (fail closed).")
    if sample_state == PriceAdjustmentState.TOTAL_RETURN_ADJUSTED and adjust_dividends:
        raise ValueError("Double adjustment rejected: Series is already PriceAdjustmentState.TOTAL_RETURN_ADJUSTED.")

    # Sort prices chronologically
    sorted_prices = sorted(prices, key=lambda p: p.trading_date)
    date_to_price: Dict[date, DailyPriceRecord] = {p.trading_date: p for p in sorted_prices}
    sorted_actions = sort_corporate_actions(actions)

    normalized_actions: List[NormalizedCorporateAction] = []

    # Map each ex_date to normalized actions
    for act in sorted_actions:
        ref_price: Optional[Decimal] = None
        if act.action_type == CorporateActionType.CASH_DIVIDEND:
            # Find closest trading day strictly before ex_date
            prior_dates = [d for d in date_to_price if d < act.ex_date]
            if prior_dates:
                last_prior_date = max(prior_dates)
                ref_price = date_to_price[last_prior_date].close

        norm = CorporateActionEngine.normalize_action(act, reference_price=ref_price)
        normalized_actions.append(norm)

    # Calculate cumulative factors for each trading day
    # Pre-ex-date days receive the compounding factor of all subsequent actions
    adjusted_records: List[DailyPriceRecord] = []

    for p in sorted_prices:
        cum_split_factor = Decimal("1.0")
        cum_div_factor = Decimal("1.0")

        for norm in normalized_actions:
            if norm.resolution != CorporateActionResolution.APPLIED:
                continue
            # Action applies backward to all dates strictly before ex_date
            if p.trading_date < norm.record.ex_date:
                if norm.record.action_type in (CorporateActionType.SPLIT, CorporateActionType.BONUS):
                    cum_split_factor *= norm.multiplier
                elif norm.record.action_type == CorporateActionType.CASH_DIVIDEND and adjust_dividends:
                    if norm.dividend_factor is not None:
                        cum_div_factor *= norm.dividend_factor

        # Apply adjustments
        # Price division by split factor, multiplication by div factor
        adj_open = (p.open / cum_split_factor) * cum_div_factor
        adj_high = (p.high / cum_split_factor) * cum_div_factor
        adj_low = (p.low / cum_split_factor) * cum_div_factor
        adj_close = (p.close / cum_split_factor) * cum_div_factor
        adj_vol = int(Decimal(p.volume) * cum_split_factor)

        target_state = PriceAdjustmentState.SPLIT_ADJUSTED
        if adjust_dividends:
            target_state = PriceAdjustmentState.TOTAL_RETURN_ADJUSTED

        adj_rec = DailyPriceRecord(
            trading_date=p.trading_date,
            symbol=p.symbol,
            isin=p.isin,
            open=adj_open,
            high=adj_high,
            low=adj_low,
            close=adj_close,
            volume=adj_vol,
            traded_value_inr=p.traded_value_inr,
            traded_value_status=p.traded_value_status,
            price_adjustment_state=target_state,
            source_timestamp=p.source_timestamp,
            ingestion_timestamp=p.ingestion_timestamp,
            source_identifier=f"{p.source_identifier}_ADJUSTED",
            adjusted_close=adj_close,
        )
        adjusted_records.append(adj_rec)

    return adjusted_records, normalized_actions
