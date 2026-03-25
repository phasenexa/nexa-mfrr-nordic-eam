"""GS tax (grunnrenteskatt) price adjustment for Norwegian mFRR bids.

Norwegian hydro generators are subject to a resource rent tax (grunnrenteskatt,
commonly abbreviated "GS tax"). The Nordic regulator requires that BSPs should
not make more money in mFRR than is possible in the day-ahead auction. The tax
is defined as a proportion of the day-ahead price, and mFRR bid prices must
account for it.

The adjusted price depends on the day-ahead price for each MTU, meaning bid
prices are not static per tier – they vary per MTU as the DA price varies.
"""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

from nexa_mfrr_eam.config import get_mari_mode
from nexa_mfrr_eam.types import Direction, MARIMode

if TYPE_CHECKING:
    from nexa_mfrr_eam.types import BidTimeSeriesModel

# ---------------------------------------------------------------------------
# Statnett price limits (slightly inside official limits to avoid boundary issues)
# ---------------------------------------------------------------------------

_PRE_MARI_PRICE_MAX: Decimal = Decimal("9999")
_PRE_MARI_PRICE_MIN: Decimal = Decimal("-9999")
_POST_MARI_PRICE_MAX: Decimal = Decimal("14999")
_POST_MARI_PRICE_MIN: Decimal = Decimal("-14999")

_TWO_PLACES = Decimal("0.01")


def _price_bounds(mari_mode: MARIMode) -> tuple[Decimal, Decimal]:
    """Return (min, max) price bounds for the given MARI mode."""
    if mari_mode is MARIMode.POST_MARI:
        return _POST_MARI_PRICE_MIN, _POST_MARI_PRICE_MAX
    return _PRE_MARI_PRICE_MIN, _PRE_MARI_PRICE_MAX


def gs_adjusted_price(
    tier_price: Decimal | float,
    da_price: Decimal | float,
    tax_rate: Decimal | float,
    direction: Direction,
    mari_mode: MARIMode | None = None,
) -> Decimal:
    """Calculate a GS-tax-adjusted bid price for a single MTU.

    Applies the formula::

        adjusted = tier_price + tax_rate * (da_price - tier_price)

    Then clamps the result:

    - Up bids: ``adjusted >= da_price``
    - Down bids: ``adjusted <= da_price``
    - Statnett limits (pre-MARI ±9,999 EUR/MWh; post-MARI ±14,999 EUR/MWh)
    - Rounds to 2 decimal places (0.01 EUR granularity)

    Args:
        tier_price: Base price the trader has set for this bid tier (EUR/MWh).
        da_price: Day-ahead price for this specific MTU (EUR/MWh).
        tax_rate: Resource rent tax rate as a decimal (e.g. ``0.59`` for 59%).
        direction: Bid direction; determines clamping rule.
        mari_mode: MARI mode for Statnett price limit selection.  Defaults to
            the global setting from :func:`~nexa_mfrr_eam.config.get_mari_mode`.

    Returns:
        GS-adjusted bid price in EUR/MWh, rounded to 2 decimal places.

    Raises:
        ValueError: If ``tax_rate`` is not between 0 and 1 (inclusive).

    Examples:
        >>> from decimal import Decimal
        >>> from nexa_mfrr_eam.types import Direction
        >>> gs_adjusted_price(185.0, 131.73, 0.59, Direction.UP)
        Decimal('153.57')
    """
    tax_rate_d = Decimal(str(tax_rate))
    if not (Decimal("0") <= tax_rate_d <= Decimal("1")):
        raise ValueError(
            f"tax_rate must be between 0 and 1 (inclusive), got {tax_rate}"
        )

    tier_d = Decimal(str(tier_price))
    da_d = Decimal(str(da_price))

    adjusted = tier_d + tax_rate_d * (da_d - tier_d)

    # Direction clamping
    adjusted = max(adjusted, da_d) if direction is Direction.UP else min(adjusted, da_d)

    # Statnett price limit clamping
    active_mode = mari_mode if mari_mode is not None else get_mari_mode()
    price_min, price_max = _price_bounds(active_mode)
    adjusted = max(price_min, min(price_max, adjusted))

    return adjusted.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def gs_adjust_bids(
    bids: list[BidTimeSeriesModel],
    da_prices: dict[datetime, Decimal | float],
    tax_rate: Decimal | float,
    mari_mode: MARIMode | None = None,
) -> list[BidTimeSeriesModel]:
    """Apply GS tax price adjustment to a list of bids.

    Returns new :class:`~nexa_mfrr_eam.types.BidTimeSeriesModel` instances
    with adjusted prices.  The original bids are not mutated.

    Each bid's MTU start time is looked up in *da_prices* to retrieve the
    day-ahead price for that period.  The direction is read from the bid's
    ``flow_direction`` field.

    Args:
        bids: List of built bids to adjust.
        da_prices: Mapping from MTU start :class:`~datetime.datetime` to
            day-ahead price (EUR/MWh).  Keys must be timezone-aware UTC
            datetimes matching the bids' ``period.time_interval_start``.
        tax_rate: Resource rent tax rate as a decimal (e.g. ``0.59`` for 59%).
        mari_mode: MARI mode for Statnett price limit selection.  Defaults to
            the global setting from :func:`~nexa_mfrr_eam.config.get_mari_mode`.

    Returns:
        New list of bids with GS-adjusted prices.

    Raises:
        ValueError: If ``tax_rate`` is not between 0 and 1 (inclusive).
        KeyError: If a bid's MTU start is not found in *da_prices*.

    Examples:
        >>> from datetime import datetime, timezone
        >>> from decimal import Decimal
        >>> adjusted = gs_adjust_bids(my_bids, da_prices, tax_rate=Decimal("0.59"))
    """
    # Validate tax_rate early so we get a clear error before any bids are processed
    tax_rate_d = Decimal(str(tax_rate))
    if not (Decimal("0") <= tax_rate_d <= Decimal("1")):
        raise ValueError(
            f"tax_rate must be between 0 and 1 (inclusive), got {tax_rate}"
        )

    # Normalise da_prices keys to Decimal values
    normalised: dict[datetime, Decimal] = {
        k: Decimal(str(v)) for k, v in da_prices.items()
    }

    result: list[BidTimeSeriesModel] = []
    for bid in bids:
        mtu_start = bid.period.time_interval_start
        if mtu_start not in normalised:
            raise KeyError(
                f"No DA price found for MTU {mtu_start.isoformat()} "
                f"(bid mRID {bid.mrid})"
            )

        da_price = normalised[mtu_start]
        direction = Direction(bid.flow_direction)
        tier_price = bid.period.point.energy_price

        if tier_price is None:
            # Period-shift-only bids (Z01) have no price; skip adjustment
            result.append(bid)
            continue

        new_price = gs_adjusted_price(
            tier_price=tier_price,
            da_price=da_price,
            tax_rate=tax_rate_d,
            direction=direction,
            mari_mode=mari_mode,
        )

        new_point = bid.period.point.model_copy(update={"energy_price": new_price})
        new_period = bid.period.model_copy(update={"point": new_point})
        result.append(bid.model_copy(update={"period": new_period}))

    return result
