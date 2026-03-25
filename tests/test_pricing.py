"""Tests for the GS tax (grunnrenteskatt) price adjustment module."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from nexa_mfrr_eam import (
    Bid,
    BiddingZone,
    Direction,
    MARIMode,
    MarketProductType,
    gs_adjust_bids,
    gs_adjusted_price,
)

MTU_1 = datetime(2026, 3, 21, 10, 0, tzinfo=UTC)
MTU_2 = datetime(2026, 3, 21, 10, 15, tzinfo=UTC)
MTU_3 = datetime(2026, 3, 21, 10, 30, tzinfo=UTC)


def _up_bid(price: float, mtu: datetime = MTU_1) -> object:
    return (
        Bid.up(volume_mw=20, price_eur=price)
        .divisible(min_volume_mw=5)
        .for_mtu(mtu)
        .bidding_zone(BiddingZone.NO2)
        .resource("NOKG90901", coding_scheme="NNO")
        .product_type(MarketProductType.SCHEDULED_AND_DIRECT)
        .build()
    )


def _down_bid(price: float, mtu: datetime = MTU_1) -> object:
    return (
        Bid.down(volume_mw=20, price_eur=price)
        .divisible(min_volume_mw=5)
        .for_mtu(mtu)
        .bidding_zone(BiddingZone.NO2)
        .resource("NOKG90901", coding_scheme="NNO")
        .product_type(MarketProductType.SCHEDULED_AND_DIRECT)
        .build()
    )


# ---------------------------------------------------------------------------
# gs_adjusted_price – basic formula
# ---------------------------------------------------------------------------


class TestGsAdjustedPriceFormula:
    def test_up_bid_basic(self) -> None:
        # 185 + 0.59 * (131.73 - 185) = 185 - 31.43 = 153.57
        result = gs_adjusted_price(185.0, 131.73, 0.59, Direction.UP)
        assert result == Decimal("153.57")

    def test_down_bid_basic(self) -> None:
        # 40 + 0.59 * (80 - 40) = 40 + 23.60 = 63.60
        # But clamped DOWN to <= 80 -> 63.60 (no clamp needed)
        result = gs_adjusted_price(40.0, 80.0, 0.59, Direction.DOWN)
        assert result == Decimal("63.60")

    def test_returns_decimal(self) -> None:
        result = gs_adjusted_price(100.0, 100.0, 0.59, Direction.UP)
        assert isinstance(result, Decimal)

    def test_rounded_to_two_decimal_places(self) -> None:
        result = gs_adjusted_price(200.0, 131.73, 0.59, Direction.UP)
        # Verify granularity
        assert result == result.quantize(Decimal("0.01"))

    def test_accepts_decimal_inputs(self) -> None:
        result = gs_adjusted_price(
            Decimal("185.00"),
            Decimal("131.73"),
            Decimal("0.59"),
            Direction.UP,
        )
        assert result == Decimal("153.57")


# ---------------------------------------------------------------------------
# gs_adjusted_price – clamping
# ---------------------------------------------------------------------------


class TestGsAdjustedPriceClamping:
    def test_up_bid_clamp_when_result_below_da(self) -> None:
        # Very high DA price: tier=50, DA=200, tax=0.59
        # formula: 50 + 0.59*(200-50) = 50 + 88.5 = 138.5 < 200 -> clamp to 200
        result = gs_adjusted_price(50.0, 200.0, 0.59, Direction.UP)
        assert result == Decimal("200.00")

    def test_down_bid_clamp_when_result_above_da(self) -> None:
        # tier=200, DA=50, tax=0.59
        # formula: 200 + 0.59*(50-200) = 200 - 88.5 = 111.5 > 50 -> clamp to 50
        result = gs_adjusted_price(200.0, 50.0, 0.59, Direction.DOWN)
        assert result == Decimal("50.00")

    def test_pre_mari_upper_limit(self) -> None:
        # tier_price=100, da_price=10_000, tax=0 (no adjustment) -> would be 100
        # Use extreme values to test upper limit path
        # tier=100, da=20000 (above limit), tax=0 -> UP clamp -> 20000 -> clamp to 9999
        result = gs_adjusted_price(
            100.0, 20_000.0, 0.0, Direction.UP, mari_mode=MARIMode.PRE_MARI
        )
        assert result == Decimal("9999.00")

    def test_pre_mari_lower_limit(self) -> None:
        # tier=-100, da=-20000, tax=0 -> DOWN clamp -> -20000 -> clamp to -9999
        result = gs_adjusted_price(
            -100.0, -20_000.0, 0.0, Direction.DOWN, mari_mode=MARIMode.PRE_MARI
        )
        assert result == Decimal("-9999.00")

    def test_post_mari_upper_limit(self) -> None:
        result = gs_adjusted_price(
            100.0, 20_000.0, 0.0, Direction.UP, mari_mode=MARIMode.POST_MARI
        )
        assert result == Decimal("14999.00")

    def test_post_mari_lower_limit(self) -> None:
        result = gs_adjusted_price(
            -100.0, -20_000.0, 0.0, Direction.DOWN, mari_mode=MARIMode.POST_MARI
        )
        assert result == Decimal("-14999.00")


# ---------------------------------------------------------------------------
# gs_adjusted_price – edge cases
# ---------------------------------------------------------------------------


class TestGsAdjustedPriceEdgeCases:
    def test_negative_da_price(self) -> None:
        # DA price can be negative in high renewable periods
        # tier=50, DA=-50, tax=0.59
        # formula: 50 + 0.59*(-50-50) = 50 - 59 = -9
        # UP clamp: max(-9, -50) = -9
        result = gs_adjusted_price(50.0, -50.0, 0.59, Direction.UP)
        assert result == Decimal("-9.00")

    def test_tier_equals_da_price(self) -> None:
        # Formula returns tier_price unchanged
        result = gs_adjusted_price(100.0, 100.0, 0.59, Direction.UP)
        assert result == Decimal("100.00")

    def test_tax_rate_zero_passthrough(self) -> None:
        # tax=0 -> formula returns tier_price
        result = gs_adjusted_price(185.0, 131.73, 0.0, Direction.UP)
        assert result == Decimal("185.00")

    def test_tax_rate_one_returns_da_price(self) -> None:
        # tax=1 -> formula: tier + 1*(da - tier) = da
        result = gs_adjusted_price(185.0, 131.73, 1.0, Direction.UP)
        assert result == Decimal("131.73")

    def test_tax_rate_invalid_above_one(self) -> None:
        with pytest.raises(ValueError, match="tax_rate must be between 0 and 1"):
            gs_adjusted_price(100.0, 80.0, 1.01, Direction.UP)

    def test_tax_rate_invalid_negative(self) -> None:
        with pytest.raises(ValueError, match="tax_rate must be between 0 and 1"):
            gs_adjusted_price(100.0, 80.0, -0.01, Direction.UP)

    def test_tax_rate_boundary_zero_valid(self) -> None:
        # Should not raise
        gs_adjusted_price(100.0, 80.0, 0.0, Direction.UP)

    def test_tax_rate_boundary_one_valid(self) -> None:
        # Should not raise
        gs_adjusted_price(100.0, 80.0, 1.0, Direction.UP)

    def test_negative_da_down_bid(self) -> None:
        # tier=10, DA=-50, tax=0.59
        # formula: 10 + 0.59*(-50-10) = 10 - 35.4 = -25.4
        # DOWN clamp: min(-25.4, -50) = -50
        result = gs_adjusted_price(10.0, -50.0, 0.59, Direction.DOWN)
        assert result == Decimal("-50.00")


# ---------------------------------------------------------------------------
# gs_adjust_bids – batch function
# ---------------------------------------------------------------------------


class TestGsAdjustBids:
    def test_multiple_bids_across_mtus(self) -> None:
        bids = [
            _up_bid(185.0, MTU_1),
            _up_bid(185.0, MTU_2),
            _up_bid(185.0, MTU_3),
        ]
        da_prices = {
            MTU_1: Decimal("131.73"),
            MTU_2: Decimal("145.00"),
            MTU_3: Decimal("90.00"),
        }
        result = gs_adjust_bids(bids, da_prices, tax_rate=Decimal("0.59"))
        assert len(result) == 3
        # MTU1: 185 + 0.59*(131.73-185) = 153.57; >= 131.73 -> 153.57
        assert result[0].period.point.energy_price == Decimal("153.57")
        # MTU2: 185 + 0.59*(145-185) = 185 - 23.6 = 161.4; >= 145 -> 161.40
        assert result[1].period.point.energy_price == Decimal("161.40")
        # MTU3: 185 + 0.59*(90-185) = 185 - 56.05 = 128.95; >= 90 -> 128.95
        assert result[2].period.point.energy_price == Decimal("128.95")

    def test_does_not_mutate_original_bids(self) -> None:
        original_price = Decimal("185.00")
        bids = [_up_bid(float(original_price), MTU_1)]
        da_prices = {MTU_1: Decimal("100.00")}
        gs_adjust_bids(bids, da_prices, tax_rate=Decimal("0.59"))
        # Original bid price unchanged
        assert bids[0].period.point.energy_price == original_price

    def test_missing_da_price_raises_key_error(self) -> None:
        bids = [_up_bid(185.0, MTU_1)]
        da_prices: dict[datetime, Decimal] = {}  # empty – MTU_1 not present
        with pytest.raises(KeyError, match="No DA price found"):
            gs_adjust_bids(bids, da_prices, tax_rate=Decimal("0.59"))

    def test_invalid_tax_rate_raises_value_error(self) -> None:
        bids = [_up_bid(185.0, MTU_1)]
        da_prices = {MTU_1: Decimal("100.00")}
        with pytest.raises(ValueError, match="tax_rate must be between 0 and 1"):
            gs_adjust_bids(bids, da_prices, tax_rate=1.5)

    def test_returns_new_instances(self) -> None:
        bids = [_up_bid(185.0, MTU_1)]
        da_prices = {MTU_1: Decimal("100.00")}
        result = gs_adjust_bids(bids, da_prices, tax_rate=Decimal("0.59"))
        assert result[0] is not bids[0]

    def test_accepts_float_da_prices(self) -> None:
        bids = [_up_bid(185.0, MTU_1)]
        da_prices_float: dict[datetime, float] = {MTU_1: 131.73}
        result = gs_adjust_bids(bids, da_prices_float, tax_rate=0.59)
        assert result[0].period.point.energy_price == Decimal("153.57")

    def test_mixed_direction_bids(self) -> None:
        up = _up_bid(185.0, MTU_1)
        down = _down_bid(40.0, MTU_2)
        da_prices = {MTU_1: Decimal("131.73"), MTU_2: Decimal("80.00")}
        result = gs_adjust_bids([up, down], da_prices, tax_rate=Decimal("0.59"))
        # Up bid: 185 + 0.59*(131.73-185) = 153.57
        assert result[0].period.point.energy_price == Decimal("153.57")
        # Down bid: 40 + 0.59*(80-40) = 63.60; <= 80 -> 63.60
        assert result[1].period.point.energy_price == Decimal("63.60")
