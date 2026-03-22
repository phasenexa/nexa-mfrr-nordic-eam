"""Technically linked bid builder.

A technical link groups simple bids across consecutive MTUs under a shared
``linkedBidsIdentification`` UUID.  This prevents double-activation when a
bid in one MTU is activated via direct activation and the resource is still
ramping during the next MTU.

Usage::

    from nexa_mfrr_eam import TechnicalLink, BiddingZone, Direction, MarketProductType

    link = (
        TechnicalLink(bidding_zone=BiddingZone.SE2)
        .resource("ZZZ", coding_scheme="NSE")
        .add_mtu(
            mtu="2026-03-21T10:00Z",
            direction=Direction.UP,
            volume_mw=26,
            price_eur=41.33,
            product_type=MarketProductType.SCHEDULED_AND_DIRECT,
            divisible=False,
        )
        .add_mtu(
            mtu="2026-03-21T10:15Z",
            direction=Direction.UP,
            volume_mw=26,
            price_eur=41.33,
            product_type=MarketProductType.SCHEDULED_AND_DIRECT,
            divisible=True,
            min_volume_mw=6,
        )
        .build()
    )

    doc = (
        BidDocument(tso=TSO.SVK)
        .sender(party_id="99999", coding_scheme="NSE")
        .add_bids(link)
        .build()
    )
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Self

from nexa_mfrr_eam.bids.simple import SimpleBidBuilder
from nexa_mfrr_eam.types import (
    BiddingZone,
    BidTimeSeriesModel,
    Direction,
    MarketProductType,
)


class TechnicalLink:
    """Builder for a group of technically linked simple bids across MTUs.

    All bids share the same ``linkedBidsIdentification`` UUID, which prevents
    the AOF from activating two consecutive-MTU bids for the same resource
    simultaneously (double-activation guard).

    Create an instance via the constructor, configure shared attributes, then
    call :meth:`add_mtu` for each quarter-hour period.  Call :meth:`build` to
    produce the tuple of :class:`~nexa_mfrr_eam.types.BidTimeSeriesModel`
    instances ready to add to a document.
    """

    def __init__(
        self,
        bidding_zone: BiddingZone | None = None,
        link_id: str | None = None,
    ) -> None:
        """Initialise the technical link builder.

        Args:
            bidding_zone: The connecting domain (bidding zone) that all bids
                in this link share.  Can also be set per-MTU via
                :meth:`add_mtu`.
            link_id: UUID for the link group.  Auto-generated if omitted.
        """
        self._bidding_zone = bidding_zone
        self._link_id: str = link_id or str(uuid.uuid4())
        self._resource_id: str | None = None
        self._resource_coding_scheme: str | None = None
        self._max_constraint: str | None = None
        self._resting_constraint: str | None = None
        self._mtu_configs: list[dict[str, Any]] = []

    def resource(self, resource_id: str, coding_scheme: str = "A01") -> Self:
        """Set the registered resource identifier for all bids in this link.

        Args:
            resource_id: Resource identifier (e.g. ``"ZZZ"`` with NSE scheme,
                or an EIC code with A01 scheme).
            coding_scheme: Coding scheme (``"A01"`` EIC, ``"NSE"``, etc.).

        Returns:
            This builder (for method chaining).
        """
        self._resource_id = resource_id
        self._resource_coding_scheme = coding_scheme
        return self

    def max_duration(self, minutes: int) -> Self:
        """Set the maximum activation duration for all bids in this link.

        Args:
            minutes: Maximum activation duration in minutes.

        Returns:
            This builder (for method chaining).
        """
        self._max_constraint = f"PT{minutes}M"
        return self

    def resting_time(self, minutes: int) -> Self:
        """Set the required resting time between activations for all bids.

        Args:
            minutes: Resting time in minutes.

        Returns:
            This builder (for method chaining).
        """
        self._resting_constraint = f"PT{minutes}M"
        return self

    def add_mtu(
        self,
        mtu: str | datetime,
        direction: Direction,
        volume_mw: int,
        price_eur: float | Decimal,
        product_type: MarketProductType = MarketProductType.SCHEDULED_AND_DIRECT,
        divisible: bool = True,
        min_volume_mw: int | None = None,
        bidding_zone: BiddingZone | None = None,
        mrid: str | None = None,
    ) -> Self:
        """Add a bid for one MTU to this link group.

        Args:
            mtu: MTU start time as ISO 8601 string or timezone-aware datetime.
            direction: Regulation direction (UP or DOWN).
            volume_mw: Bid volume in MW.
            price_eur: Bid price in EUR/MWh.
            product_type: Market product type.  Defaults to
                ``SCHEDULED_AND_DIRECT``.
            divisible: Whether the bid is divisible.  Defaults to ``True``.
            min_volume_mw: Minimum activation volume for divisible bids.
                Required when ``divisible=True``.
            bidding_zone: Override the link-level bidding zone for this MTU.
            mrid: Override the auto-generated mRID for this bid.

        Returns:
            This builder (for method chaining).
        """
        self._mtu_configs.append(
            {
                "mtu": mtu,
                "direction": direction,
                "volume_mw": volume_mw,
                "price_eur": price_eur,
                "product_type": product_type,
                "divisible": divisible,
                "min_volume_mw": min_volume_mw,
                "bidding_zone": bidding_zone,
                "mrid": mrid,
            }
        )
        return self

    @property
    def link_id(self) -> str:
        """The UUID identifying this technical link group."""
        return self._link_id

    def build(self) -> tuple[BidTimeSeriesModel, ...]:
        """Build all bids in this technical link group.

        Returns:
            A tuple of frozen :class:`~nexa_mfrr_eam.types.BidTimeSeriesModel`
            instances, one per :meth:`add_mtu` call, all sharing the same
            ``linkedBidsIdentification``.

        Raises:
            :class:`~nexa_mfrr_eam.exceptions.BidValidationError`: If any
                individual bid fails builder validation.
        """
        bids: list[BidTimeSeriesModel] = []
        for cfg in self._mtu_configs:
            builder = SimpleBidBuilder(
                direction=cfg["direction"],
                volume_mw=cfg["volume_mw"],
                price_eur=Decimal(str(cfg["price_eur"])),
            )
            builder.for_mtu(cfg["mtu"])
            builder.product_type(cfg["product_type"])
            builder.technical_link(self._link_id)

            if cfg["divisible"]:
                builder.divisible(
                    min_volume_mw=cfg["min_volume_mw"]
                    if cfg["min_volume_mw"] is not None
                    else cfg["volume_mw"]
                )
            else:
                builder.indivisible()

            zone = cfg["bidding_zone"] or self._bidding_zone
            if zone is not None:
                builder.bidding_zone(zone)

            if self._resource_id is not None:
                builder.resource(
                    self._resource_id,
                    coding_scheme=self._resource_coding_scheme or "A01",
                )

            if self._max_constraint is not None:
                builder._max_constraint = self._max_constraint
            if self._resting_constraint is not None:
                builder._resting_constraint = self._resting_constraint

            if cfg["mrid"] is not None:
                builder.with_mrid(cfg["mrid"])

            bids.append(builder.build())
        return tuple(bids)
