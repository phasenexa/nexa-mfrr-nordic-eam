"""nexa-mfrr-nordic-eam: Python library for Nordic mFRR EAM bid management.

This library covers bid building, validation, CIM XML serialization and
deserialization of ReserveBid_MarketDocument, and parsing of
Acknowledgement_MarketDocument responses.

Quickstart::

    from nexa_mfrr_eam import Bid, BidDocument, MARIMode, TSO

    bid = (
        Bid.up(volume_mw=50, price_eur=85.50)
        .divisible(min_volume_mw=10)
        .for_mtu("2026-03-21T10:00Z")
        .resource("NOKG90901", coding_scheme="NNO")
        .product_type(MarketProductType.SCHEDULED_AND_DIRECT)
        .build()
    )

    doc = (
        BidDocument(tso=TSO.STATNETT)
        .sender(party_id="9999909919920", coding_scheme="A10")
        .add_bid(bid)
        .build()
    )
    xml_bytes = doc.to_xml()

See the project README for full usage examples.
"""

from nexa_mfrr_eam.bids.complex import ExclusiveGroup, InclusiveGroup, MultipartGroup
from nexa_mfrr_eam.bids.linked import TechnicalLink
from nexa_mfrr_eam.bids.simple import Bid
from nexa_mfrr_eam.config import configure, get_mari_mode
from nexa_mfrr_eam.documents.reserve_bid import BidDocument, BuiltBidDocument
from nexa_mfrr_eam.exceptions import (
    BidValidationError,
    InvalidMTUError,
    NaiveDatetimeError,
    NexaMFRREAMError,
)
from nexa_mfrr_eam.types import (
    TSO,
    BiddingZone,
    BidDocumentModel,
    CodingScheme,
    ConditionalStatus,
    Direction,
    MARIMode,
    MarketProductType,
    NonStandardType,
    PeriodShiftPosition,
    ProductionType,
)
from nexa_mfrr_eam.xml.deserialize import deserialize_reserve_bid_document
from nexa_mfrr_eam.xml.namespaces import SchemaVersion

__version__ = "0.3.0b1"

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
    "BidValidationError",
    # Bid builders
    "Bid",
    "TechnicalLink",
    "ExclusiveGroup",
    "MultipartGroup",
    "InclusiveGroup",
    # Document builders / parsers
    "BidDocument",
    "BuiltBidDocument",
    "deserialize_reserve_bid_document",
    "SchemaVersion",
    # Internal models (needed for type annotations on parsed results)
    "BidDocumentModel",
    # Enums
    "MARIMode",
    "Direction",
    "MarketProductType",
    "BiddingZone",
    "TSO",
    "ConditionalStatus",
    "NonStandardType",
    "PeriodShiftPosition",
    "ProductionType",
    "CodingScheme",
]
