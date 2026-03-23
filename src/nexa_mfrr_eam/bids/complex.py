"""Complex bid group builders with fluent API.

Complex bids are groups of simple bids for the same MTU that share a group
identifier.  Three group types are supported:

- :class:`ExclusiveGroup` — at most one bid in the group can be activated
  (mutually exclusive alternatives).
- :class:`MultipartGroup` — multiple price tiers; if the highest-priced
  component is activated, all cheaper components must also be activated.
- :class:`InclusiveGroup` — all bids must be activated together or not at
  all (used for aggregated DER portfolios, Fingrid / Statnett / SVK only).

All three builders follow the same fluent pattern as :class:`TechnicalLink`:
configure shared attributes, call :meth:`add_component` for each bid, then
call :meth:`build` to receive a tuple of frozen
:class:`~nexa_mfrr_eam.types.BidTimeSeriesModel` instances.

Example – exclusive group for Energinet::

    from nexa_mfrr_eam import (
        ExclusiveGroup, BidDocument, BiddingZone,
        MarketProductType, ProductionType, TSO,
    )

    group = (
        ExclusiveGroup(bidding_zone=BiddingZone.DK1)
        .resource("DK1-RES-001", coding_scheme="A01")
        .product_type(MarketProductType.SCHEDULED_ONLY)
        .for_mtu("2026-03-21T10:00Z")
        .add_component(volume_mw=30, price_eur=60.0, divisible=True,
                       min_volume_mw=10, psr_type=ProductionType.WIND_ONSHORE)
        .add_component(volume_mw=50, price_eur=80.0, divisible=False,
                       psr_type=ProductionType.WIND_ONSHORE)
        .build()
    )

    doc = (
        BidDocument(tso=TSO.ENERGINET)
        .sender(party_id="10XBRP-001-----A", coding_scheme="A01")
        .add_bids(group)
        .build()
    )
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Self

from nexa_mfrr_eam.bids.simple import SimpleBidBuilder
from nexa_mfrr_eam.exceptions import BidValidationError
from nexa_mfrr_eam.types import (
    BiddingZone,
    BidTimeSeriesModel,
    Direction,
    MarketProductType,
    ProductionType,
)

# ---------------------------------------------------------------------------
# Shared internal helpers
# ---------------------------------------------------------------------------


def _make_builder(
    cfg: dict[str, Any],
    group_direction: Direction | None,
    group_mtu: str | None,
    group_product_type: MarketProductType | None,
    group_bidding_zone: BiddingZone | None,
    group_resource_id: str | None,
    group_resource_scheme: str | None,
) -> SimpleBidBuilder:
    """Construct a :class:`SimpleBidBuilder` from a component config dict."""
    direction: Direction = cfg.get("direction") or group_direction  # type: ignore[assignment]
    price_eur: float | Decimal = cfg["price_eur"]
    builder = SimpleBidBuilder(
        direction=direction,
        volume_mw=cfg["volume_mw"],
        price_eur=Decimal(str(price_eur)),
    )
    mtu = cfg.get("mtu") or group_mtu
    if mtu is not None:
        builder.for_mtu(mtu)

    pt = cfg.get("product_type") or group_product_type
    if pt is not None:
        builder.product_type(pt)

    zone = cfg.get("bidding_zone") or group_bidding_zone
    if zone is not None:
        builder.bidding_zone(zone)

    resource_id = cfg.get("resource_id") or group_resource_id
    if resource_id is not None:
        scheme = cfg.get("resource_coding_scheme") or group_resource_scheme or "A01"
        builder.resource(resource_id, coding_scheme=scheme)

    if cfg.get("divisible"):
        min_vol = cfg.get("min_volume_mw")
        effective_min = min_vol if min_vol is not None else cfg["volume_mw"]
        builder.divisible(min_volume_mw=effective_min)
    else:
        builder.indivisible()

    if cfg.get("mrid") is not None:
        builder.with_mrid(cfg["mrid"])

    # duration constraints (optional overrides)
    if cfg.get("max_constraint") is not None:
        builder._max_constraint = cfg["max_constraint"]
    if cfg.get("resting_constraint") is not None:
        builder._resting_constraint = cfg["resting_constraint"]

    return builder


# ---------------------------------------------------------------------------
# ExclusiveGroup
# ---------------------------------------------------------------------------


class ExclusiveGroup:
    """Builder for a group of mutually exclusive bids (at most one activates).

    All components share the same ``exclusiveBidsIdentification`` UUID.  The
    AOF may activate at most one bid from the group per MTU.

    Constraints enforced in :meth:`build`:

    - All components must cover the same MTU.
    - All components must have the same product type.
    - All components must belong to the same bidding zone.

    Usage::

        group = (
            ExclusiveGroup(bidding_zone=BiddingZone.DK1)
            .resource("DK1-RES-001", coding_scheme="A01")
            .product_type(MarketProductType.SCHEDULED_ONLY)
            .for_mtu("2026-03-21T10:00Z")
            .add_component(volume_mw=30, price_eur=60.0, divisible=True,
                           min_volume_mw=10)
            .add_component(volume_mw=50, price_eur=80.0, divisible=False)
            .build()
        )
    """

    def __init__(
        self,
        bidding_zone: BiddingZone | None = None,
        group_id: str | None = None,
    ) -> None:
        """Initialise the exclusive group builder.

        Args:
            bidding_zone: Connecting domain (bidding zone) shared by all
                components.  Can also be set per-component via
                :meth:`add_component`.
            group_id: UUID for the group.  Auto-generated if omitted.
        """
        self._bidding_zone = bidding_zone
        self._group_id: str = group_id or str(uuid.uuid4())
        self._direction: Direction | None = None
        self._mtu: str | None = None
        self._product_type: MarketProductType | None = None
        self._resource_id: str | None = None
        self._resource_scheme: str | None = None
        self._components: list[dict[str, Any]] = []

    def for_mtu(self, mtu: str) -> Self:
        """Set the MTU start time shared by all components.

        Args:
            mtu: ISO 8601 string (e.g. ``"2026-03-21T10:00Z"``).

        Returns:
            This builder (for method chaining).
        """
        self._mtu = mtu
        return self

    def direction(self, direction: Direction) -> Self:
        """Set the regulation direction shared by all components.

        Args:
            direction: UP or DOWN.

        Returns:
            This builder (for method chaining).
        """
        self._direction = direction
        return self

    def product_type(self, product_type: MarketProductType) -> Self:
        """Set the market product type shared by all components.

        Args:
            product_type: One of :class:`~nexa_mfrr_eam.types.MarketProductType`.

        Returns:
            This builder (for method chaining).
        """
        self._product_type = product_type
        return self

    def resource(self, resource_id: str, coding_scheme: str = "A01") -> Self:
        """Set the registered resource identifier shared by all components.

        Args:
            resource_id: Resource identifier.
            coding_scheme: Coding scheme (``"A01"`` EIC, ``"NNO"``, etc.).

        Returns:
            This builder (for method chaining).
        """
        self._resource_id = resource_id
        self._resource_scheme = coding_scheme
        return self

    def add_component(
        self,
        volume_mw: int,
        price_eur: float | Decimal,
        divisible: bool = True,
        min_volume_mw: int | None = None,
        direction: Direction | None = None,
        mtu: str | None = None,
        bidding_zone: BiddingZone | None = None,
        resource_id: str | None = None,
        resource_coding_scheme: str | None = None,
        psr_type: ProductionType | str | None = None,
        note: str | None = None,
        mrid: str | None = None,
    ) -> Self:
        """Add a component bid to the exclusive group.

        Args:
            volume_mw: Bid volume in MW.
            price_eur: Bid price in EUR/MWh.
            divisible: Whether the bid is divisible.  Defaults to ``True``.
            min_volume_mw: Minimum activation volume for divisible bids.
            direction: Override the group-level direction for this component.
            mtu: Override the group-level MTU for this component.
            bidding_zone: Override the group-level bidding zone.
            resource_id: Override the group-level resource identifier.
            resource_coding_scheme: Override the group-level coding scheme.
            psr_type: PSR type for Denmark bids (``ProductionType`` or raw
                string code).
            note: Free-text note for Denmark bids.
            mrid: Override the auto-generated mRID.

        Returns:
            This builder (for method chaining).
        """
        psr_value = psr_type.value if isinstance(psr_type, ProductionType) else psr_type
        self._components.append(
            {
                "volume_mw": volume_mw,
                "price_eur": price_eur,
                "divisible": divisible,
                "min_volume_mw": min_volume_mw,
                "direction": direction,
                "mtu": mtu,
                "bidding_zone": bidding_zone,
                "resource_id": resource_id,
                "resource_coding_scheme": resource_coding_scheme,
                "psr_type": psr_value,
                "note": note,
                "mrid": mrid,
            }
        )
        return self

    @property
    def group_id(self) -> str:
        """The UUID identifying this exclusive group."""
        return self._group_id

    def build(self) -> tuple[BidTimeSeriesModel, ...]:
        """Validate and build all component bids.

        Returns:
            A tuple of frozen :class:`~nexa_mfrr_eam.types.BidTimeSeriesModel`
            instances, all sharing the same ``exclusiveBidsIdentification``.

        Raises:
            :class:`~nexa_mfrr_eam.exceptions.BidValidationError`: If fewer
                than two components are defined, or if the components violate
                exclusive group constraints (same MTU, product type, zone).
        """
        errors = _validate_exclusive_constraints(
            self._components, self._direction, self._mtu
        )
        if errors:
            raise BidValidationError(errors)

        bids: list[BidTimeSeriesModel] = []
        for cfg in self._components:
            builder = _make_builder(
                cfg,
                self._direction,
                self._mtu,
                self._product_type,
                self._bidding_zone,
                self._resource_id,
                self._resource_scheme,
            )
            base = builder.build()
            bids.append(
                base.model_copy(
                    update={
                        "exclusive_bids_identification": self._group_id,
                        "psr_type": cfg.get("psr_type"),
                        "note": cfg.get("note"),
                    }
                )
            )
        return tuple(bids)


# ---------------------------------------------------------------------------
# MultipartGroup
# ---------------------------------------------------------------------------


class MultipartGroup:
    """Builder for a multipart bid group (multiple price tiers, same MTU).

    All components share the same ``multipartBidIdentification`` UUID.  If a
    higher-priced component is activated, all lower-priced components must
    also be activated.

    Constraints enforced in :meth:`build`:

    - At least two components must be added.
    - All components must cover the same MTU.
    - All components must have the same direction.
    - All components must have the same product type.
    - All components must belong to the same bidding zone.
    - All price values must be distinct.

    Usage::

        group = (
            MultipartGroup(bidding_zone=BiddingZone.DK1)
            .direction(Direction.UP)
            .resource("DK1-RES-001", coding_scheme="A01")
            .product_type(MarketProductType.SCHEDULED_ONLY)
            .for_mtu("2026-03-21T10:00Z")
            .add_component(volume_mw=20, price_eur=50.0, divisible=True,
                           min_volume_mw=5)
            .add_component(volume_mw=15, price_eur=75.0, divisible=True,
                           min_volume_mw=5)
            .add_component(volume_mw=10, price_eur=120.0, divisible=False)
            .build()
        )
    """

    def __init__(
        self,
        bidding_zone: BiddingZone | None = None,
        group_id: str | None = None,
    ) -> None:
        """Initialise the multipart group builder.

        Args:
            bidding_zone: Connecting domain (bidding zone) shared by all
                components.
            group_id: UUID for the group.  Auto-generated if omitted.
        """
        self._bidding_zone = bidding_zone
        self._group_id: str = group_id or str(uuid.uuid4())
        self._direction: Direction | None = None
        self._mtu: str | None = None
        self._product_type: MarketProductType | None = None
        self._resource_id: str | None = None
        self._resource_scheme: str | None = None
        self._components: list[dict[str, Any]] = []

    def for_mtu(self, mtu: str) -> Self:
        """Set the MTU start time shared by all components.

        Args:
            mtu: ISO 8601 string (e.g. ``"2026-03-21T10:00Z"``).

        Returns:
            This builder (for method chaining).
        """
        self._mtu = mtu
        return self

    def direction(self, direction: Direction) -> Self:
        """Set the regulation direction shared by all components.

        Args:
            direction: UP or DOWN.

        Returns:
            This builder (for method chaining).
        """
        self._direction = direction
        return self

    def product_type(self, product_type: MarketProductType) -> Self:
        """Set the market product type shared by all components.

        Args:
            product_type: One of :class:`~nexa_mfrr_eam.types.MarketProductType`.

        Returns:
            This builder (for method chaining).
        """
        self._product_type = product_type
        return self

    def resource(self, resource_id: str, coding_scheme: str = "A01") -> Self:
        """Set the registered resource identifier shared by all components.

        Args:
            resource_id: Resource identifier.
            coding_scheme: Coding scheme (``"A01"`` EIC, ``"NNO"``, etc.).

        Returns:
            This builder (for method chaining).
        """
        self._resource_id = resource_id
        self._resource_scheme = coding_scheme
        return self

    def add_component(
        self,
        volume_mw: int,
        price_eur: float | Decimal,
        divisible: bool = True,
        min_volume_mw: int | None = None,
        direction: Direction | None = None,
        mtu: str | None = None,
        bidding_zone: BiddingZone | None = None,
        resource_id: str | None = None,
        resource_coding_scheme: str | None = None,
        psr_type: ProductionType | str | None = None,
        note: str | None = None,
        mrid: str | None = None,
    ) -> Self:
        """Add a price-tier component to the multipart group.

        Args:
            volume_mw: Bid volume in MW for this price tier.
            price_eur: Bid price in EUR/MWh (must be unique within the group).
            divisible: Whether the bid is divisible.  Defaults to ``True``.
            min_volume_mw: Minimum activation volume for divisible bids.
            direction: Override the group-level direction.
            mtu: Override the group-level MTU.
            bidding_zone: Override the group-level bidding zone.
            resource_id: Override the group-level resource identifier.
            resource_coding_scheme: Override the group-level coding scheme.
            psr_type: PSR type for Denmark bids.
            note: Free-text note for Denmark bids.
            mrid: Override the auto-generated mRID.

        Returns:
            This builder (for method chaining).
        """
        psr_value = psr_type.value if isinstance(psr_type, ProductionType) else psr_type
        self._components.append(
            {
                "volume_mw": volume_mw,
                "price_eur": price_eur,
                "divisible": divisible,
                "min_volume_mw": min_volume_mw,
                "direction": direction,
                "mtu": mtu,
                "bidding_zone": bidding_zone,
                "resource_id": resource_id,
                "resource_coding_scheme": resource_coding_scheme,
                "psr_type": psr_value,
                "note": note,
                "mrid": mrid,
            }
        )
        return self

    @property
    def group_id(self) -> str:
        """The UUID identifying this multipart group."""
        return self._group_id

    def build(self) -> tuple[BidTimeSeriesModel, ...]:
        """Validate and build all component bids.

        Returns:
            A tuple of frozen :class:`~nexa_mfrr_eam.types.BidTimeSeriesModel`
            instances, all sharing the same ``multipartBidIdentification``.

        Raises:
            :class:`~nexa_mfrr_eam.exceptions.BidValidationError`: If fewer
                than two components are defined, or if the components violate
                multipart constraints (same MTU/direction/zone, distinct
                prices).
        """
        errors = _validate_multipart_constraints(
            self._components, self._direction, self._mtu
        )
        if errors:
            raise BidValidationError(errors)

        bids: list[BidTimeSeriesModel] = []
        for cfg in self._components:
            builder = _make_builder(
                cfg,
                self._direction,
                self._mtu,
                self._product_type,
                self._bidding_zone,
                self._resource_id,
                self._resource_scheme,
            )
            base = builder.build()
            bids.append(
                base.model_copy(
                    update={
                        "multipart_bid_identification": self._group_id,
                        "psr_type": cfg.get("psr_type"),
                        "note": cfg.get("note"),
                    }
                )
            )
        return tuple(bids)


# ---------------------------------------------------------------------------
# InclusiveGroup
# ---------------------------------------------------------------------------


class InclusiveGroup:
    """Builder for an inclusive bid group (all-or-nothing activation).

    All components share the same ``inclusiveBidsIdentification`` UUID.  If
    one component is activated, all components must be activated.  The TSO
    merges the group into a single bid before forwarding to the AOF.

    Supported by: Fingrid, Statnett, Svenska kraftnat.
    **Not supported by Energinet (Denmark).**

    Constraints enforced in :meth:`build`:

    - At least two components must be added.
    - All components must cover the same MTU.
    - All components must have the same direction.
    - All components must have the same product type.
    - All components must belong to the same bidding zone.
    - All components must have the same price.

    Usage::

        group = (
            InclusiveGroup(bidding_zone=BiddingZone.FI)
            .direction(Direction.UP)
            .resource("FI-RES-001", coding_scheme="A01")
            .product_type(MarketProductType.SCHEDULED_AND_DIRECT)
            .for_mtu("2026-03-21T10:00Z")
            .add_component(volume_mw=15, price_eur=65.0, divisible=True,
                           min_volume_mw=5)
            .add_component(volume_mw=20, price_eur=65.0, divisible=True,
                           min_volume_mw=5)
            .build()
        )
    """

    def __init__(
        self,
        bidding_zone: BiddingZone | None = None,
        group_id: str | None = None,
    ) -> None:
        """Initialise the inclusive group builder.

        Args:
            bidding_zone: Connecting domain (bidding zone) shared by all
                components.
            group_id: UUID for the group.  Auto-generated if omitted.
        """
        self._bidding_zone = bidding_zone
        self._group_id: str = group_id or str(uuid.uuid4())
        self._direction: Direction | None = None
        self._mtu: str | None = None
        self._product_type: MarketProductType | None = None
        self._resource_id: str | None = None
        self._resource_scheme: str | None = None
        self._components: list[dict[str, Any]] = []

    def for_mtu(self, mtu: str) -> Self:
        """Set the MTU start time shared by all components.

        Args:
            mtu: ISO 8601 string (e.g. ``"2026-03-21T10:00Z"``).

        Returns:
            This builder (for method chaining).
        """
        self._mtu = mtu
        return self

    def direction(self, direction: Direction) -> Self:
        """Set the regulation direction shared by all components.

        Args:
            direction: UP or DOWN.

        Returns:
            This builder (for method chaining).
        """
        self._direction = direction
        return self

    def product_type(self, product_type: MarketProductType) -> Self:
        """Set the market product type shared by all components.

        Args:
            product_type: One of :class:`~nexa_mfrr_eam.types.MarketProductType`.

        Returns:
            This builder (for method chaining).
        """
        self._product_type = product_type
        return self

    def resource(self, resource_id: str, coding_scheme: str = "A01") -> Self:
        """Set the registered resource identifier shared by all components.

        Args:
            resource_id: Resource identifier.
            coding_scheme: Coding scheme (``"A01"`` EIC, ``"NNO"``, etc.).

        Returns:
            This builder (for method chaining).
        """
        self._resource_id = resource_id
        self._resource_scheme = coding_scheme
        return self

    def add_component(
        self,
        volume_mw: int,
        price_eur: float | Decimal,
        divisible: bool = True,
        min_volume_mw: int | None = None,
        direction: Direction | None = None,
        mtu: str | None = None,
        bidding_zone: BiddingZone | None = None,
        resource_id: str | None = None,
        resource_coding_scheme: str | None = None,
        mrid: str | None = None,
    ) -> Self:
        """Add a component bid to the inclusive group.

        Args:
            volume_mw: Bid volume in MW.
            price_eur: Bid price in EUR/MWh (must match all other components).
            divisible: Whether the bid is divisible.  Defaults to ``True``.
            min_volume_mw: Minimum activation volume for divisible bids.
            direction: Override the group-level direction.
            mtu: Override the group-level MTU.
            bidding_zone: Override the group-level bidding zone.
            resource_id: Override the group-level resource identifier.
            resource_coding_scheme: Override the group-level coding scheme.
            mrid: Override the auto-generated mRID.

        Returns:
            This builder (for method chaining).
        """
        self._components.append(
            {
                "volume_mw": volume_mw,
                "price_eur": price_eur,
                "divisible": divisible,
                "min_volume_mw": min_volume_mw,
                "direction": direction,
                "mtu": mtu,
                "bidding_zone": bidding_zone,
                "resource_id": resource_id,
                "resource_coding_scheme": resource_coding_scheme,
                "mrid": mrid,
            }
        )
        return self

    @property
    def group_id(self) -> str:
        """The UUID identifying this inclusive group."""
        return self._group_id

    def build(self) -> tuple[BidTimeSeriesModel, ...]:
        """Validate and build all component bids.

        Returns:
            A tuple of frozen :class:`~nexa_mfrr_eam.types.BidTimeSeriesModel`
            instances, all sharing the same ``inclusiveBidsIdentification``.

        Raises:
            :class:`~nexa_mfrr_eam.exceptions.BidValidationError`: If fewer
                than two components are defined, or if the components violate
                inclusive group constraints (same MTU/direction/zone/price).
        """
        errors = _validate_inclusive_constraints(
            self._components, self._direction, self._mtu
        )
        if errors:
            raise BidValidationError(errors)

        bids: list[BidTimeSeriesModel] = []
        for cfg in self._components:
            builder = _make_builder(
                cfg,
                self._direction,
                self._mtu,
                self._product_type,
                self._bidding_zone,
                self._resource_id,
                self._resource_scheme,
            )
            base = builder.build()
            bids.append(
                base.model_copy(
                    update={"inclusive_bids_identification": self._group_id}
                )
            )
        return tuple(bids)


# ---------------------------------------------------------------------------
# Validation helpers (called by build() methods above)
# ---------------------------------------------------------------------------


def _resolve_mtu(cfg: dict[str, Any], group_mtu: str | None) -> str | None:
    return cfg.get("mtu") or group_mtu


def _resolve_zone(cfg: dict[str, Any], group_zone: BiddingZone | None) -> str | None:
    zone: BiddingZone | None = cfg.get("bidding_zone") or group_zone
    return zone.value if zone is not None else None


def _resolve_direction(
    cfg: dict[str, Any], group_direction: Direction | None
) -> str | None:
    direction: Direction | None = cfg.get("direction") or group_direction
    return direction.value if direction is not None else None


def _validate_exclusive_constraints(
    components: list[dict[str, Any]],
    group_direction: Direction | None,
    group_mtu: str | None,
) -> list[str]:
    errors: list[str] = []
    if len(components) < 2:
        errors.append("ExclusiveGroup requires at least 2 components")
    mtus = [_resolve_mtu(c, group_mtu) for c in components]
    if len(set(m for m in mtus if m is not None)) > 1:
        errors.append("ExclusiveGroup: all components must cover the same MTU")
    for i, c in enumerate(components):
        if _resolve_direction(c, group_direction) is None:
            errors.append(
                f"ExclusiveGroup: direction must be set on the group"
                f" or component {i + 1}"
            )
    return errors


def _validate_multipart_constraints(
    components: list[dict[str, Any]],
    group_direction: Direction | None,
    group_mtu: str | None,
) -> list[str]:
    errors: list[str] = []
    if len(components) < 2:
        errors.append("MultipartGroup requires at least 2 components")
    mtus = [_resolve_mtu(c, group_mtu) for c in components]
    if len(set(m for m in mtus if m is not None)) > 1:
        errors.append("MultipartGroup: all components must cover the same MTU")
    directions = [_resolve_direction(c, group_direction) for c in components]
    if len(set(d for d in directions if d is not None)) > 1:
        errors.append("MultipartGroup: all components must have the same direction")
    prices = [Decimal(str(c["price_eur"])) for c in components]
    if len(set(prices)) != len(prices):
        errors.append("MultipartGroup: all component prices must be distinct")
    return errors


def _validate_inclusive_constraints(
    components: list[dict[str, Any]],
    group_direction: Direction | None,
    group_mtu: str | None,
) -> list[str]:
    errors: list[str] = []
    if len(components) < 2:
        errors.append("InclusiveGroup requires at least 2 components")
    mtus = [_resolve_mtu(c, group_mtu) for c in components]
    if len(set(m for m in mtus if m is not None)) > 1:
        errors.append("InclusiveGroup: all components must cover the same MTU")
    directions = [_resolve_direction(c, group_direction) for c in components]
    if len(set(d for d in directions if d is not None)) > 1:
        errors.append("InclusiveGroup: all components must have the same direction")
    prices = [Decimal(str(c["price_eur"])) for c in components]
    if len(set(prices)) != 1:
        errors.append("InclusiveGroup: all components must have the same price")
    return errors
