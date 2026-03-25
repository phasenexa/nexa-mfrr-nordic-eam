"""Technical link ordering for mFRR bids following the PowerDesk convention.

PowerDesk assigns technical links to all bids, not just those that need
double-activation protection.  The link ordering follows specific rules that
encode the multipart price stack hierarchy across time:

1. All bids should have a technical link.
2. Technical link IDs are UUIDs.
3. Up bids: lowest-priced bid in each MTU gets rank 0 (first link). Additional
   links added in order of increasing price.
4. Down bids: highest-priced bid gets rank 0. Additional links added in order
   of decreasing price.
5. Links are ordered by price rank (position), not by price value. The same
   rank position across MTUs shares the same link UUID even if actual prices
   differ (e.g. after GS tax adjustment).
6. Gaps are allowed. If a bid exists in QH1 and QH3 but not QH2, the same
   link ID is used for both.
7. Technical links can span multiple days.
8. Within an MTU, each link ID is used by exactly one bid.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from nexa_mfrr_eam.types import Direction

if TYPE_CHECKING:
    from nexa_mfrr_eam.types import BidTimeSeriesModel


def assign_technical_links(
    bids: list[BidTimeSeriesModel],
    direction: Direction,
) -> list[BidTimeSeriesModel]:
    """Assign technical link UUIDs to a set of bids by price rank.

    Bids at the same price rank across MTUs receive the same link UUID.
    For up bids the cheapest bid in each MTU is rank 0; for down bids the
    most expensive bid is rank 0.

    The function returns new :class:`~nexa_mfrr_eam.types.BidTimeSeriesModel`
    instances with ``linked_bids_identification`` populated.  The original bids
    are not mutated.

    Args:
        bids: List of built bids that share the same resource/bidding zone.
            Bids must not already have ``linked_bids_identification`` set.
        direction: Bid direction; determines sort order (ascending for UP,
            descending for DOWN).

    Returns:
        New list of bids with ``linked_bids_identification`` set to a
        consistent UUID per price rank position.

    Raises:
        ValueError: If any bid already has ``linked_bids_identification`` set.
        ValueError: If bids within the same MTU have duplicate prices.

    Examples:
        >>> from nexa_mfrr_eam.types import Direction
        >>> linked = assign_technical_links(my_bids, direction=Direction.UP)
    """
    # Guard: no bids already linked
    for bid in bids:
        if bid.linked_bids_identification is not None:
            raise ValueError(
                f"Bid mRID {bid.mrid} already has linked_bids_identification "
                f"'{bid.linked_bids_identification}'. Remove it before calling "
                "assign_technical_links."
            )

    # Group bids by MTU start time
    by_mtu: dict[datetime, list[BidTimeSeriesModel]] = {}
    for bid in bids:
        mtu_start = bid.period.time_interval_start
        by_mtu.setdefault(mtu_start, []).append(bid)

    # Validate: no duplicate prices within the same MTU
    for mtu_start, mtu_bids in by_mtu.items():
        prices = [b.period.point.energy_price for b in mtu_bids]
        if len(prices) != len(set(prices)):
            raise ValueError(
                f"Duplicate prices within MTU {mtu_start.isoformat()}: {prices}. "
                "Price ordering is ambiguous; deduplicate before assigning links."
            )

    # Determine max number of price tiers across all MTUs
    max_tiers = max((len(v) for v in by_mtu.values()), default=0)

    # Generate one UUID per rank position
    link_uuids: list[str] = [str(uuid.uuid4()) for _ in range(max_tiers)]

    # Assign link UUIDs by rank within each MTU
    # Build a mapping from original bid mRID -> new link UUID
    link_assignments: dict[str, str] = {}

    reverse = direction is Direction.DOWN
    for mtu_bids in by_mtu.values():
        sorted_bids = sorted(
            mtu_bids,
            key=lambda b: b.period.point.energy_price or Decimal("0"),
            reverse=reverse,
        )
        for rank, bid in enumerate(sorted_bids):
            link_assignments[bid.mrid] = link_uuids[rank]

    # Return new bid instances with link IDs populated
    result: list[BidTimeSeriesModel] = []
    for bid in bids:
        link_uuid = link_assignments[bid.mrid]
        result.append(bid.model_copy(update={"linked_bids_identification": link_uuid}))

    return result
