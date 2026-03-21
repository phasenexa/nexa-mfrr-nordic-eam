"""MTU boundary calculations, gate closure times, and timing helpers.

This module provides pure functions for working with 15-minute Market Time
Units (MTUs), gate closure calculations for pre-MARI and post-MARI modes,
and conditional availability evaluation.

All datetime inputs and outputs are UTC-aware. Naive datetimes are rejected
with :class:`~nexa_mfrr_eam.exceptions.NaiveDatetimeError`.

Example::

    from datetime import datetime, timezone
    from nexa_mfrr_eam.timing import gate_closure, current_mtu, mtu_range, MARIMode

    mtu_start = datetime(2026, 3, 21, 10, 0, tzinfo=timezone.utc)
    gc = gate_closure(mtu_start, mari_mode=MARIMode.PRE_MARI)
    print(gc.bsp_gct)   # 2026-03-21 09:15:00+00:00
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from nexa_mfrr_eam.exceptions import InvalidMTUError, NaiveDatetimeError
from nexa_mfrr_eam.types import MARIMode as MARIMode  # re-exported for convenience

_UTC = datetime.UTC

# Timing offsets subtracted from mtu_start to calculate each gate closure time.
# Values are (minutes, seconds) tuples.
_PRE_MARI_OFFSETS: dict[str, datetime.timedelta] = {
    "bsp_gct": datetime.timedelta(minutes=45),
    "tso_gct": datetime.timedelta(minutes=15),
    "aof_run": datetime.timedelta(minutes=14),
    "activation": datetime.timedelta(minutes=7, seconds=30),
}

_POST_MARI_OFFSETS: dict[str, datetime.timedelta] = {
    "bsp_gct": datetime.timedelta(minutes=25),
    "tso_gct": datetime.timedelta(minutes=12),
    "aof_run": datetime.timedelta(minutes=10),
    "activation": datetime.timedelta(minutes=7, seconds=30),
}


@dataclass(frozen=True)
class MTU:
    """A single 15-minute Market Time Unit.

    Attributes:
        start: UTC-aware start time of the MTU (on a 15-minute boundary).
        end: UTC-aware end time of the MTU (start + 15 minutes).
    """

    start: datetime.datetime
    end: datetime.datetime


@dataclass(frozen=True)
class GateClosure:
    """Gate closure times for a single MTU.

    All times are UTC-aware. Computed from the MTU start time and the
    applicable MARI mode timing offsets.

    Attributes:
        mtu_start: The MTU start time this closure applies to.
        bsp_gct: BSP Gate Closure Time (BEGCT). Bids must be submitted before this.
        tso_gct: TSO Gate Closure Time.
        aof_run: Time the Activation Optimisation Function runs.
        activation: Time activation orders are sent to BSPs (QH-7.5).
        mari_mode: The MARI mode used to compute these times.
    """

    mtu_start: datetime.datetime
    bsp_gct: datetime.datetime
    tso_gct: datetime.datetime
    aof_run: datetime.datetime
    activation: datetime.datetime
    mari_mode: MARIMode

    def is_gate_open(self, now: datetime.datetime | None = None) -> bool:
        """Return True if the gate is currently open (before BSP GCT).

        Args:
            now: The current time. Defaults to ``datetime.now(UTC)``.
                Must be timezone-aware if provided.

        Returns:
            True if ``now < bsp_gct``.

        Raises:
            NaiveDatetimeError: If ``now`` is provided without timezone info.
        """
        if now is None:
            now = datetime.datetime.now(_UTC)
        if now.tzinfo is None:
            raise NaiveDatetimeError(
                "The 'now' argument must be timezone-aware. "
                "Use datetime.now(timezone.utc) or attach a tzinfo."
            )
        return now < self.bsp_gct


def gate_closure(
    mtu_start: datetime.datetime,
    mari_mode: MARIMode = MARIMode.PRE_MARI,
) -> GateClosure:
    """Compute all gate closure times for a given MTU start time.

    Args:
        mtu_start: The start of the MTU. Must be timezone-aware and fall on
            a 15-minute boundary (minutes 0, 15, 30, or 45).
        mari_mode: The MARI mode determining timing offsets. Defaults to
            :attr:`MARIMode.PRE_MARI`.

    Returns:
        A frozen :class:`GateClosure` with BSP GCT, TSO GCT, AOF run, and
        activation times.

    Raises:
        NaiveDatetimeError: If ``mtu_start`` has no timezone information.
        InvalidMTUError: If ``mtu_start`` does not fall on a 15-minute boundary.

    Example::

        >>> from datetime import datetime, timezone
        >>> from nexa_mfrr_eam.timing import gate_closure, MARIMode
        >>> mtu = datetime(2026, 3, 21, 10, 0, tzinfo=timezone.utc)
        >>> gc = gate_closure(mtu, MARIMode.PRE_MARI)
        >>> gc.bsp_gct
        datetime.datetime(2026, 3, 21, 9, 15, tzinfo=datetime.timezone.utc)
    """
    if mtu_start.tzinfo is None:
        raise NaiveDatetimeError(
            f"mtu_start must be timezone-aware, got naive datetime: {mtu_start!r}. "
            "Use datetime.timezone.utc or zoneinfo.ZoneInfo."
        )

    # Normalise to UTC
    utc_start = mtu_start.astimezone(_UTC)

    # Validate 15-minute boundary
    on_boundary = (
        utc_start.minute in (0, 15, 30, 45)
        and utc_start.second == 0
        and utc_start.microsecond == 0
    )
    if not on_boundary:
        raise InvalidMTUError(
            f"mtu_start must be on a 15-minute boundary (minutes 0, 15, 30, 45) "
            f"with zero seconds and microseconds, got: {mtu_start!r}"
        )

    offsets = (
        _PRE_MARI_OFFSETS if mari_mode is MARIMode.PRE_MARI else _POST_MARI_OFFSETS
    )

    return GateClosure(
        mtu_start=utc_start,
        bsp_gct=utc_start - offsets["bsp_gct"],
        tso_gct=utc_start - offsets["tso_gct"],
        aof_run=utc_start - offsets["aof_run"],
        activation=utc_start - offsets["activation"],
        mari_mode=mari_mode,
    )


def current_mtu(now: datetime.datetime | None = None) -> MTU:
    """Return the MTU that contains the given time.

    Args:
        now: The reference time. Defaults to ``datetime.now(UTC)``.
            Must be timezone-aware if provided.

    Returns:
        The :class:`MTU` containing ``now``.

    Raises:
        NaiveDatetimeError: If ``now`` is provided without timezone info.

    Example::

        >>> from datetime import datetime, timezone
        >>> from nexa_mfrr_eam.timing import current_mtu
        >>> t = datetime(2026, 3, 21, 10, 7, 30, tzinfo=timezone.utc)
        >>> mtu = current_mtu(t)
        >>> mtu.start
        datetime.datetime(2026, 3, 21, 10, 0, tzinfo=datetime.timezone.utc)
    """
    if now is None:
        now = datetime.datetime.now(_UTC)
    if now.tzinfo is None:
        raise NaiveDatetimeError(
            "now must be timezone-aware. Use datetime.now(timezone.utc)."
        )

    utc_now = now.astimezone(_UTC)
    start = utc_now.replace(
        minute=(utc_now.minute // 15) * 15,
        second=0,
        microsecond=0,
    )
    end = start + datetime.timedelta(minutes=15)
    return MTU(start=start, end=end)


def mtu_range(
    start: datetime.datetime | str,
    end: datetime.datetime | str,
    tz: str | None = None,  # accepted for API clarity; UTC arithmetic handles DST
) -> list[MTU]:
    """Return all MTUs in the half-open interval [start, end).

    The ``tz`` parameter is accepted for API clarity but UTC arithmetic
    naturally handles DST transitions:

    - CET spring-forward day: 23 UTC hours → 92 MTUs
    - CET fall-back day: 25 UTC hours → 100 MTUs

    Args:
        start: Start of the range (inclusive). String inputs are parsed via
            ``datetime.fromisoformat``; Python 3.11+ accepts the ``Z`` suffix.
        end: End of the range (exclusive). Same parsing rules as ``start``.
        tz: Optional timezone name (e.g. ``"CET"``). Accepted but unused;
            UTC arithmetic already handles DST-aware day lengths correctly.

    Returns:
        List of :class:`MTU` objects covering the range.

    Raises:
        ValueError: If ``start >= end``.
        NaiveDatetimeError: If parsed datetimes have no timezone information.

    Example::

        >>> from nexa_mfrr_eam.timing import mtu_range
        >>> mtus = mtu_range("2026-03-21T00:00Z", "2026-03-22T00:00Z")
        >>> len(mtus)
        96
    """
    if isinstance(start, str):
        start = datetime.datetime.fromisoformat(start)
    if isinstance(end, str):
        end = datetime.datetime.fromisoformat(end)

    if start.tzinfo is None:
        raise NaiveDatetimeError(f"start must be timezone-aware, got: {start!r}")
    if end.tzinfo is None:
        raise NaiveDatetimeError(f"end must be timezone-aware, got: {end!r}")

    start_utc = start.astimezone(_UTC)
    end_utc = end.astimezone(_UTC)

    if start_utc >= end_utc:
        raise ValueError(
            f"start must be strictly before end, "
            f"got start={start_utc!r}, end={end_utc!r}"
        )

    # Snap start to the nearest 15-minute boundary at or after start_utc
    minute_offset = start_utc.minute % 15
    if minute_offset != 0 or start_utc.second != 0 or start_utc.microsecond != 0:
        # Round up to next boundary
        snapped = start_utc.replace(second=0, microsecond=0)
        snapped = snapped.replace(minute=(start_utc.minute // 15) * 15)
        snapped += datetime.timedelta(minutes=15)
    else:
        snapped = start_utc.replace(second=0, microsecond=0)

    result: list[MTU] = []
    current = snapped
    # Also include the original start if it was already on a boundary
    if minute_offset == 0 and start_utc.second == 0 and start_utc.microsecond == 0:
        current = start_utc

    while current < end_utc:
        result.append(MTU(start=current, end=current + datetime.timedelta(minutes=15)))
        current += datetime.timedelta(minutes=15)

    return result


def evaluate_conditional_availability(
    bid_status: str,
    links: list[dict[str, object]],
) -> bool:
    """Evaluate whether a conditionally-available bid is available.

    Processes the list of conditional links and returns whether the bid
    should be considered available based on the activation outcomes of
    linked bids.

    Args:
        bid_status: The bid's status code. Only ``"A65"`` (conditionally
            available) triggers link evaluation; all other values return True.
        links: List of link dicts, each with:
            - ``"condition"`` (str): ``"A55"`` or ``"A56"``
            - ``"linked_bid_activated"`` (bool): whether the linked bid fired

    Returns:
        True if the bid is available, False if any link blocks it.

    Example::

        >>> evaluate_conditional_availability(
        ...     bid_status="A65",
        ...     links=[{"condition": "A55", "linked_bid_activated": True}],
        ... )
        False
    """
    if bid_status != "A65":
        return True  # Not a conditional bid; always available

    for link in links:
        condition = str(link.get("condition", ""))
        activated = bool(link.get("linked_bid_activated", False))

        if condition == "A55" and activated:
            # NOT_AVAILABLE_IF_ACTIVATED: block if linked bid was activated
            return False
        elif condition == "A56" and not activated:
            # AVAILABLE_IF_ACTIVATED: block if linked bid was NOT activated
            return False
        # Unknown conditions are silently ignored (forward-compatible)
        # TODO: implement A71 (not available if partially activated) and
        #       A72 (available if partially activated) when implementation
        #       guide section is available. Energinet does not support A71/A72.

    return True
