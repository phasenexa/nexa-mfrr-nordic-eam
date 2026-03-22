"""Enums and type definitions for the nexa-mfrr-nordic-eam library.

This module contains all domain enumerations and Pydantic data models used
throughout the library.  The enums are imported by everything; the models are
the internal canonical representation of bids and documents.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


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


# ---------------------------------------------------------------------------
# Pydantic models – internal canonical representation
# ---------------------------------------------------------------------------


class PointModel(BaseModel):
    """A single Point within a Period (one price-quantity pair).

    Corresponds to the ``Point`` element in ``BidTimeSeries/Period``.
    """

    model_config = ConfigDict(frozen=True)

    position: int = 1
    """Sequence position within the Period (always 1 for simple bids)."""

    quantity: Decimal
    """Bid volume in MW."""

    minimum_quantity: Decimal | None = None
    """Minimum activatable volume in MW (divisible bids only)."""

    energy_price: Decimal | None = None
    """Bid price in EUR/MWh (absent for period-shift-only bids)."""


class PeriodModel(BaseModel):
    """A single Period covering one MTU (15 minutes).

    Corresponds to the ``Period`` element in ``BidTimeSeries``.
    """

    model_config = ConfigDict(frozen=True)

    time_interval_start: datetime
    """Start of the MTU (UTC, on a 15-minute boundary)."""

    time_interval_end: datetime
    """End of the MTU (start + 15 minutes)."""

    resolution: str = "PT15M"
    """ISO 8601 duration; always PT15M for mFRR EAM."""

    point: PointModel
    """The single price/quantity Point for this period."""


class ReasonModel(BaseModel):
    """A reason code with optional free-text description.

    Corresponds to the ``Reason`` element in ``BidTimeSeries``.
    """

    model_config = ConfigDict(frozen=True)

    code: str
    """CIM reason code (e.g. ``A95`` for voluntary Fingrid bid ID)."""

    text: str | None = None
    """Optional free-text description (max 512 chars per XSD)."""


class BidTimeSeriesModel(BaseModel):
    """Internal model for a single ``Bid_TimeSeries`` element.

    Constructed by the bid builders and consumed by the XML serializer.
    """

    model_config = ConfigDict(frozen=True)

    mrid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    """Unique identifier for this bid time series (UUID v4)."""

    auction_mrid: str = "MFRR_ENERGY_ACTIVATION_MARKET"
    """Auction market identifier."""

    business_type: str = "B74"
    """CIM business type: B74 = mFRR energy activation."""

    acquiring_domain_mrid: str = "10Y1001A1001A91G"
    """Nordic Market Area EIC code."""

    connecting_domain_mrid: str | None = None
    """Bidding zone EIC code (e.g. NO2)."""

    quantity_measure_unit_name: str = "MAW"
    """Unit of measure for quantity: MAW = megawatts."""

    currency_unit_name: str = "EUR"
    """Currency for price values."""

    divisible_code: str
    """A01 = divisible, A02 = indivisible."""

    status_value: str = "A06"
    """Nested status value: A06 = available."""

    registered_resource_mrid: str | None = None
    """Resource object identifier (e.g. NOKG90901 for Statnett NNO codes)."""

    registered_resource_coding_scheme: str | None = None
    """Coding scheme for the registered resource (A01, NNO, NSE, etc.)."""

    flow_direction: str
    """A01 = up-regulation, A02 = down-regulation."""

    energy_price_measure_unit_name: str = "MWH"
    """Unit of measure for energy price: MWH = megawatt-hours."""

    activation_constraint_duration: str | None = None
    """ISO 8601 duration for faster/slower activation constraint."""

    resting_constraint_duration: str | None = None
    """ISO 8601 duration for required resting time."""

    minimum_constraint_duration: str | None = None
    """ISO 8601 minimum activation duration."""

    maximum_constraint_duration: str | None = None
    """ISO 8601 maximum activation duration."""

    standard_market_product_type: str | None = None
    """CIM market product type (A05, A07, A02, Z01, etc.)."""

    linked_bids_identification: str | None = None
    """Technical link group UUID."""

    multipart_bid_identification: str | None = None
    """Multipart group identifier."""

    exclusive_bids_identification: str | None = None
    """Exclusive group identifier."""

    inclusive_bids_identification: str | None = None
    """Inclusive group identifier (last element per XSD sequence)."""

    period: PeriodModel
    """The single Period element for this bid."""

    reasons: tuple[ReasonModel, ...] = ()
    """Optional Reason elements (e.g. period-shift codes, voluntary bid IDs)."""


class BidDocumentModel(BaseModel):
    """Internal model for a ``ReserveBid_MarketDocument``.

    Produced by :class:`~nexa_mfrr_eam.documents.reserve_bid.BidDocumentBuilder`
    and consumed by the XML serializer.
    """

    model_config = ConfigDict(frozen=True)

    mrid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    """Document unique identifier (UUID v4)."""

    revision_number: str = "1"
    """Always 1; each update is a new document with a new mRID."""

    document_type: str = "A37"
    """CIM document type: A37 = ReserveBid_MarketDocument."""

    process_type: str = "A47"
    """CIM process type: A47 = mFRR."""

    sender_mrid: str
    """BSP party identifier."""

    sender_coding_scheme: str
    """Coding scheme for sender (A01 EIC or A10 GS1)."""

    sender_market_role_type: str = "A46"
    """Market role: A46 = BSP."""

    receiver_mrid: str
    """TSO party identifier (EIC)."""

    receiver_coding_scheme: str = "A01"
    """Coding scheme for receiver (EIC)."""

    receiver_market_role_type: str = "A34"
    """Market role: A34 = TSO."""

    created_datetime: datetime
    """Document creation timestamp (UTC)."""

    reserve_bid_period_start: datetime
    """Start of the trading day covered by this document (UTC)."""

    reserve_bid_period_end: datetime
    """End of the trading day covered by this document (UTC)."""

    domain_mrid: str
    """Control area EIC for the TSO."""

    domain_coding_scheme: str = "A01"
    """Coding scheme for domain (always A01 EIC)."""

    subject_mrid: str | None = None
    """Subject party identifier (typically same as sender)."""

    subject_coding_scheme: str | None = None
    """Coding scheme for subject."""

    subject_market_role_type: str | None = None
    """Market role for subject (A46 = BSP)."""

    bid_time_series: tuple[BidTimeSeriesModel, ...] = ()
    """All BidTimeSeries included in this document."""
