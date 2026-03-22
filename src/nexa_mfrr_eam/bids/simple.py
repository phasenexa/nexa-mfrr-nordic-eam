"""Simple bid builder with fluent API.

A simple bid covers a single MTU (15-minute period) with one price and one
volume.  Use :class:`Bid` as the entry point::

    bid = (
        Bid.up(volume_mw=50, price_eur=85.50)
        .divisible(min_volume_mw=10)
        .for_mtu("2026-03-21T10:00Z")
        .resource("NOKG90901", coding_scheme="NNO")
        .product_type(MarketProductType.SCHEDULED_AND_DIRECT)
        .build()
    )
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Self

from nexa_mfrr_eam.exceptions import BidValidationError
from nexa_mfrr_eam.types import (
    BiddingZone,
    BidTimeSeriesModel,
    Direction,
    MarketProductType,
    PeriodModel,
    PointModel,
    ReasonModel,
)


class SimpleBidBuilder:
    """Mutable builder for simple bids.

    Use :meth:`Bid.up` or :meth:`Bid.down` to create an instance.
    Call :meth:`build` when all required fields have been set.
    """

    def __init__(
        self,
        direction: Direction,
        volume_mw: int,
        price_eur: Decimal | None,
    ) -> None:
        """Initialise the builder.

        Args:
            direction: Regulation direction (UP or DOWN).
            volume_mw: Bid volume in MW.
            price_eur: Bid price in EUR/MWh, or None for period-shift-only bids.
        """
        self._direction = direction
        self._volume_mw = volume_mw
        self._price_eur = price_eur
        self._mtu_start: datetime | None = None
        self._divisible: bool | None = None
        self._min_volume_mw: int | None = None
        self._resource_id: str | None = None
        self._resource_coding_scheme: str | None = None
        self._product_type: MarketProductType | None = None
        self._bidding_zone: BiddingZone | None = None
        self._mrid: str | None = None
        self._status: str = "A06"
        self._linked_bids_id: str | None = None
        self._activation_constraint: str | None = None
        self._max_constraint: str | None = None
        self._resting_constraint: str | None = None
        self._reasons: list[ReasonModel] = []

    def divisible(self, min_volume_mw: int) -> Self:
        """Mark the bid as divisible with the given minimum activation volume.

        Args:
            min_volume_mw: Minimum volume that can be activated in MW.

        Returns:
            This builder (for method chaining).
        """
        self._divisible = True
        self._min_volume_mw = min_volume_mw
        return self

    def indivisible(self) -> Self:
        """Mark the bid as indivisible (must be fully activated or not at all).

        Returns:
            This builder (for method chaining).
        """
        self._divisible = False
        self._min_volume_mw = None
        return self

    def for_mtu(self, mtu: str | datetime) -> Self:
        """Set the MTU start time.

        Args:
            mtu: ISO 8601 string (e.g. ``"2026-03-21T10:00Z"`` or with
                ``+00:00`` offset) or a timezone-aware :class:`datetime`.

        Returns:
            This builder (for method chaining).

        Raises:
            ValueError: If the datetime is not timezone-aware, not on a
                15-minute boundary, or has non-zero seconds/microseconds.
        """
        if isinstance(mtu, str):
            # Python 3.11+ fromisoformat handles +00:00; replace Z for compat
            normalised = mtu.replace("Z", "+00:00")
            dt: datetime = datetime.fromisoformat(normalised)
        else:
            dt = mtu
        if dt.tzinfo is None:
            raise ValueError("MTU datetime must be timezone-aware (UTC)")
        dt_utc = dt.astimezone(UTC)
        if dt_utc.second != 0 or dt_utc.microsecond != 0:
            raise ValueError(
                f"MTU must be on 15-minute boundary with no seconds: {dt_utc}"
            )
        if dt_utc.minute not in (0, 15, 30, 45):
            raise ValueError(
                f"MTU minute must be 0, 15, 30, or 45; got {dt_utc.minute}"
            )
        self._mtu_start = dt_utc
        return self

    def resource(self, resource_id: str, coding_scheme: str = "A01") -> Self:
        """Set the registered resource mRID and coding scheme.

        Args:
            resource_id: Resource identifier (e.g. ``"NOKG90901"`` for NNO,
                or an EIC code for A01).
            coding_scheme: Coding scheme code (``"A01"`` EIC, ``"NNO"``,
                ``"NSE"``, etc.).  Defaults to ``"A01"``.

        Returns:
            This builder (for method chaining).
        """
        self._resource_id = resource_id
        self._resource_coding_scheme = coding_scheme
        return self

    def product_type(self, product_type: MarketProductType) -> Self:
        """Set the market product type.

        Args:
            product_type: One of :class:`~nexa_mfrr_eam.types.MarketProductType`.

        Returns:
            This builder (for method chaining).
        """
        self._product_type = product_type
        return self

    def bidding_zone(self, zone: BiddingZone) -> Self:
        """Set the connecting domain (bidding zone) for this bid.

        Args:
            zone: One of :class:`~nexa_mfrr_eam.types.BiddingZone`.

        Returns:
            This builder (for method chaining).
        """
        self._bidding_zone = zone
        return self

    def with_mrid(self, mrid: str) -> Self:
        """Override the auto-generated mRID for this bid.

        Args:
            mrid: The mRID to use (max 60 characters per XSD ``ID_String``).

        Returns:
            This builder (for method chaining).
        """
        self._mrid = mrid
        return self

    def technical_link(self, link_id: str) -> Self:
        """Attach this bid to a technical link group.

        Args:
            link_id: UUID identifying the technical link group.

        Returns:
            This builder (for method chaining).
        """
        self._linked_bids_id = link_id
        return self

    def faster_activation(self, minutes: int) -> Self:
        """Set faster activation time as an ISO 8601 duration.

        The duration includes the 1-minute preparation time mandated by
        Statnett.  For example, a 2-minute ramp means ``minutes=3``.

        Args:
            minutes: Total activation time in minutes (prep + ramp).

        Returns:
            This builder (for method chaining).
        """
        self._activation_constraint = f"PT{minutes}M"
        return self

    def max_duration(self, minutes: int) -> Self:
        """Set the maximum activation duration.

        Args:
            minutes: Maximum duration in minutes.

        Returns:
            This builder (for method chaining).
        """
        self._max_constraint = f"PT{minutes}M"
        return self

    def resting_time(self, minutes: int) -> Self:
        """Set the required resting time between consecutive activations.

        Args:
            minutes: Resting time in minutes.

        Returns:
            This builder (for method chaining).
        """
        self._resting_constraint = f"PT{minutes}M"
        return self

    def build(self) -> BidTimeSeriesModel:
        """Validate all required fields and return an immutable model.

        Returns:
            A frozen :class:`~nexa_mfrr_eam.types.BidTimeSeriesModel`.

        Raises:
            :class:`~nexa_mfrr_eam.exceptions.BidValidationError`: If any
                required field has not been set.
        """
        errors: list[str] = []
        if self._mtu_start is None:
            errors.append("for_mtu() must be called before build()")
        if self._divisible is None:
            errors.append("divisible() or indivisible() must be called before build()")
        if self._product_type is None:
            errors.append("product_type() must be called before build()")
        if errors:
            raise BidValidationError(errors)

        # Type-narrowed after error checks above
        mtu_start: datetime = self._mtu_start  # type: ignore[assignment]
        mtu_end = mtu_start + timedelta(minutes=15)

        point = PointModel(
            position=1,
            quantity=Decimal(str(self._volume_mw)),
            minimum_quantity=(
                Decimal(str(self._min_volume_mw))
                if self._min_volume_mw is not None
                else None
            ),
            energy_price=self._price_eur,
        )
        period = PeriodModel(
            time_interval_start=mtu_start,
            time_interval_end=mtu_end,
            point=point,
        )
        return BidTimeSeriesModel(
            mrid=self._mrid or str(uuid.uuid4()),
            auction_mrid="MFRR_ENERGY_ACTIVATION_MARKET",
            business_type="B74",
            acquiring_domain_mrid="10Y1001A1001A91G",
            connecting_domain_mrid=(
                self._bidding_zone.value if self._bidding_zone else None
            ),
            quantity_measure_unit_name="MAW",
            currency_unit_name="EUR",
            divisible_code="A01" if self._divisible else "A02",
            status_value=self._status,
            registered_resource_mrid=self._resource_id,
            registered_resource_coding_scheme=self._resource_coding_scheme,
            flow_direction=self._direction.value,
            energy_price_measure_unit_name="MWH",
            activation_constraint_duration=self._activation_constraint,
            resting_constraint_duration=self._resting_constraint,
            maximum_constraint_duration=self._max_constraint,
            standard_market_product_type=(
                self._product_type.value if self._product_type else None
            ),
            linked_bids_identification=self._linked_bids_id,
            period=period,
            reasons=tuple(self._reasons),
        )


class Bid:
    """Factory for creating simple bid builders using the fluent API.

    Usage::

        bid = (
            Bid.up(volume_mw=50, price_eur=85.50)
            .divisible(min_volume_mw=10)
            .for_mtu("2026-03-21T10:00Z")
            .resource("NOKG90901", coding_scheme="NNO")
            .product_type(MarketProductType.SCHEDULED_AND_DIRECT)
            .build()
        )
    """

    @classmethod
    def up(
        cls,
        volume_mw: int,
        price_eur: float | Decimal | None = None,
    ) -> SimpleBidBuilder:
        """Create an up-regulation bid builder.

        Args:
            volume_mw: Bid volume in MW.
            price_eur: Bid price in EUR/MWh (omit for period-shift-only bids).

        Returns:
            A :class:`SimpleBidBuilder` configured for up-regulation.
        """
        price = Decimal(str(price_eur)) if price_eur is not None else None
        return SimpleBidBuilder(Direction.UP, volume_mw, price)

    @classmethod
    def down(
        cls,
        volume_mw: int,
        price_eur: float | Decimal | None = None,
    ) -> SimpleBidBuilder:
        """Create a down-regulation bid builder.

        Args:
            volume_mw: Bid volume in MW.
            price_eur: Bid price in EUR/MWh (omit for period-shift-only bids).

        Returns:
            A :class:`SimpleBidBuilder` configured for down-regulation.
        """
        price = Decimal(str(price_eur)) if price_eur is not None else None
        return SimpleBidBuilder(Direction.DOWN, volume_mw, price)
