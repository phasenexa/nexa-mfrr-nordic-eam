"""Tests for the simple bid builder (bids/simple.py) and validation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from nexa_mfrr_eam import Bid, BiddingZone, Direction, MarketProductType
from nexa_mfrr_eam.bids.validation import validate_bid_time_series, validate_document
from nexa_mfrr_eam.exceptions import BidValidationError
from nexa_mfrr_eam.types import (
    BidDocumentModel,
    BidTimeSeriesModel,
    MARIMode,
    PeriodModel,
    PointModel,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MTU = "2026-03-21T10:00Z"
MTU_DT = datetime(2026, 3, 21, 10, 0, tzinfo=UTC)


def _minimal_divisible_bid() -> BidTimeSeriesModel:
    return (
        Bid.up(volume_mw=20, price_eur=50.00)
        .divisible(min_volume_mw=10)
        .for_mtu(MTU)
        .bidding_zone(BiddingZone.NO2)
        .resource("NOKG90901", coding_scheme="NNO")
        .product_type(MarketProductType.SCHEDULED_AND_DIRECT)
        .build()
    )


def _minimal_indivisible_bid() -> BidTimeSeriesModel:
    return (
        Bid.up(volume_mw=15, price_eur=70.00)
        .indivisible()
        .for_mtu(MTU)
        .bidding_zone(BiddingZone.NO2)
        .resource("NOKG90901", coding_scheme="NNO")
        .product_type(MarketProductType.SCHEDULED_ONLY)
        .build()
    )


# ---------------------------------------------------------------------------
# Bid.up / Bid.down factory
# ---------------------------------------------------------------------------


class TestBidFactory:
    def test_bid_up_returns_builder(self) -> None:
        builder = Bid.up(volume_mw=10, price_eur=50.0)
        assert builder._direction is Direction.UP

    def test_bid_down_returns_builder(self) -> None:
        builder = Bid.down(volume_mw=10, price_eur=50.0)
        assert builder._direction is Direction.DOWN

    def test_bid_up_no_price(self) -> None:
        builder = Bid.up(volume_mw=10)
        assert builder._price_eur is None

    def test_price_converted_to_decimal(self) -> None:
        builder = Bid.up(volume_mw=10, price_eur=85.50)
        assert isinstance(builder._price_eur, Decimal)
        assert builder._price_eur == Decimal("85.5")

    def test_decimal_price_accepted(self) -> None:
        builder = Bid.up(volume_mw=10, price_eur=Decimal("100.00"))
        assert builder._price_eur == Decimal("100.00")


# ---------------------------------------------------------------------------
# SimpleBidBuilder – individual methods
# ---------------------------------------------------------------------------


class TestSimpleBidBuilder:
    def test_divisible_sets_flag(self) -> None:
        b = Bid.up(10, 50.0).divisible(min_volume_mw=5)
        assert b._divisible is True
        assert b._min_volume_mw == 5

    def test_indivisible_sets_flag(self) -> None:
        b = Bid.up(10, 50.0).indivisible()
        assert b._divisible is False
        assert b._min_volume_mw is None

    def test_for_mtu_string_with_z(self) -> None:
        b = Bid.up(10, 50.0).for_mtu("2026-03-21T10:00Z")
        assert b._mtu_start == MTU_DT

    def test_for_mtu_string_with_offset(self) -> None:
        b = Bid.up(10, 50.0).for_mtu("2026-03-21T10:00+00:00")
        assert b._mtu_start == MTU_DT

    def test_for_mtu_datetime(self) -> None:
        b = Bid.up(10, 50.0).for_mtu(MTU_DT)
        assert b._mtu_start == MTU_DT

    def test_for_mtu_naive_raises(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            Bid.up(10, 50.0).for_mtu("2026-03-21T10:00")

    def test_for_mtu_non_boundary_raises(self) -> None:
        with pytest.raises(ValueError, match="0, 15, 30, or 45"):
            Bid.up(10, 50.0).for_mtu("2026-03-21T10:07Z")

    def test_for_mtu_with_seconds_raises(self) -> None:
        with pytest.raises(ValueError, match="no seconds"):
            Bid.up(10, 50.0).for_mtu("2026-03-21T10:00:30+00:00")

    def test_resource_defaults_to_eic(self) -> None:
        b = Bid.up(10, 50.0).resource("SOMERESOURCE")
        assert b._resource_id == "SOMERESOURCE"
        assert b._resource_coding_scheme == "A01"

    def test_resource_custom_coding_scheme(self) -> None:
        b = Bid.up(10, 50.0).resource("NOKG90901", coding_scheme="NNO")
        assert b._resource_coding_scheme == "NNO"

    def test_bidding_zone_stored(self) -> None:
        b = Bid.up(10, 50.0).bidding_zone(BiddingZone.NO2)
        assert b._bidding_zone is BiddingZone.NO2

    def test_product_type_stored(self) -> None:
        b = Bid.up(10, 50.0).product_type(MarketProductType.SCHEDULED_ONLY)
        assert b._product_type is MarketProductType.SCHEDULED_ONLY

    def test_with_mrid_override(self) -> None:
        custom = "my-custom-mrid"
        b = Bid.up(10, 50.0).with_mrid(custom)
        assert b._mrid == custom

    def test_technical_link_stored(self) -> None:
        link_id = str(uuid.uuid4())
        b = Bid.up(10, 50.0).technical_link(link_id)
        assert b._linked_bids_id == link_id

    def test_faster_activation_stored(self) -> None:
        b = Bid.up(10, 50.0).faster_activation(minutes=3)
        assert b._activation_constraint == "PT3M"

    def test_max_duration_stored(self) -> None:
        b = Bid.up(10, 50.0).max_duration(minutes=90)
        assert b._max_constraint == "PT90M"

    def test_resting_time_stored(self) -> None:
        b = Bid.up(10, 50.0).resting_time(minutes=60)
        assert b._resting_constraint == "PT60M"


# ---------------------------------------------------------------------------
# build() – valid outputs
# ---------------------------------------------------------------------------


class TestSimpleBidBuild:
    def test_build_divisible_bid(self) -> None:
        bid = _minimal_divisible_bid()
        assert bid.divisible_code == "A01"
        assert bid.flow_direction == "A01"  # UP
        assert bid.period.point.quantity == Decimal("20")
        assert bid.period.point.minimum_quantity == Decimal("10")
        assert bid.period.point.energy_price == Decimal("50")

    def test_build_indivisible_bid(self) -> None:
        bid = _minimal_indivisible_bid()
        assert bid.divisible_code == "A02"
        assert bid.period.point.minimum_quantity is None

    def test_build_period_duration_15_min(self) -> None:
        bid = _minimal_divisible_bid()
        delta = bid.period.time_interval_end - bid.period.time_interval_start
        assert delta == timedelta(minutes=15)

    def test_build_auto_uuid_mrid(self) -> None:
        bid = _minimal_divisible_bid()
        # Should be a valid UUID string
        parsed = uuid.UUID(bid.mrid)
        assert str(parsed) == bid.mrid

    def test_build_mrid_override(self) -> None:
        custom = "custom-mrid-123"
        bid = (
            Bid.up(volume_mw=20, price_eur=50.0)
            .divisible(min_volume_mw=10)
            .for_mtu(MTU)
            .product_type(MarketProductType.SCHEDULED_ONLY)
            .with_mrid(custom)
            .build()
        )
        assert bid.mrid == custom

    def test_build_connecting_domain_from_zone(self) -> None:
        bid = _minimal_divisible_bid()
        assert bid.connecting_domain_mrid == BiddingZone.NO2.value

    def test_build_no_bidding_zone_gives_none(self) -> None:
        bid = (
            Bid.up(volume_mw=20, price_eur=50.0)
            .divisible(min_volume_mw=10)
            .for_mtu(MTU)
            .product_type(MarketProductType.SCHEDULED_ONLY)
            .build()
        )
        assert bid.connecting_domain_mrid is None

    def test_build_product_type_stored(self) -> None:
        bid = (
            Bid.up(volume_mw=20, price_eur=50.0)
            .divisible(min_volume_mw=10)
            .for_mtu(MTU)
            .product_type(MarketProductType.SCHEDULED_AND_DIRECT)
            .build()
        )
        assert bid.standard_market_product_type == "A07"

    def test_build_down_regulation(self) -> None:
        bid = (
            Bid.down(volume_mw=20, price_eur=30.0)
            .indivisible()
            .for_mtu(MTU)
            .product_type(MarketProductType.SCHEDULED_ONLY)
            .build()
        )
        assert bid.flow_direction == "A02"  # DOWN

    def test_build_model_is_frozen(self) -> None:
        from pydantic import ValidationError

        bid = _minimal_divisible_bid()
        with pytest.raises(ValidationError):
            bid.mrid = "nope"  # type: ignore[misc]

    def test_build_includes_activation_constraint(self) -> None:
        bid = (
            Bid.up(volume_mw=20, price_eur=50.0)
            .divisible(min_volume_mw=10)
            .for_mtu(MTU)
            .product_type(MarketProductType.SCHEDULED_ONLY)
            .faster_activation(minutes=3)
            .build()
        )
        assert bid.activation_constraint_duration == "PT3M"

    def test_build_technical_link_stored(self) -> None:
        link_id = str(uuid.uuid4())
        bid = (
            Bid.up(volume_mw=20, price_eur=50.0)
            .divisible(min_volume_mw=10)
            .for_mtu(MTU)
            .product_type(MarketProductType.SCHEDULED_ONLY)
            .technical_link(link_id)
            .build()
        )
        assert bid.linked_bids_identification == link_id


# ---------------------------------------------------------------------------
# build() – error cases
# ---------------------------------------------------------------------------


class TestSimpleBidBuildErrors:
    def test_missing_mtu_raises(self) -> None:
        with pytest.raises(BidValidationError, match="for_mtu"):
            Bid.up(10, 50.0).divisible(5).product_type(
                MarketProductType.SCHEDULED_ONLY
            ).build()

    def test_missing_divisible_raises(self) -> None:
        with pytest.raises(BidValidationError, match="divisible"):
            Bid.up(10, 50.0).for_mtu(MTU).product_type(
                MarketProductType.SCHEDULED_ONLY
            ).build()

    def test_missing_product_type_raises(self) -> None:
        with pytest.raises(BidValidationError, match="product_type"):
            Bid.up(10, 50.0).divisible(5).for_mtu(MTU).build()


# ---------------------------------------------------------------------------
# validate_bid_time_series
# ---------------------------------------------------------------------------


class TestValidateBidTimeSeries:
    def _bid(
        self,
        quantity: int = 20,
        min_qty: int | None = 10,
        price: float | None = 50.0,
        divisible: bool = True,
        product_type: str = "A05",
    ) -> BidTimeSeriesModel:
        point = PointModel(
            quantity=Decimal(str(quantity)),
            minimum_quantity=Decimal(str(min_qty)) if min_qty is not None else None,
            energy_price=Decimal(str(price)) if price is not None else None,
        )
        period = PeriodModel(
            time_interval_start=MTU_DT,
            time_interval_end=MTU_DT + timedelta(minutes=15),
            point=point,
        )
        return BidTimeSeriesModel(
            mrid=str(uuid.uuid4()),
            divisible_code="A01" if divisible else "A02",
            flow_direction="A01",
            standard_market_product_type=product_type,
            period=period,
        )

    def test_valid_bid_no_errors(self) -> None:
        bid = self._bid()
        errors = validate_bid_time_series(bid, MARIMode.PRE_MARI, min_bid_mw=1)
        assert errors == []

    def test_quantity_below_1_mw(self) -> None:
        bid = self._bid(quantity=0, min_qty=0)
        errors = validate_bid_time_series(bid, MARIMode.PRE_MARI, min_bid_mw=1)
        assert any("minimum of 1 MW" in e for e in errors)

    def test_quantity_below_tso_min(self) -> None:
        bid = self._bid(quantity=5, min_qty=5)
        errors = validate_bid_time_series(bid, MARIMode.PRE_MARI, min_bid_mw=10)
        assert any("TSO minimum" in e for e in errors)

    def test_quantity_above_max(self) -> None:
        bid = self._bid(quantity=10000, min_qty=1)
        errors = validate_bid_time_series(bid, MARIMode.PRE_MARI)
        assert any("9999" in e for e in errors)

    def test_divisible_without_min_quantity_error(self) -> None:
        bid = self._bid(divisible=True, min_qty=None)
        errors = validate_bid_time_series(bid, MARIMode.PRE_MARI)
        assert any("minimum_quantity" in e for e in errors)

    def test_min_quantity_exceeds_quantity_error(self) -> None:
        bid = self._bid(quantity=10, min_qty=20)
        errors = validate_bid_time_series(bid, MARIMode.PRE_MARI)
        assert any("minimum_quantity" in e and "exceeds" in e for e in errors)

    def test_price_at_pre_mari_limit_ok(self) -> None:
        bid = self._bid(price=10000.0)
        errors = validate_bid_time_series(bid, MARIMode.PRE_MARI)
        assert errors == []

    def test_price_exceeds_pre_mari_limit(self) -> None:
        bid = self._bid(price=10001.0)
        errors = validate_bid_time_series(bid, MARIMode.PRE_MARI)
        assert any("pre_mari" in e for e in errors)

    def test_price_at_post_mari_limit_ok(self) -> None:
        bid = self._bid(price=15000.0)
        errors = validate_bid_time_series(bid, MARIMode.POST_MARI)
        assert errors == []

    def test_price_exceeds_post_mari_limit(self) -> None:
        bid = self._bid(price=15001.0)
        errors = validate_bid_time_series(bid, MARIMode.POST_MARI)
        assert any("post_mari" in e for e in errors)

    def test_negative_price_within_range_ok(self) -> None:
        bid = self._bid(price=-9999.0)
        errors = validate_bid_time_series(bid, MARIMode.PRE_MARI)
        assert errors == []

    def test_period_shift_with_price_error(self) -> None:
        bid = self._bid(product_type="Z01", price=50.0)
        errors = validate_bid_time_series(bid, MARIMode.PRE_MARI)
        assert any("Z01" in e and "price" in e for e in errors)

    def test_period_shift_without_price_ok(self) -> None:
        bid = self._bid(product_type="Z01", price=None)
        errors = validate_bid_time_series(bid, MARIMode.PRE_MARI)
        assert errors == []

    def test_mrid_over_60_chars_error(self) -> None:
        point = PointModel(quantity=Decimal("20"), minimum_quantity=Decimal("10"))
        period = PeriodModel(
            time_interval_start=MTU_DT,
            time_interval_end=MTU_DT + timedelta(minutes=15),
            point=point,
        )
        bid = BidTimeSeriesModel(
            mrid="a" * 61,
            divisible_code="A01",
            flow_direction="A01",
            period=period,
        )
        errors = validate_bid_time_series(bid, MARIMode.PRE_MARI)
        assert any("60" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_document
# ---------------------------------------------------------------------------


class TestValidateDocument:
    def _doc(self, bids: list[BidTimeSeriesModel]) -> BidDocumentModel:
        start = bids[0].period.time_interval_start if bids else MTU_DT
        fallback = MTU_DT + timedelta(minutes=15)
        end = bids[-1].period.time_interval_end if bids else fallback
        return BidDocumentModel(
            sender_mrid="9999909919920",
            sender_coding_scheme="A10",
            receiver_mrid="10X1001A1001A38Y",
            created_datetime=datetime.now(tz=UTC),
            reserve_bid_period_start=start,
            reserve_bid_period_end=end,
            domain_mrid="10YNO-0--------C",
            bid_time_series=tuple(bids),
        )

    def test_valid_document(self) -> None:
        bid = (
            Bid.up(volume_mw=20, price_eur=50.0)
            .divisible(min_volume_mw=10)
            .for_mtu(MTU)
            .product_type(MarketProductType.SCHEDULED_ONLY)
            .build()
        )
        doc = self._doc([bid])
        errors = validate_document(doc, MARIMode.PRE_MARI)
        assert errors == []

    def test_empty_document_error(self) -> None:
        doc = self._doc([])
        errors = validate_document(doc, MARIMode.PRE_MARI)
        assert any("no BidTimeSeries" in e for e in errors)

    def test_too_many_bids_error(self) -> None:
        bid = (
            Bid.up(volume_mw=20, price_eur=50.0)
            .divisible(min_volume_mw=10)
            .for_mtu(MTU)
            .product_type(MarketProductType.SCHEDULED_ONLY)
            .build()
        )
        doc = self._doc([bid])
        errors = validate_document(doc, MARIMode.PRE_MARI, max_bids_per_message=0)
        assert any("exceeds" in e for e in errors)
