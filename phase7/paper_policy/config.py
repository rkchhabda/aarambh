"""Governed Paper Policy Configuration and Parameter Contracts [Milestone 4.14].

Defines immutable, versioned parameter structures for indicators, freshness,
Price/OI classification, opening range, options wall quality, PCR, and paper risk.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

from phase7.paper_policy.constants import (
    PARAMETER_SET_ID,
    PARAMETER_SET_VERSION,
)


@dataclass(frozen=True)
class IndicatorConfig:
    """Versioned technical indicator parameter contracts."""
    sma_periods: Tuple[int, ...] = (20, 50, 200)
    ema_periods: Tuple[int, ...] = (9, 21)
    rsi_period: int = 14
    atr_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    execution_status: str = "BLOCKED_UNTIL_GATE1"

    def validate(self) -> None:
        """Validate indicator parameter consistency."""
        if any(p <= 0 for p in self.sma_periods):
            raise ValueError("All SMA periods must be strictly positive integers")
        if any(p <= 0 for p in self.ema_periods):
            raise ValueError("All EMA periods must be strictly positive integers")
        if self.rsi_period <= 0 or self.atr_period <= 0:
            raise ValueError("RSI and ATR periods must be strictly positive integers")
        if self.macd_fast >= self.macd_slow:
            raise ValueError("MACD fast period must be strictly less than slow period")
        if self.macd_signal <= 0:
            raise ValueError("MACD signal period must be strictly positive")


@dataclass(frozen=True)
class PriceOIConfig:
    """Governed Price/Open-Interest classification thresholds."""
    price_state_threshold_pct: float = 0.25
    oi_state_threshold_pct: float = 2.00
    price_neutral_band_pct: float = 0.10
    oi_neutral_band_pct: float = 1.00

    def validate(self) -> None:
        """Validate Price/OI parameter bounds."""
        if self.price_state_threshold_pct <= 0:
            raise ValueError("price_state_threshold_pct must be strictly positive")
        if self.oi_state_threshold_pct <= 0:
            raise ValueError("oi_state_threshold_pct must be strictly positive")
        if self.price_neutral_band_pct < 0 or self.price_neutral_band_pct >= self.price_state_threshold_pct:
            raise ValueError("price_neutral_band_pct must be >= 0 and < price_state_threshold_pct")
        if self.oi_neutral_band_pct < 0 or self.oi_neutral_band_pct >= self.oi_state_threshold_pct:
            raise ValueError("oi_neutral_band_pct must be >= 0 and < oi_state_threshold_pct")


@dataclass(frozen=True)
class FreshnessConfig:
    """Governed freshness and timestamp boundary contracts."""
    maximum_quote_age_seconds: float = 20.0
    maximum_vwap_age_seconds: float = 30.0
    require_exchange_timestamp: bool = True
    require_same_business_date: bool = True
    reject_future_timestamp: bool = True
    reject_previous_business_date: bool = True
    reject_zero_volume: bool = True

    def validate(self) -> None:
        """Validate freshness contract parameters."""
        if self.maximum_quote_age_seconds <= 0:
            raise ValueError("maximum_quote_age_seconds must be strictly positive")
        if self.maximum_vwap_age_seconds <= 0:
            raise ValueError("maximum_vwap_age_seconds must be strictly positive")


@dataclass(frozen=True)
class OpeningRangeConfig:
    """Governed opening-range evaluation parameters."""
    timezone: str = "Asia/Kolkata"
    start_time: str = "09:15:00"
    end_time: str = "09:30:00"
    completion_buffer_seconds: int = 30
    earliest_evaluation: str = "09:30:30"
    require_finalized_interval: bool = True
    require_positive_volume: bool = True

    def validate(self) -> None:
        """Validate opening-range parameters."""
        if self.completion_buffer_seconds < 0:
            raise ValueError("completion_buffer_seconds must be non-negative")


@dataclass(frozen=True)
class OptionsQualityConfig:
    """Governed options-wall and PCR liquidity contracts."""
    strike_window_pct: float = 15.0
    minimum_open_interest: int = 1000
    minimum_volume: int = 100
    minimum_trade_count: int = 10
    maximum_bid_ask_spread_pct: float = 5.0
    expiry_policy: str = "NEAREST_LIQUID_VALID_EXPIRY"

    def validate(self) -> None:
        """Validate options quality parameters."""
        if self.strike_window_pct <= 0 or self.strike_window_pct > 100.0:
            raise ValueError("strike_window_pct must be between 0 and 100")
        if self.minimum_open_interest < 0 or self.minimum_volume < 0 or self.minimum_trade_count < 0:
            raise ValueError("Minimum liquidity thresholds must be non-negative")
        if self.maximum_bid_ask_spread_pct <= 0:
            raise ValueError("maximum_bid_ask_spread_pct must be strictly positive")


@dataclass(frozen=True)
class PaperRiskConfig:
    """Governed paper-only risk parameters and caps."""
    risk_per_observation_pct: float = 0.25
    maximum_position_pct: float = 5.0
    maximum_sector_exposure_pct: float = 15.0
    maximum_open_observations: int = 5
    minimum_stop_distance_pct: float = 0.75
    maximum_stop_distance_pct: float = 3.50
    maximum_daily_paper_loss_pct: float = 1.00
    maximum_weekly_paper_loss_pct: float = 2.50
    minimum_reward_risk_ratio: float = 1.50

    def validate(self) -> None:
        """Validate risk parameter bounds."""
        if not (0 < self.risk_per_observation_pct <= 5.0):
            raise ValueError("risk_per_observation_pct must be in (0, 5.0]")
        if not (0 < self.maximum_position_pct <= 100.0):
            raise ValueError("maximum_position_pct must be in (0, 100.0]")
        if self.minimum_stop_distance_pct >= self.maximum_stop_distance_pct:
            raise ValueError("minimum_stop_distance_pct must be < maximum_stop_distance_pct")
        if self.minimum_reward_risk_ratio <= 0:
            raise ValueError("minimum_reward_risk_ratio must be strictly positive")
        if self.maximum_open_observations <= 0:
            raise ValueError("maximum_open_observations must be strictly positive")


@dataclass(frozen=True)
class PaperPolicyMasterConfig:
    """Master parameter set integrating all governed policy configurations."""
    parameter_set_id: str = PARAMETER_SET_ID
    parameter_set_version: str = PARAMETER_SET_VERSION
    indicators: IndicatorConfig = field(default_factory=IndicatorConfig)
    price_oi: PriceOIConfig = field(default_factory=PriceOIConfig)
    freshness: FreshnessConfig = field(default_factory=FreshnessConfig)
    opening_range: OpeningRangeConfig = field(default_factory=OpeningRangeConfig)
    options_quality: OptionsQualityConfig = field(default_factory=OptionsQualityConfig)
    paper_risk: PaperRiskConfig = field(default_factory=PaperRiskConfig)

    def validate(self) -> None:
        """Validate the full policy configuration hierarchy."""
        self.indicators.validate()
        self.price_oi.validate()
        self.freshness.validate()
        self.opening_range.validate()
        self.options_quality.validate()
        self.paper_risk.validate()

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary representation."""
        return {
            "parameter_set_id": self.parameter_set_id,
            "parameter_set_version": self.parameter_set_version,
            "indicators": {
                "sma_periods": list(self.indicators.sma_periods),
                "ema_periods": list(self.indicators.ema_periods),
                "rsi_period": self.indicators.rsi_period,
                "atr_period": self.indicators.atr_period,
                "macd": [self.indicators.macd_fast, self.indicators.macd_slow, self.indicators.macd_signal],
                "execution_status": self.indicators.execution_status,
            },
            "price_oi": {
                "price_state_threshold_pct": self.price_oi.price_state_threshold_pct,
                "oi_state_threshold_pct": self.price_oi.oi_state_threshold_pct,
                "price_neutral_band_pct": self.price_oi.price_neutral_band_pct,
                "oi_neutral_band_pct": self.price_oi.oi_neutral_band_pct,
            },
            "freshness": {
                "maximum_quote_age_seconds": self.freshness.maximum_quote_age_seconds,
                "maximum_vwap_age_seconds": self.freshness.maximum_vwap_age_seconds,
                "require_exchange_timestamp": self.freshness.require_exchange_timestamp,
                "require_same_business_date": self.freshness.require_same_business_date,
                "reject_future_timestamp": self.freshness.reject_future_timestamp,
                "reject_previous_business_date": self.freshness.reject_previous_business_date,
                "reject_zero_volume": self.freshness.reject_zero_volume,
            },
            "opening_range": {
                "timezone": self.opening_range.timezone,
                "start_time": self.opening_range.start_time,
                "end_time": self.opening_range.end_time,
                "completion_buffer_seconds": self.opening_range.completion_buffer_seconds,
                "earliest_evaluation": self.opening_range.earliest_evaluation,
                "require_finalized_interval": self.opening_range.require_finalized_interval,
                "require_positive_volume": self.opening_range.require_positive_volume,
            },
            "options_quality": {
                "strike_window_pct": self.options_quality.strike_window_pct,
                "minimum_open_interest": self.options_quality.minimum_open_interest,
                "minimum_volume": self.options_quality.minimum_volume,
                "minimum_trade_count": self.options_quality.minimum_trade_count,
                "maximum_bid_ask_spread_pct": self.options_quality.maximum_bid_ask_spread_pct,
                "expiry_policy": self.options_quality.expiry_policy,
            },
            "paper_risk": {
                "risk_per_observation_pct": self.paper_risk.risk_per_observation_pct,
                "maximum_position_pct": self.paper_risk.maximum_position_pct,
                "maximum_sector_exposure_pct": self.paper_risk.maximum_sector_exposure_pct,
                "maximum_open_observations": self.paper_risk.maximum_open_observations,
                "minimum_stop_distance_pct": self.paper_risk.minimum_stop_distance_pct,
                "maximum_stop_distance_pct": self.paper_risk.maximum_stop_distance_pct,
                "maximum_daily_paper_loss_pct": self.paper_risk.maximum_daily_paper_loss_pct,
                "maximum_weekly_paper_loss_pct": self.paper_risk.maximum_weekly_paper_loss_pct,
                "minimum_reward_risk_ratio": self.paper_risk.minimum_reward_risk_ratio,
            },
        }
