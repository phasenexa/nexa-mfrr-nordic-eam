"""Statnett (Norway) TSO configuration.

Statnett is the Norwegian TSO participating in the mFRR EAM with the richest
feature set including period shift, faster activation, mFRR-D, inclusive bids,
and heartbeat.

Key Statnett specifics:
- Receiver EIC: ``10X1001A1001A38Y``
- Control area EIC: ``10YNO-0--------C``
- Minimum bid: 10 MW (with a 5–9 MW exception for one bid per resource/direction/MTU)
- Resource coding scheme: NNO (NOKG/NOG national codes)
- Cut-off: 15 minutes (messages older than 15 min are silently dropped)
- Heartbeat: required at T-12, T-7.5, T-3
"""

from __future__ import annotations

from nexa_mfrr_eam.tso.base import TSOConfig

STATNETT_CONFIG: TSOConfig = TSOConfig(
    receiver_mrid="10X1001A1001A38Y",
    domain_mrid="10YNO-0--------C",
    min_bid_mw=10,
    max_bids_per_message=4000,
    supports_heartbeat=True,
    supports_inclusive_bids=True,
    supports_period_shift=True,
    resource_coding_scheme="NNO",
)
"""Singleton TSOConfig for Statnett (Norway)."""
