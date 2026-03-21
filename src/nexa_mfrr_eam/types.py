"""Enums and type definitions for the nexa-mfrr-nordic-eam library.

This module contains all domain enumerations used throughout the library.
Pydantic models for bid and document structures will be added in future milestones.
"""

import enum


class MARIMode(enum.Enum):
    """MARI mode toggle affecting timing, price limits, and validation rules.

    The mFRR EAM will transition to the European MARI platform at a later date.
    Toggle between pre-MARI and post-MARI behaviour using this enum.
    """

    PRE_MARI = "pre_mari"
    POST_MARI = "post_mari"


class Direction(enum.Enum):
    """Bid direction (regulation direction).

    CIM code values per IEC 62325-451-7.
    """

    UP = "A01"  # Up-regulation (increase production / decrease consumption)
    DOWN = "A02"  # Down-regulation (decrease production / increase consumption)


class MarketProductType(enum.Enum):
    """Market product type for a bid time series.

    CIM code values per IEC 62325-451-7 and NBM implementation guide.
    """

    SCHEDULED_ONLY = "A05"  # Scheduled activation only
    SCHEDULED_AND_DIRECT = "A07"  # Scheduled + direct activation
    NON_STANDARD = "A02"  # Non-standard product (mFRR-D, other)
    PERIOD_SHIFT_ONLY = "Z01"  # Period-shift-only (Statnett national)


class BiddingZone(enum.Enum):
    """Nordic bidding zones with their EIC codes.

    EIC codes sourced from the ENTSO-E EIC registry and NBM implementation guide.
    """

    # Norway
    NO1 = "10YNO-1--------2"
    NO2 = "10YNO-2--------T"
    NO3 = "10YNO-3--------J"
    NO4 = "10YNO-4--------9"
    NO5 = "10Y1001A1001A48H"

    # Sweden
    SE1 = "10Y1001A1001A44P"
    SE2 = "10Y1001A1001A45N"
    SE3 = "10Y1001A1001A46L"
    SE4 = "10Y1001A1001A47J"

    # Denmark
    DK1 = "10YDK-1--------W"
    DK2 = "10YDK-2--------M"

    # Finland
    FI = "10YFI-1--------U"


class TSO(enum.Enum):
    """Nordic Transmission System Operators participating in mFRR EAM."""

    STATNETT = "statnett"  # Norway
    FINGRID = "fingrid"  # Finland
    ENERGINET = "energinet"  # Denmark
    SVK = "svk"  # Svenska kraftnat (Sweden)


class ConditionalStatus(enum.Enum):
    """Condition codes for conditional bid links.

    Used in the ``Linked_BidTimeSeries`` element to define how a bid's
    availability depends on the activation outcome of a linked bid.
    """

    NOT_AVAILABLE_IF_ACTIVATED = "A55"  # Bid unavailable if linked bid was activated
    AVAILABLE_IF_ACTIVATED = "A56"  # Bid available only if linked bid was activated
    # A71 and A72 are referenced in CLAUDE.md as unsupported by Energinet;
    # their precise semantics require the full implementation guide.
    # TODO: add A71, A72 when implementation guide section is available.


class NonStandardType(enum.Enum):
    """Non-standard bid type reason codes (national extensions).

    Used in the ``Reason`` element of non-standard bids.
    """

    DISTURBANCE_RESERVE = "Z74"  # mFRR-D (Statnett) / Overbelastning (SVK)
    OTHER = "Z83"  # Other non-standard (Statnett)


class PeriodShiftPosition(enum.Enum):
    """Period shift position codes for Statnett period-shift bids.

    Used in the ``Reason`` element of period-shift bids.
    """

    BEGINNING_OF_PERIOD = "Z64"  # Bid covers start of the period
    END_OF_PERIOD = "Z65"  # Bid covers end of the period


class CodingScheme(enum.Enum):
    """Coding scheme identifiers for party, area, and resource mRID attributes.

    These appear as ``codingScheme`` attributes on ``AreaID_String``,
    ``PartyID_String``, and ``ResourceID_String`` elements in the XML.
    """

    EIC = "A01"  # ENTSO-E Energy Identification Code
    GS1 = "A10"  # GS1 Global Location Number
    NNO = "NNO"  # Norwegian national (NOKG/NOG codes, Statnett)
    NSE = "NSE"  # Swedish national (Svenska kraftnat)
