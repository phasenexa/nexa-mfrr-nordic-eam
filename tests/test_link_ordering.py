"""Tests for the technical link ordering module."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from nexa_mfrr_eam import (
    Bid,
    BiddingZone,
    Direction,
    MarketProductType,
    assign_technical_links,
)

MTU_1 = datetime(2026, 3, 21, 10, 0, tzinfo=UTC)
MTU_2 = datetime(2026, 3, 21, 10, 15, tzinfo=UTC)
MTU_3 = datetime(2026, 3, 21, 10, 30, tzinfo=UTC)
MTU_4 = datetime(2026, 3, 21, 10, 45, tzinfo=UTC)


def _up_bid(price: float, mtu: datetime, volume: int = 20) -> object:
    return (
        Bid.up(volume_mw=volume, price_eur=price)
        .divisible(min_volume_mw=5)
        .for_mtu(mtu)
        .bidding_zone(BiddingZone.NO2)
        .resource("NOKG90901", coding_scheme="NNO")
        .product_type(MarketProductType.SCHEDULED_AND_DIRECT)
        .build()
    )


def _down_bid(price: float, mtu: datetime, volume: int = 20) -> object:
    return (
        Bid.down(volume_mw=volume, price_eur=price)
        .divisible(min_volume_mw=5)
        .for_mtu(mtu)
        .bidding_zone(BiddingZone.NO2)
        .resource("NOKG90901", coding_scheme="NNO")
        .product_type(MarketProductType.SCHEDULED_AND_DIRECT)
        .build()
    )


# ---------------------------------------------------------------------------
# Basic ordering – up bids
# ---------------------------------------------------------------------------


class TestUpBidOrdering:
    def test_two_tiers_three_mtus_same_rank_same_link(self) -> None:
        bids = [
            _up_bid(50.0, MTU_1),
            _up_bid(80.0, MTU_1),
            _up_bid(53.0, MTU_2),
            _up_bid(83.0, MTU_2),
            _up_bid(48.0, MTU_3),
            _up_bid(78.0, MTU_3),
        ]
        result = assign_technical_links(bids, direction=Direction.UP)

        # Build lookup: mtu -> sorted bids by price
        by_mtu: dict[datetime, list] = {}
        for b in result:
            by_mtu.setdefault(b.period.time_interval_start, []).append(b)

        # Within each MTU, the cheaper bid (rank 0) should share the same link ID
        rank0_links = set()
        rank1_links = set()
        for mtu in [MTU_1, MTU_2, MTU_3]:
            sorted_bids = sorted(by_mtu[mtu], key=lambda b: b.period.point.energy_price)
            rank0_links.add(sorted_bids[0].linked_bids_identification)
            rank1_links.add(sorted_bids[1].linked_bids_identification)

        # All rank-0 bids share the same link UUID
        assert len(rank0_links) == 1
        # All rank-1 bids share a different link UUID
        assert len(rank1_links) == 1
        # The two link UUIDs are different
        assert rank0_links != rank1_links

    def test_all_bids_get_a_link(self) -> None:
        bids = [_up_bid(50.0, MTU_1)]
        result = assign_technical_links(bids, direction=Direction.UP)
        assert result[0].linked_bids_identification is not None

    def test_single_tier_single_mtu(self) -> None:
        bids = [_up_bid(100.0, MTU_1)]
        result = assign_technical_links(bids, direction=Direction.UP)
        assert len(result) == 1
        assert result[0].linked_bids_identification is not None


# ---------------------------------------------------------------------------
# Basic ordering – down bids
# ---------------------------------------------------------------------------


class TestDownBidOrdering:
    def test_down_bids_sorted_descending(self) -> None:
        # 3 down tiers: 40, 20, 10 EUR/MWh
        # rank 0 -> 40 (highest first for DOWN), rank 1 -> 20, rank 2 -> 10
        bids = [
            _down_bid(40.0, MTU_1),
            _down_bid(20.0, MTU_1),
            _down_bid(10.0, MTU_1),
            _down_bid(38.0, MTU_2),
            _down_bid(18.0, MTU_2),
            _down_bid(9.0, MTU_2),
        ]
        result = assign_technical_links(bids, direction=Direction.DOWN)

        by_mtu: dict[datetime, list] = {}
        for b in result:
            by_mtu.setdefault(b.period.time_interval_start, []).append(b)

        # For DOWN: highest price = rank 0
        rank0_links: set[str] = set()
        rank1_links: set[str] = set()
        rank2_links: set[str] = set()
        for mtu in [MTU_1, MTU_2]:
            sorted_bids = sorted(
                by_mtu[mtu],
                key=lambda b: b.period.point.energy_price,
                reverse=True,
            )
            rank0_links.add(sorted_bids[0].linked_bids_identification)
            rank1_links.add(sorted_bids[1].linked_bids_identification)
            rank2_links.add(sorted_bids[2].linked_bids_identification)

        assert len(rank0_links) == 1
        assert len(rank1_links) == 1
        assert len(rank2_links) == 1
        # All three are distinct link IDs
        assert len(rank0_links | rank1_links | rank2_links) == 3


# ---------------------------------------------------------------------------
# Gap handling
# ---------------------------------------------------------------------------


class TestGapHandling:
    def test_same_link_across_non_consecutive_mtus(self) -> None:
        # Bid exists in MTU_1 and MTU_3 but not MTU_2
        bids = [
            _up_bid(50.0, MTU_1),
            _up_bid(80.0, MTU_1),
            _up_bid(48.0, MTU_3),
            _up_bid(78.0, MTU_3),
        ]
        result = assign_technical_links(bids, direction=Direction.UP)

        by_mtu: dict[datetime, list] = {}
        for b in result:
            by_mtu.setdefault(b.period.time_interval_start, []).append(b)

        rank0_links = set()
        for mtu in [MTU_1, MTU_3]:
            sorted_bids = sorted(by_mtu[mtu], key=lambda b: b.period.point.energy_price)
            rank0_links.add(sorted_bids[0].linked_bids_identification)

        assert len(rank0_links) == 1  # same link UUID across the gap


# ---------------------------------------------------------------------------
# Uneven tiers
# ---------------------------------------------------------------------------


class TestUnevenTiers:
    def test_mtu_with_fewer_tiers_uses_subset_of_links(self) -> None:
        # MTU_1 has 3 tiers, MTU_2 has 2 tiers
        bids = [
            _up_bid(50.0, MTU_1),
            _up_bid(75.0, MTU_1),
            _up_bid(100.0, MTU_1),
            _up_bid(52.0, MTU_2),
            _up_bid(77.0, MTU_2),
        ]
        result = assign_technical_links(bids, direction=Direction.UP)
        # All bids should have a link
        for b in result:
            assert b.linked_bids_identification is not None

        by_mtu: dict[datetime, list] = {}
        for b in result:
            by_mtu.setdefault(b.period.time_interval_start, []).append(b)

        mtu1_sorted = sorted(by_mtu[MTU_1], key=lambda b: b.period.point.energy_price)
        mtu2_sorted = sorted(by_mtu[MTU_2], key=lambda b: b.period.point.energy_price)

        # rank 0 and rank 1 link IDs should be consistent across MTUs
        link0_mtu1 = mtu1_sorted[0].linked_bids_identification
        link0_mtu2 = mtu2_sorted[0].linked_bids_identification
        assert link0_mtu1 == link0_mtu2
        link1_mtu1 = mtu1_sorted[1].linked_bids_identification
        link1_mtu2 = mtu2_sorted[1].linked_bids_identification
        assert link1_mtu1 == link1_mtu2
        # MTU2 doesn't use the rank-2 link at all (it only has 2 tiers)


# ---------------------------------------------------------------------------
# GS-adjusted prices: rank consistency despite different actual prices
# ---------------------------------------------------------------------------


class TestGsAdjustedPricesRankConsistency:
    def test_same_rank_same_link_after_gs_adjustment(self) -> None:
        # Simulates bids where prices differ across MTUs due to GS adjustment
        # but rank order stays the same
        bids = [
            _up_bid(153.57, MTU_1),  # tier1 adjusted for MTU1 DA
            _up_bid(216.90, MTU_1),  # tier2 adjusted for MTU1 DA
            _up_bid(161.40, MTU_2),  # tier1 adjusted for MTU2 DA (higher DA)
            _up_bid(222.50, MTU_2),  # tier2 adjusted for MTU2 DA
        ]
        result = assign_technical_links(bids, direction=Direction.UP)

        by_mtu: dict[datetime, list] = {}
        for b in result:
            by_mtu.setdefault(b.period.time_interval_start, []).append(b)

        mtu1_sorted = sorted(by_mtu[MTU_1], key=lambda b: b.period.point.energy_price)
        mtu2_sorted = sorted(by_mtu[MTU_2], key=lambda b: b.period.point.energy_price)

        # Rank 0 (cheapest per MTU) shares the same link UUID
        assert (
            mtu1_sorted[0].linked_bids_identification
            == mtu2_sorted[0].linked_bids_identification
        )
        # Rank 1 (more expensive per MTU) shares a different link UUID
        assert (
            mtu1_sorted[1].linked_bids_identification
            == mtu2_sorted[1].linked_bids_identification
        )


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


class TestValidationErrors:
    def test_raises_if_bids_already_have_links(self) -> None:
        bid = _up_bid(50.0, MTU_1)
        # Manually create a linked version
        linked = bid.model_copy(
            update={"linked_bids_identification": str(uuid.uuid4())}
        )
        with pytest.raises(ValueError, match="already has linked_bids_identification"):
            assign_technical_links([linked], direction=Direction.UP)

    def test_raises_on_duplicate_prices_within_mtu(self) -> None:
        bids = [
            _up_bid(50.0, MTU_1),
            _up_bid(50.0, MTU_1),  # same price – ambiguous ordering
        ]
        with pytest.raises(ValueError, match="Duplicate prices"):
            assign_technical_links(bids, direction=Direction.UP)


# ---------------------------------------------------------------------------
# Link ID format
# ---------------------------------------------------------------------------


class TestLinkIdFormat:
    def test_link_ids_are_valid_uuids(self) -> None:
        bids = [
            _up_bid(50.0, MTU_1),
            _up_bid(80.0, MTU_1),
        ]
        result = assign_technical_links(bids, direction=Direction.UP)
        for bid in result:
            link_id = bid.linked_bids_identification
            assert link_id is not None
            # Should parse without raising
            parsed = uuid.UUID(link_id)
            assert str(parsed) == link_id

    def test_does_not_mutate_original_bids(self) -> None:
        bids = [_up_bid(50.0, MTU_1)]
        assign_technical_links(bids, direction=Direction.UP)
        assert bids[0].linked_bids_identification is None

    def test_returns_new_instances(self) -> None:
        bids = [_up_bid(50.0, MTU_1)]
        result = assign_technical_links(bids, direction=Direction.UP)
        assert result[0] is not bids[0]
