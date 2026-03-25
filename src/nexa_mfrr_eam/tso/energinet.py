"""Energinet (Denmark) TSO configuration.

Energinet is the Danish TSO participating in the mFRR EAM.  Denmark uses a
BRP-as-BSP model (the BRP submits bids on behalf of BSPs) and a local direct
activation model where the DA bid and its linked next-quarter bid are two
separate simple bids.

Key Energinet specifics:

- Receiver EIC: ``10X1001A1001A248``
- Control area EIC: ``10Y1001A1001A796``
- Minimum bid: 1 MW (common minimum)
- Resource coding scheme: A01 (EIC)
- BRP acts as BSP; always use market role A46 (BSP) in documents
- ``mktPSRType.psrType`` is mandatory (DK-specific schema extension)
- ``Note`` element is optional (DK-specific schema extension)
- Cannot change market product type on update; must cancel and resubmit
- Local DA model: DA bid + linked bid in next QH are separate, may have
  different price/volume
- Conditional bid types A71 and A72 are not supported
"""

from __future__ import annotations

from nexa_mfrr_eam.tso.base import TSOConfig

ENERGINET_CONFIG: TSOConfig = TSOConfig(
    receiver_mrid="10X1001A1001A248",
    domain_mrid="10Y1001A1001A796",
    min_bid_mw=1,
    max_bids_per_message=4000,
    supports_inclusive_bids=False,
    supports_period_shift=False,
    resource_coding_scheme="A01",
    requires_psr_type=True,
)
"""Singleton TSOConfig for Energinet (Denmark)."""
