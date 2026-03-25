"""Fingrid (Finland) TSO configuration.

Fingrid is the Finnish TSO participating in the mFRR EAM.

Key Fingrid specifics:

- Receiver EIC: ``10X1001A1001A264``
- Control area EIC: ``10YFI-1--------U``
- Minimum bid: 1 MW (common minimum)
- Resource coding scheme: A01 (EIC)
- Max 2000 bids per message (stricter than the common 4000 limit)
- Supports inclusive bids (used for aggregated bids; same proportion selected)
- Conditional linking allowed for inclusive bids (special rules)
- Voluntary secondary bid ID via Reason element (code A95, text max 100 chars)
- Can change product type between A05 and A07
- BEGOT is 30 days
"""

from __future__ import annotations

from nexa_mfrr_eam.tso.base import TSOConfig

FINGRID_CONFIG: TSOConfig = TSOConfig(
    receiver_mrid="10X1001A1001A264",
    domain_mrid="10YFI-1--------U",
    min_bid_mw=1,
    max_bids_per_message=2000,
    supports_inclusive_bids=True,
    supports_period_shift=False,
    resource_coding_scheme="A01",
    requires_psr_type=False,
)
"""Singleton TSOConfig for Fingrid (Finland)."""
