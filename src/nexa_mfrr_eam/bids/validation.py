"""Validation rules for bids and bid documents.

Common rules apply to all TSOs.  TSO-specific rules are layered on top via
the :class:`~nexa_mfrr_eam.tso.base.TSOConfig` strategy object.
"""

from __future__ import annotations

from decimal import Decimal

from nexa_mfrr_eam.types import BidDocumentModel, BidTimeSeriesModel, MARIMode

# ---------------------------------------------------------------------------
# Price limit constants
# ---------------------------------------------------------------------------

_PRE_MARI_MAX_PRICE: Decimal = Decimal("10000")
_POST_MARI_MAX_PRICE: Decimal = Decimal("15000")


def _price_limit(mari_mode: MARIMode) -> Decimal:
    """Return the absolute maximum price for the given MARI mode.

    Args:
        mari_mode: The active MARI mode.

    Returns:
        Maximum absolute price in EUR/MWh.
    """
    if mari_mode is MARIMode.POST_MARI:
        return _POST_MARI_MAX_PRICE
    return _PRE_MARI_MAX_PRICE


# ---------------------------------------------------------------------------
# Per-time-series validation
# ---------------------------------------------------------------------------


def validate_bid_time_series(
    ts: BidTimeSeriesModel,
    mari_mode: MARIMode,
    min_bid_mw: int = 1,
    max_bids_per_message: int = 4000,
    requires_psr_type: bool = False,
) -> list[str]:
    """Validate a single BidTimeSeries against common rules.

    Args:
        ts: The bid time series to validate.
        mari_mode: Active MARI mode (affects price limits).
        min_bid_mw: Minimum bid volume for the TSO (default 1 MW).
        max_bids_per_message: Not used here; checked at document level.
        requires_psr_type: When ``True``, the bid must have a ``psr_type``
            set (Energinet / Denmark requirement).

    Returns:
        A (possibly empty) list of human-readable error strings.
    """
    errors: list[str] = []
    limit = _price_limit(mari_mode)

    # Volume checks
    qty = ts.period.point.quantity
    if qty < 1:
        errors.append(
            f"Bid mRID {ts.mrid}: quantity {qty} MW is below absolute minimum of 1 MW"
        )
    if qty < min_bid_mw:
        errors.append(
            f"Bid mRID {ts.mrid}: quantity {qty} MW is below "
            f"TSO minimum of {min_bid_mw} MW"
        )
    if qty > 9999:
        errors.append(
            f"Bid mRID {ts.mrid}: quantity {qty} MW exceeds maximum of 9999 MW"
        )

    # Minimum quantity must be ≤ quantity for divisible bids
    min_qty = ts.period.point.minimum_quantity
    if ts.divisible_code == "A01" and min_qty is None:
        errors.append(f"Bid mRID {ts.mrid}: divisible bid must have a minimum_quantity")
    if min_qty is not None and min_qty > qty:
        errors.append(
            f"Bid mRID {ts.mrid}: minimum_quantity {min_qty} exceeds quantity {qty}"
        )

    # Price checks
    price = ts.period.point.energy_price
    if price is not None:
        if price < -limit:
            errors.append(
                f"Bid mRID {ts.mrid}: price {price} EUR/MWh is below minimum "
                f"{-limit} for {mari_mode.value}"
            )
        if price > limit:
            errors.append(
                f"Bid mRID {ts.mrid}: price {price} EUR/MWh exceeds maximum "
                f"{limit} for {mari_mode.value}"
            )

    # Period-shift-only bids must not have a price
    if (
        ts.standard_market_product_type == "Z01"
        and ts.period.point.energy_price is not None
    ):
        errors.append(
            f"Bid mRID {ts.mrid}: period-shift-only bid (Z01) must not have a price"
        )

    # Energinet / Denmark: psr_type is mandatory
    if requires_psr_type and ts.psr_type is None:
        errors.append(
            f"Bid mRID {ts.mrid}: mktPSRType.psrType is required for Energinet bids "
            f"(use ProductionType.SOLAR, WIND_OFFSHORE, WIND_ONSHORE, or OTHER)"
        )

    # mRID length (XSD ID_String max 60)
    if len(ts.mrid) > 60:
        errors.append(
            f"Bid mRID {ts.mrid}: mRID length {len(ts.mrid)} exceeds maximum of 60"
        )

    return errors


# ---------------------------------------------------------------------------
# Document-level validation
# ---------------------------------------------------------------------------


def validate_document(
    doc: BidDocumentModel,
    mari_mode: MARIMode,
    min_bid_mw: int = 1,
    max_bids_per_message: int = 4000,
    requires_psr_type: bool = False,
) -> list[str]:
    """Validate a BidDocumentModel against common and TSO-supplied rules.

    Args:
        doc: The document to validate.
        mari_mode: Active MARI mode.
        min_bid_mw: TSO minimum bid volume in MW.
        max_bids_per_message: Maximum number of BidTimeSeries per message.
        requires_psr_type: When ``True``, every bid must carry a
            ``psr_type`` value (Energinet / Denmark requirement).

    Returns:
        A (possibly empty) list of human-readable error strings.
    """
    errors: list[str] = []

    if not doc.bid_time_series:
        errors.append("Document contains no BidTimeSeries")

    if len(doc.bid_time_series) > max_bids_per_message:
        errors.append(
            f"Document contains {len(doc.bid_time_series)} BidTimeSeries "
            f"which exceeds the TSO limit of {max_bids_per_message}"
        )

    for ts in doc.bid_time_series:
        errors.extend(
            validate_bid_time_series(
                ts,
                mari_mode,
                min_bid_mw=min_bid_mw,
                requires_psr_type=requires_psr_type,
            )
        )

    return errors
