"""Tests for the BidDocumentBuilder and BuiltBidDocument."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from nexa_mfrr_eam import TSO, Bid, BidDocument, MARIMode, MarketProductType
from nexa_mfrr_eam.documents.reserve_bid import BidDocumentBuilder, BuiltBidDocument
from nexa_mfrr_eam.exceptions import BidValidationError
from nexa_mfrr_eam.types import BiddingZone

MTU = "2026-03-21T10:00Z"
SENDER_ID = "9999909919920"


def _simple_bid(
    mtu: str = MTU,
    volume_mw: int = 20,
    price: float = 50.0,
    min_vol: int = 10,
) -> object:
    return (
        Bid.up(volume_mw=volume_mw, price_eur=price)
        .divisible(min_volume_mw=min_vol)
        .for_mtu(mtu)
        .bidding_zone(BiddingZone.NO2)
        .resource("NOKG90901", coding_scheme="NNO")
        .product_type(MarketProductType.SCHEDULED_AND_DIRECT)
        .build()
    )


class TestBidDocumentFactory:
    def test_bid_document_returns_builder(self) -> None:
        result = BidDocument(tso=TSO.STATNETT)
        assert isinstance(result, BidDocumentBuilder)

    def test_fingrid_tso_supported(self) -> None:
        result = BidDocument(tso=TSO.FINGRID)
        assert isinstance(result, BidDocumentBuilder)


class TestBidDocumentBuilder:
    def test_build_missing_sender_raises(self) -> None:
        with pytest.raises(BidValidationError, match="sender"):
            BidDocument(tso=TSO.STATNETT).add_bid(_simple_bid()).build()  # type: ignore[arg-type]

    def test_build_missing_bids_raises(self) -> None:
        with pytest.raises(BidValidationError, match="bid"):
            BidDocument(tso=TSO.STATNETT).sender(SENDER_ID, "A10").build()

    def test_build_sets_statnett_receiver(self) -> None:
        doc = (
            BidDocument(tso=TSO.STATNETT)
            .sender(SENDER_ID, "A10")
            .add_bid(_simple_bid())  # type: ignore[arg-type]
            .build()
        )
        assert doc.model.receiver_mrid == "10X1001A1001A38Y"

    def test_build_sets_statnett_domain(self) -> None:
        doc = (
            BidDocument(tso=TSO.STATNETT)
            .sender(SENDER_ID, "A10")
            .add_bid(_simple_bid())  # type: ignore[arg-type]
            .build()
        )
        assert doc.model.domain_mrid == "10YNO-0--------C"

    def test_build_period_from_single_bid(self) -> None:
        bid = _simple_bid(mtu="2026-03-21T10:00Z")
        doc = (
            BidDocument(tso=TSO.STATNETT)
            .sender(SENDER_ID, "A10")
            .add_bid(bid)  # type: ignore[arg-type]
            .build()
        )
        expected_start = datetime(2026, 3, 21, 10, 0, tzinfo=UTC)
        expected_end = datetime(2026, 3, 21, 10, 15, tzinfo=UTC)
        assert doc.model.reserve_bid_period_start == expected_start
        assert doc.model.reserve_bid_period_end == expected_end

    def test_build_period_spans_multiple_bids(self) -> None:
        bid1 = _simple_bid(mtu="2026-03-21T10:00Z")
        bid2 = _simple_bid(mtu="2026-03-21T10:15Z")
        bid3 = _simple_bid(mtu="2026-03-21T10:30Z")
        doc = (
            BidDocument(tso=TSO.STATNETT)
            .sender(SENDER_ID, "A10")
            .add_bids([bid1, bid2, bid3])  # type: ignore[list-item]
            .build()
        )
        expected_start = datetime(2026, 3, 21, 10, 0, tzinfo=UTC)
        expected_end = datetime(2026, 3, 21, 10, 45, tzinfo=UTC)
        assert doc.model.reserve_bid_period_start == expected_start
        assert doc.model.reserve_bid_period_end == expected_end

    def test_build_includes_subject_as_sender(self) -> None:
        doc = (
            BidDocument(tso=TSO.STATNETT)
            .sender(SENDER_ID, "A10")
            .add_bid(_simple_bid())  # type: ignore[arg-type]
            .build()
        )
        assert doc.model.subject_mrid == SENDER_ID

    def test_time_series_count(self) -> None:
        doc = (
            BidDocument(tso=TSO.STATNETT)
            .sender(SENDER_ID, "A10")
            .add_bid(_simple_bid())  # type: ignore[arg-type]
            .add_bid(_simple_bid())  # type: ignore[arg-type]
            .build()
        )
        assert doc.time_series_count == 2

    def test_revision_number_always_one(self) -> None:
        doc = (
            BidDocument(tso=TSO.STATNETT)
            .sender(SENDER_ID, "A10")
            .add_bid(_simple_bid())  # type: ignore[arg-type]
            .build()
        )
        assert doc.model.revision_number == "1"

    def test_document_type_a37(self) -> None:
        doc = (
            BidDocument(tso=TSO.STATNETT)
            .sender(SENDER_ID, "A10")
            .add_bid(_simple_bid())  # type: ignore[arg-type]
            .build()
        )
        assert doc.model.document_type == "A37"


class TestBuiltBidDocument:
    def _build(self) -> BuiltBidDocument:
        return (
            BidDocument(tso=TSO.STATNETT)
            .sender(SENDER_ID, "A10")
            .add_bid(_simple_bid())  # type: ignore[arg-type]
            .build()
        )

    def test_validate_returns_empty_for_valid_doc(self) -> None:
        doc = self._build()
        errors = doc.validate(mari_mode=MARIMode.PRE_MARI)
        assert errors == []

    def test_validate_uses_global_mode_when_none(self) -> None:
        doc = self._build()
        # Should not raise; uses default PRE_MARI
        errors = doc.validate()
        assert isinstance(errors, list)

    def test_to_xml_returns_bytes(self) -> None:
        doc = self._build()
        xml = doc.to_xml()
        assert isinstance(xml, bytes)

    def test_to_xml_starts_with_declaration(self) -> None:
        doc = self._build()
        xml = doc.to_xml()
        assert xml.startswith(b"<?xml")

    def test_to_xml_contains_root_element(self) -> None:
        doc = self._build()
        xml = doc.to_xml()
        assert b"ReserveBid_MarketDocument" in xml

    def test_to_xml_contains_bid_time_series(self) -> None:
        doc = self._build()
        xml = doc.to_xml()
        assert b"Bid_TimeSeries" in xml

    def test_validate_catches_statnett_min_volume(self) -> None:
        # Statnett minimum is 10 MW; bid of 5 MW should fail
        small_bid = _simple_bid(volume_mw=5, min_vol=5)
        doc = (
            BidDocument(tso=TSO.STATNETT)
            .sender(SENDER_ID, "A10")
            .add_bid(small_bid)  # type: ignore[arg-type]
            .build()
        )
        errors = doc.validate(mari_mode=MARIMode.PRE_MARI)
        assert len(errors) > 0
        assert any("TSO minimum" in e for e in errors)
