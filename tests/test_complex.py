"""Tests for complex bid group builders (bids/complex.py)."""

from __future__ import annotations

import pytest
from nexa_mfrr_eam import (
    TSO,
    BiddingZone,
    BidDocument,
    Direction,
    ExclusiveGroup,
    InclusiveGroup,
    MARIMode,
    MarketProductType,
    MultipartGroup,
    ProductionType,
)
from nexa_mfrr_eam.exceptions import BidValidationError

MTU = "2026-03-21T10:00Z"
MTU2 = "2026-03-21T10:15Z"

# ---------------------------------------------------------------------------
# ExclusiveGroup
# ---------------------------------------------------------------------------


def test_exclusive_group_happy_path() -> None:
    group = (
        ExclusiveGroup(bidding_zone=BiddingZone.DK1)
        .direction(Direction.UP)
        .resource("DK1-RES-001", coding_scheme="A01")
        .product_type(MarketProductType.SCHEDULED_ONLY)
        .for_mtu(MTU)
        .add_component(volume_mw=30, price_eur=60.0, divisible=True, min_volume_mw=10)
        .add_component(volume_mw=50, price_eur=80.0, divisible=False)
        .build()
    )
    assert len(group) == 2
    for bid in group:
        assert bid.exclusive_bids_identification is not None
        assert bid.multipart_bid_identification is None
        assert bid.inclusive_bids_identification is None


def test_exclusive_group_shared_id() -> None:
    group = (
        ExclusiveGroup(bidding_zone=BiddingZone.DK1)
        .direction(Direction.UP)
        .resource("DK1-RES-001")
        .product_type(MarketProductType.SCHEDULED_ONLY)
        .for_mtu(MTU)
        .add_component(volume_mw=10, price_eur=55.0, divisible=False)
        .add_component(volume_mw=20, price_eur=70.0, divisible=False)
        .build()
    )
    ids = {bid.exclusive_bids_identification for bid in group}
    assert len(ids) == 1, "All bids must share the same exclusive_bids_identification"


def test_exclusive_group_custom_id() -> None:
    custom_id = "my-custom-group-id"
    group = (
        ExclusiveGroup(bidding_zone=BiddingZone.DK1, group_id=custom_id)
        .direction(Direction.UP)
        .product_type(MarketProductType.SCHEDULED_ONLY)
        .for_mtu(MTU)
        .add_component(volume_mw=10, price_eur=55.0, divisible=False)
        .add_component(volume_mw=20, price_eur=70.0, divisible=False)
        .build()
    )
    assert group[0].exclusive_bids_identification == custom_id


def test_exclusive_group_requires_two_components() -> None:
    with pytest.raises(BidValidationError, match="at least 2"):
        (
            ExclusiveGroup(bidding_zone=BiddingZone.DK1)
            .product_type(MarketProductType.SCHEDULED_ONLY)
            .for_mtu(MTU)
            .add_component(volume_mw=10, price_eur=55.0, divisible=False)
            .build()
        )


def test_exclusive_group_components_same_mtu() -> None:
    with pytest.raises(BidValidationError, match="same MTU"):
        (
            ExclusiveGroup(bidding_zone=BiddingZone.DK1)
            .product_type(MarketProductType.SCHEDULED_ONLY)
            .add_component(volume_mw=10, price_eur=55.0, divisible=False, mtu=MTU)
            .add_component(volume_mw=20, price_eur=70.0, divisible=False, mtu=MTU2)
            .build()
        )


def test_exclusive_group_with_psr_type() -> None:
    group = (
        ExclusiveGroup(bidding_zone=BiddingZone.DK1)
        .direction(Direction.UP)
        .resource("DK1-RES-001")
        .product_type(MarketProductType.SCHEDULED_ONLY)
        .for_mtu(MTU)
        .add_component(
            volume_mw=30,
            price_eur=60.0,
            divisible=False,
            psr_type=ProductionType.WIND_ONSHORE,
        )
        .add_component(
            volume_mw=50,
            price_eur=80.0,
            divisible=False,
            psr_type=ProductionType.WIND_ONSHORE,
        )
        .build()
    )
    assert group[0].psr_type == "B19"
    assert group[1].psr_type == "B19"


# ---------------------------------------------------------------------------
# MultipartGroup
# ---------------------------------------------------------------------------


def test_multipart_group_happy_path() -> None:
    group = (
        MultipartGroup(bidding_zone=BiddingZone.DK1)
        .direction(Direction.UP)
        .resource("DK1-RES-001")
        .product_type(MarketProductType.SCHEDULED_ONLY)
        .for_mtu(MTU)
        .add_component(volume_mw=20, price_eur=50.0, divisible=True, min_volume_mw=5)
        .add_component(volume_mw=15, price_eur=75.0, divisible=True, min_volume_mw=5)
        .add_component(volume_mw=10, price_eur=120.0, divisible=False)
        .build()
    )
    assert len(group) == 3
    for bid in group:
        assert bid.multipart_bid_identification is not None
        assert bid.exclusive_bids_identification is None


def test_multipart_group_shared_id() -> None:
    group = (
        MultipartGroup(bidding_zone=BiddingZone.DK1)
        .direction(Direction.UP)
        .product_type(MarketProductType.SCHEDULED_ONLY)
        .for_mtu(MTU)
        .add_component(volume_mw=10, price_eur=50.0, divisible=False)
        .add_component(volume_mw=10, price_eur=80.0, divisible=False)
        .build()
    )
    ids = {bid.multipart_bid_identification for bid in group}
    assert len(ids) == 1


def test_multipart_group_requires_two_components() -> None:
    with pytest.raises(BidValidationError, match="at least 2"):
        (
            MultipartGroup(bidding_zone=BiddingZone.DK1)
            .direction(Direction.UP)
            .product_type(MarketProductType.SCHEDULED_ONLY)
            .for_mtu(MTU)
            .add_component(volume_mw=10, price_eur=50.0, divisible=False)
            .build()
        )


def test_multipart_group_prices_must_differ() -> None:
    with pytest.raises(BidValidationError, match="prices must be distinct"):
        (
            MultipartGroup(bidding_zone=BiddingZone.DK1)
            .direction(Direction.UP)
            .product_type(MarketProductType.SCHEDULED_ONLY)
            .for_mtu(MTU)
            .add_component(volume_mw=10, price_eur=50.0, divisible=False)
            .add_component(volume_mw=20, price_eur=50.0, divisible=False)  # duplicate
            .build()
        )


def test_multipart_group_same_mtu_enforced() -> None:
    with pytest.raises(BidValidationError, match="same MTU"):
        (
            MultipartGroup(bidding_zone=BiddingZone.DK1)
            .direction(Direction.UP)
            .product_type(MarketProductType.SCHEDULED_ONLY)
            .add_component(volume_mw=10, price_eur=50.0, divisible=False, mtu=MTU)
            .add_component(volume_mw=10, price_eur=80.0, divisible=False, mtu=MTU2)
            .build()
        )


def test_multipart_group_direction_must_match() -> None:
    with pytest.raises(BidValidationError, match="same direction"):
        (
            MultipartGroup(bidding_zone=BiddingZone.DK1)
            .product_type(MarketProductType.SCHEDULED_ONLY)
            .for_mtu(MTU)
            .add_component(
                volume_mw=10, price_eur=50.0, divisible=False, direction=Direction.UP
            )
            .add_component(
                volume_mw=10, price_eur=80.0, divisible=False, direction=Direction.DOWN
            )
            .build()
        )


# ---------------------------------------------------------------------------
# InclusiveGroup
# ---------------------------------------------------------------------------


def test_inclusive_group_happy_path() -> None:
    group = (
        InclusiveGroup(bidding_zone=BiddingZone.FI)
        .direction(Direction.UP)
        .resource("FI-RES-001")
        .product_type(MarketProductType.SCHEDULED_AND_DIRECT)
        .for_mtu(MTU)
        .add_component(volume_mw=15, price_eur=65.0, divisible=True, min_volume_mw=5)
        .add_component(volume_mw=20, price_eur=65.0, divisible=True, min_volume_mw=5)
        .build()
    )
    assert len(group) == 2
    for bid in group:
        assert bid.inclusive_bids_identification is not None
        assert bid.exclusive_bids_identification is None
        assert bid.multipart_bid_identification is None


def test_inclusive_group_shared_id() -> None:
    group = (
        InclusiveGroup(bidding_zone=BiddingZone.FI)
        .direction(Direction.UP)
        .product_type(MarketProductType.SCHEDULED_AND_DIRECT)
        .for_mtu(MTU)
        .add_component(volume_mw=15, price_eur=65.0, divisible=False)
        .add_component(volume_mw=20, price_eur=65.0, divisible=False)
        .build()
    )
    ids = {bid.inclusive_bids_identification for bid in group}
    assert len(ids) == 1


def test_inclusive_group_prices_must_match() -> None:
    with pytest.raises(BidValidationError, match="same price"):
        (
            InclusiveGroup(bidding_zone=BiddingZone.FI)
            .direction(Direction.UP)
            .product_type(MarketProductType.SCHEDULED_AND_DIRECT)
            .for_mtu(MTU)
            .add_component(volume_mw=15, price_eur=65.0, divisible=False)
            .add_component(volume_mw=20, price_eur=70.0, divisible=False)  # different
            .build()
        )


def test_inclusive_group_requires_two_components() -> None:
    with pytest.raises(BidValidationError, match="at least 2"):
        (
            InclusiveGroup(bidding_zone=BiddingZone.FI)
            .direction(Direction.UP)
            .product_type(MarketProductType.SCHEDULED_AND_DIRECT)
            .for_mtu(MTU)
            .add_component(volume_mw=15, price_eur=65.0, divisible=False)
            .build()
        )


# ---------------------------------------------------------------------------
# Energinet psr_type validation
# ---------------------------------------------------------------------------


def test_psr_type_required_for_energinet() -> None:
    """Validate that Energinet bids without psr_type fail document validation."""
    from nexa_mfrr_eam import Bid

    bid = (
        Bid.up(volume_mw=20, price_eur=50.0)
        .divisible(min_volume_mw=5)
        .for_mtu(MTU)
        .resource("DK1-RES-001", coding_scheme="A01")
        .product_type(MarketProductType.SCHEDULED_ONLY)
        .build()
    )
    doc = (
        BidDocument(tso=TSO.ENERGINET)
        .sender(party_id="10XBRP-001-----A", coding_scheme="A01")
        .add_bid(bid)
        .build()
    )
    errors = doc.validate(mari_mode=MARIMode.PRE_MARI)
    assert any("mktPSRType.psrType" in e for e in errors), errors


def test_psr_type_valid_for_energinet() -> None:
    """Validate that Energinet bids WITH psr_type pass validation."""
    from nexa_mfrr_eam import Bid

    bid = (
        Bid.up(volume_mw=20, price_eur=50.0)
        .divisible(min_volume_mw=5)
        .for_mtu(MTU)
        .resource("DK1-RES-001", coding_scheme="A01")
        .product_type(MarketProductType.SCHEDULED_ONLY)
        .build()
    )
    # Add psr_type via model_copy since SimpleBidBuilder doesn't expose it directly
    bid_with_psr = bid.model_copy(
        update={"psr_type": ProductionType.WIND_ONSHORE.value}
    )
    doc = (
        BidDocument(tso=TSO.ENERGINET)
        .sender(party_id="10XBRP-001-----A", coding_scheme="A01")
        .add_bid(bid_with_psr)
        .build()
    )
    errors = doc.validate(mari_mode=MARIMode.PRE_MARI)
    assert not any("mktPSRType" in e for e in errors), errors


def test_exclusive_group_in_energinet_document() -> None:
    """Exclusive group bids with psr_type validate cleanly for Energinet."""
    group = (
        ExclusiveGroup(bidding_zone=BiddingZone.DK1)
        .direction(Direction.UP)
        .resource("DK1-RES-001")
        .product_type(MarketProductType.SCHEDULED_ONLY)
        .for_mtu(MTU)
        .add_component(
            volume_mw=30,
            price_eur=60.0,
            divisible=False,
            psr_type=ProductionType.WIND_OFFSHORE,
        )
        .add_component(
            volume_mw=50,
            price_eur=80.0,
            divisible=False,
            psr_type=ProductionType.WIND_OFFSHORE,
        )
        .build()
    )
    doc = (
        BidDocument(tso=TSO.ENERGINET)
        .sender(party_id="10XBRP-001-----A", coding_scheme="A01")
        .add_bids(group)
        .build()
    )
    errors = doc.validate(mari_mode=MARIMode.PRE_MARI)
    assert not errors, errors


# ---------------------------------------------------------------------------
# XML serialization
# ---------------------------------------------------------------------------


def test_exclusive_group_xml_contains_exclusive_id() -> None:
    group = (
        ExclusiveGroup(bidding_zone=BiddingZone.DK1)
        .direction(Direction.UP)
        .resource("DK1-RES-001")
        .product_type(MarketProductType.SCHEDULED_ONLY)
        .for_mtu(MTU)
        .add_component(
            volume_mw=30,
            price_eur=60.0,
            divisible=False,
            psr_type=ProductionType.WIND_ONSHORE,
        )
        .add_component(
            volume_mw=50,
            price_eur=80.0,
            divisible=False,
            psr_type=ProductionType.WIND_ONSHORE,
        )
        .build()
    )
    doc = (
        BidDocument(tso=TSO.ENERGINET)
        .sender(party_id="10XBRP-001-----A", coding_scheme="A01")
        .add_bids(group)
        .build()
    )
    xml = doc.to_xml().decode("utf-8")
    assert "exclusiveBidsIdentification" in xml
    assert "mktPSRType.psrType" in xml
    assert "B19" in xml


def test_multipart_group_xml_contains_multipart_id() -> None:
    group = (
        MultipartGroup(bidding_zone=BiddingZone.DK2)
        .direction(Direction.UP)
        .resource("DK2-RES-001")
        .product_type(MarketProductType.SCHEDULED_ONLY)
        .for_mtu(MTU)
        .add_component(
            volume_mw=20,
            price_eur=50.0,
            divisible=True,
            min_volume_mw=5,
            psr_type=ProductionType.SOLAR,
        )
        .add_component(
            volume_mw=15, price_eur=80.0, divisible=False, psr_type=ProductionType.SOLAR
        )
        .build()
    )
    doc = (
        BidDocument(tso=TSO.ENERGINET)
        .sender(party_id="10XBRP-001-----A", coding_scheme="A01")
        .add_bids(group)
        .build()
    )
    xml = doc.to_xml().decode("utf-8")
    assert "multipartBidIdentification" in xml
    assert "mktPSRType.psrType" in xml
    assert "B16" in xml


def test_note_serialized_in_xml() -> None:
    from nexa_mfrr_eam import Bid

    bid = (
        Bid.up(volume_mw=20, price_eur=50.0)
        .divisible(min_volume_mw=5)
        .for_mtu(MTU)
        .resource("DK1-RES-001")
        .product_type(MarketProductType.SCHEDULED_ONLY)
        .build()
    )
    bid_with_note = bid.model_copy(
        update={"psr_type": "B19", "note": "Custom BRP reference 12345"}
    )
    doc = (
        BidDocument(tso=TSO.ENERGINET)
        .sender(party_id="10XBRP-001-----A", coding_scheme="A01")
        .add_bid(bid_with_note)
        .build()
    )
    xml = doc.to_xml().decode("utf-8")
    assert "<Note>Custom BRP reference 12345</Note>" in xml


def test_inclusive_group_xml_contains_inclusive_id() -> None:
    group = (
        InclusiveGroup(bidding_zone=BiddingZone.FI)
        .direction(Direction.UP)
        .resource("FI-RES-001")
        .product_type(MarketProductType.SCHEDULED_AND_DIRECT)
        .for_mtu(MTU)
        .add_component(volume_mw=15, price_eur=65.0, divisible=False)
        .add_component(volume_mw=20, price_eur=65.0, divisible=False)
        .build()
    )
    doc = (
        BidDocument(tso=TSO.STATNETT)
        .sender(party_id="9999909919920", coding_scheme="A10")
        .add_bids(group)
        .build()
    )
    xml = doc.to_xml().decode("utf-8")
    assert "inclusiveBidsIdentification" in xml
