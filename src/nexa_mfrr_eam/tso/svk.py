"""Svenska kraftnat (Sweden) TSO configuration.

Svenska kraftnat (SVK) is the Swedish TSO participating in the mFRR EAM.

Key SVK specifics:

- Receiver EIC: ``10X1001A1001A418``
- Control area EIC: ``10YSE-1--------K``
- Minimum bid: 1 MW (common minimum)
- Resource coding scheme: NSE (Swedish national identifiers)
- Cut-off: 6 minutes (messages older than 6 min are silently dropped)
- Non-standard bids (A02): overbelastningshantering (overload handling), reason
  code Z74, indivisible, technically linked, activation time required
- Sender/resource coding scheme: NSE (Swedish national) or A01 (EIC)
"""

from __future__ import annotations

from nexa_mfrr_eam.tso.base import TSOConfig

SVK_CONFIG: TSOConfig = TSOConfig(
    receiver_mrid="10X1001A1001A418",
    domain_mrid="10YSE-1--------K",
    min_bid_mw=1,
    max_bids_per_message=4000,
    supports_inclusive_bids=False,
    supports_period_shift=False,
    resource_coding_scheme="NSE",
)
"""Singleton TSOConfig for Svenska kraftnat (Sweden)."""
