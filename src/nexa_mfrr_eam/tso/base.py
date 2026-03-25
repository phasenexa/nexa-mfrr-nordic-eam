"""Base TSO configuration dataclass.

Each TSO module instantiates a :class:`TSOConfig` singleton that the
validation and serialization layers consume.  The strategy pattern means
there are no if/else chains on TSO name in the core logic.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TSOConfig:
    """Immutable configuration for a single TSO.

    Attributes:
        receiver_mrid: EIC code of the TSO, used as the document receiver.
        domain_mrid: Control area EIC code for the TSO's ``domain.mRID``.
        min_bid_mw: Minimum bid volume accepted by this TSO in MW.
        max_bids_per_message: Maximum number of BidTimeSeries per document.
        supports_inclusive_bids: Whether inclusive groups are supported.
        supports_period_shift: Whether Statnett period-shift bids are supported.
        resource_coding_scheme: Default coding scheme for resource identifiers.
    """

    receiver_mrid: str
    """EIC code for the TSO receiver (used in document header)."""

    domain_mrid: str
    """Control area EIC code (used in ``domain.mRID``)."""

    min_bid_mw: int = 1
    """Minimum bid volume in MW accepted by this TSO."""

    max_bids_per_message: int = 4000
    """Maximum BidTimeSeries elements per ReserveBid_MarketDocument."""

    supports_inclusive_bids: bool = False
    """Whether inclusive bid groups are supported."""

    supports_period_shift: bool = False
    """Whether Statnett-style period-shift bids are supported."""

    resource_coding_scheme: str = "A01"
    """Default coding scheme for ``registeredResource.mRID``."""

    requires_psr_type: bool = False
    """Whether ``mktPSRType.psrType`` is mandatory (Energinet/DK only)."""
