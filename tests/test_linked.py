"""Tests for TechnicalLink builder and conditional link methods on SimpleBidBuilder."""

from __future__ import annotations

import uuid

from nexa_mfrr_eam import Bid, BiddingZone, Direction, MarketProductType, TechnicalLink
from nexa_mfrr_eam.bids.simple import SimpleBidBuilder
from nexa_mfrr_eam.types import ConditionalStatus

MTU_1 = "2026-03-21T10:00Z"
MTU_2 = "2026-03-21T10:15Z"
MTU_3 = "2026-03-21T10:30Z"


# ---------------------------------------------------------------------------
# TechnicalLink builder
# ---------------------------------------------------------------------------


class TestTechnicalLinkBuilder:
    def test_build_returns_tuple_of_models(self) -> None:
        link = (
            TechnicalLink(bidding_zone=BiddingZone.SE2)
            .resource("ZZZ", coding_scheme="NSE")
            .add_mtu(MTU_1, Direction.UP, 26, 41.33, divisible=False)
            .add_mtu(MTU_2, Direction.UP, 26, 41.33, divisible=True, min_volume_mw=6)
            .build()
        )
        assert len(link) == 2

    def test_all_bids_share_link_id(self) -> None:
        link = (
            TechnicalLink(bidding_zone=BiddingZone.SE2)
            .resource("ZZZ", coding_scheme="NSE")
            .add_mtu(MTU_1, Direction.UP, 26, 41.33, divisible=False)
            .add_mtu(MTU_2, Direction.UP, 26, 41.33, divisible=True, min_volume_mw=6)
            .build()
        )
        link_ids = {b.linked_bids_identification for b in link}
        assert (
            len(link_ids) == 1
        ), "All bids must share the same linkedBidsIdentification"

    def test_link_id_is_uuid_format(self) -> None:
        builder = TechnicalLink()
        # Should not raise
        uuid.UUID(builder.link_id)

    def test_explicit_link_id(self) -> None:
        custom_id = "ea44a00a-1d3b-455a-92b8-aae808719978"
        link = (
            TechnicalLink(link_id=custom_id, bidding_zone=BiddingZone.SE2)
            .resource("ZZZ", coding_scheme="NSE")
            .add_mtu(MTU_1, Direction.UP, 26, 41.33, divisible=False)
            .build()
        )
        assert link[0].linked_bids_identification == custom_id

    def test_indivisible_bid_no_min_quantity(self) -> None:
        link = (
            TechnicalLink(bidding_zone=BiddingZone.SE2)
            .resource("ZZZ", coding_scheme="NSE")
            .add_mtu(MTU_1, Direction.UP, 26, 41.33, divisible=False)
            .build()
        )
        assert link[0].divisible_code == "A02"
        assert link[0].period.point.minimum_quantity is None

    def test_divisible_bid_has_min_quantity(self) -> None:
        link = (
            TechnicalLink(bidding_zone=BiddingZone.SE2)
            .resource("ZZZ", coding_scheme="NSE")
            .add_mtu(MTU_1, Direction.UP, 26, 41.33, divisible=True, min_volume_mw=6)
            .build()
        )
        assert link[0].divisible_code == "A01"
        assert link[0].period.point.minimum_quantity is not None

    def test_resource_applied_to_all_bids(self) -> None:
        link = (
            TechnicalLink(bidding_zone=BiddingZone.SE2)
            .resource("ZZZ", coding_scheme="NSE")
            .add_mtu(MTU_1, Direction.UP, 26, 41.33, divisible=False)
            .add_mtu(MTU_2, Direction.UP, 26, 41.33, divisible=True, min_volume_mw=6)
            .build()
        )
        for bid in link:
            assert bid.registered_resource_mrid == "ZZZ"
            assert bid.registered_resource_coding_scheme == "NSE"

    def test_max_duration_applied_to_all(self) -> None:
        link = (
            TechnicalLink(bidding_zone=BiddingZone.SE2)
            .resource("ZZZ", coding_scheme="NSE")
            .max_duration(minutes=15)
            .add_mtu(MTU_1, Direction.UP, 26, 41.33, divisible=False)
            .add_mtu(MTU_2, Direction.UP, 26, 41.33, divisible=False)
            .build()
        )
        for bid in link:
            assert bid.maximum_constraint_duration == "PT15M"

    def test_resting_time_applied_to_all(self) -> None:
        link = (
            TechnicalLink(bidding_zone=BiddingZone.SE2)
            .resource("ZZZ", coding_scheme="NSE")
            .resting_time(minutes=30)
            .add_mtu(MTU_1, Direction.UP, 26, 41.33, divisible=False)
            .build()
        )
        assert link[0].resting_constraint_duration == "PT30M"

    def test_mtu_start_times_are_correct(self) -> None:
        from datetime import UTC, datetime

        link = (
            TechnicalLink(bidding_zone=BiddingZone.SE2)
            .resource("ZZZ", coding_scheme="NSE")
            .add_mtu(MTU_1, Direction.UP, 26, 41.33, divisible=False)
            .add_mtu(MTU_2, Direction.UP, 26, 41.33, divisible=True, min_volume_mw=6)
            .add_mtu(MTU_3, Direction.UP, 26, 41.33, divisible=True, min_volume_mw=14)
            .build()
        )
        assert link[0].period.time_interval_start == datetime(
            2026, 3, 21, 10, 0, tzinfo=UTC
        )
        assert link[1].period.time_interval_start == datetime(
            2026, 3, 21, 10, 15, tzinfo=UTC
        )
        assert link[2].period.time_interval_start == datetime(
            2026, 3, 21, 10, 30, tzinfo=UTC
        )

    def test_per_mtu_bidding_zone_override(self) -> None:
        link = (
            TechnicalLink(bidding_zone=BiddingZone.SE2)
            .resource("ZZZ", coding_scheme="NSE")
            .add_mtu(
                MTU_1,
                Direction.UP,
                26,
                41.33,
                divisible=False,
                bidding_zone=BiddingZone.SE3,
            )
            .build()
        )
        assert link[0].connecting_domain_mrid == BiddingZone.SE3.value

    def test_per_mtu_mrid_override(self) -> None:
        custom_mrid = "e6816f14-1f44-48a8-8dd5-233fcb499426"
        link = (
            TechnicalLink(bidding_zone=BiddingZone.SE2)
            .resource("ZZZ", coding_scheme="NSE")
            .add_mtu(MTU_1, Direction.UP, 26, 41.33, divisible=False, mrid=custom_mrid)
            .build()
        )
        assert link[0].mrid == custom_mrid

    def test_product_type_set_correctly(self) -> None:
        link = (
            TechnicalLink(bidding_zone=BiddingZone.SE2)
            .resource("ZZZ", coding_scheme="NSE")
            .add_mtu(
                MTU_1,
                Direction.UP,
                26,
                41.33,
                divisible=False,
                product_type=MarketProductType.SCHEDULED_ONLY,
            )
            .build()
        )
        assert (
            link[0].standard_market_product_type
            == MarketProductType.SCHEDULED_ONLY.value
        )

    def test_empty_link_returns_empty_tuple(self) -> None:
        link = TechnicalLink(bidding_zone=BiddingZone.SE2).build()
        assert link == ()


# ---------------------------------------------------------------------------
# SimpleBidBuilder conditional link methods
# ---------------------------------------------------------------------------


class TestConditionalLinkMethods:
    def _base_bid(self, mtu: str = MTU_1) -> SimpleBidBuilder:
        return (
            Bid.up(volume_mw=30, price_eur=70.00)
            .divisible(min_volume_mw=10)
            .for_mtu(mtu)
            .resource("ZZZ", coding_scheme="NSE")
            .bidding_zone(BiddingZone.SE1)
            .product_type(MarketProductType.SCHEDULED_AND_DIRECT)
        )

    def test_conditionally_available_sets_status(self) -> None:
        bid = self._base_bid().conditionally_available().build()
        assert bid.status_value == "A65"

    def test_conditionally_unavailable_sets_status(self) -> None:
        bid = self._base_bid().conditionally_unavailable().build()
        assert bid.status_value == "A66"

    def test_default_status_is_a06(self) -> None:
        bid = self._base_bid().build()
        assert bid.status_value == "A06"

    def test_link_to_adds_linked_bid(self) -> None:
        earlier_bid = self._base_bid(MTU_1).build()
        later_bid = (
            self._base_bid(MTU_2)
            .conditionally_available()
            .link_to(earlier_bid, ConditionalStatus.NOT_AVAILABLE_IF_ACTIVATED)
            .build()
        )
        assert len(later_bid.linked_bid_time_series) == 1
        assert later_bid.linked_bid_time_series[0].mrid == earlier_bid.mrid
        assert later_bid.linked_bid_time_series[0].status_value == "A55"

    def test_link_to_multiple_bids(self) -> None:
        bid1 = self._base_bid(MTU_1).build()
        bid2 = self._base_bid(MTU_2).build()
        bid3 = (
            self._base_bid(MTU_3)
            .conditionally_available()
            .link_to(bid1, ConditionalStatus.NOT_AVAILABLE_IF_ACTIVATED)
            .link_to(bid2, ConditionalStatus.AVAILABLE_IF_ACTIVATED)
            .build()
        )
        assert len(bid3.linked_bid_time_series) == 2
        assert bid3.linked_bid_time_series[0].status_value == "A55"
        assert bid3.linked_bid_time_series[1].status_value == "A56"

    def test_available_if_linked_activated_status(self) -> None:
        earlier = self._base_bid(MTU_1).build()
        later = (
            self._base_bid(MTU_2)
            .conditionally_unavailable()
            .link_to(earlier, ConditionalStatus.AVAILABLE_IF_LINKED_ACTIVATED)
            .build()
        )
        assert later.linked_bid_time_series[0].status_value == "A67"

    def test_no_links_by_default(self) -> None:
        bid = self._base_bid().build()
        assert bid.linked_bid_time_series == ()


# ---------------------------------------------------------------------------
# XML serialization of Linked_BidTimeSeries
# ---------------------------------------------------------------------------


class TestLinkedBidTimeSeriesXml:
    def test_linked_bid_serialized_in_xml(self) -> None:
        from nexa_mfrr_eam import TSO, BidDocument

        earlier = (
            Bid.up(volume_mw=71, price_eur=93.57)
            .divisible(min_volume_mw=30)
            .for_mtu("2022-02-03T22:15Z")
            .resource("ZZZ", coding_scheme="NSE")
            .bidding_zone(BiddingZone.SE1)
            .product_type(MarketProductType.SCHEDULED_AND_DIRECT)
            .build()
        )
        later = (
            Bid.up(volume_mw=30, price_eur=45.06)
            .divisible(min_volume_mw=0)
            .for_mtu("2022-02-03T22:30Z")
            .resource("ZZZ", coding_scheme="NSE")
            .bidding_zone(BiddingZone.SE1)
            .product_type(MarketProductType.SCHEDULED_ONLY)
            .conditionally_unavailable()
            .link_to(earlier, ConditionalStatus.AVAILABLE_IF_LINKED_ACTIVATED)
            .build()
        )

        doc = (
            BidDocument(tso=TSO.SVK)
            .sender(party_id="99999", coding_scheme="NSE")
            .add_bid(earlier)
            .add_bid(later)
            .build()
        )
        xml = doc.to_xml().decode("utf-8")

        assert "<Linked_BidTimeSeries>" in xml
        assert earlier.mrid in xml
        assert "<value>A67</value>" in xml

    def test_technical_link_serialized_in_xml(self) -> None:
        from nexa_mfrr_eam import TSO, BidDocument

        link_bids = (
            TechnicalLink(bidding_zone=BiddingZone.SE2)
            .resource("ZZZ", coding_scheme="NSE")
            .add_mtu(MTU_1, Direction.UP, 26, 41.33, divisible=False)
            .add_mtu(MTU_2, Direction.UP, 26, 41.33, divisible=True, min_volume_mw=6)
            .build()
        )
        link_id = link_bids[0].linked_bids_identification

        doc = (
            BidDocument(tso=TSO.SVK)
            .sender(party_id="99999", coding_scheme="NSE")
            .add_bids(link_bids)
            .build()
        )
        xml = doc.to_xml().decode("utf-8")

        assert link_id is not None
        assert link_id in xml
        assert "<linkedBidsIdentification>" in xml
        assert "10X1001A1001A418" in xml  # SVK receiver EIC
