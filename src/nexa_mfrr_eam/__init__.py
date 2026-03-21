"""nexa-mfrr-nordic-eam: Python library for Nordic mFRR EAM bid management.

This library handles the full BSP workflow for the Nordic mFRR energy
activation market: building bids, validating them, serializing to CIM XML,
and parsing TSO responses.

Quickstart::

    from nexa_mfrr_eam import MARIMode, configure, Direction, TSO

    # Set global MARI mode
    configure(mari_mode=MARIMode.PRE_MARI)

See the project README for full usage examples.
"""

from nexa_mfrr_eam.config import configure, get_mari_mode
from nexa_mfrr_eam.exceptions import (
    InvalidMTUError,
    NaiveDatetimeError,
    NexaMFRREAMError,
)
from nexa_mfrr_eam.types import (
    TSO,
    BiddingZone,
    CodingScheme,
    ConditionalStatus,
    Direction,
    MARIMode,
    MarketProductType,
    NonStandardType,
    PeriodShiftPosition,
)

__version__ = "0.1.0"

__all__ = [
    # Version
    "__version__",
    # Configuration
    "configure",
    "get_mari_mode",
    # Exceptions
    "NexaMFRREAMError",
    "InvalidMTUError",
    "NaiveDatetimeError",
    # Enums
    "MARIMode",
    "Direction",
    "MarketProductType",
    "BiddingZone",
    "TSO",
    "ConditionalStatus",
    "NonStandardType",
    "PeriodShiftPosition",
    "CodingScheme",
]
