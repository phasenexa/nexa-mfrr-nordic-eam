"""Deserialize CIM XML to BidDocumentModel using lxml.

Accepts all three known namespace URIs for ``ReserveBid_MarketDocument``:

* :data:`~nexa_mfrr_eam.xml.namespaces.NBM_NAMESPACE` (NBM v7.2 XSD)
* :data:`~nexa_mfrr_eam.xml.namespaces.IEC_NAMESPACE` (IEC v7.2, Statnett example)
* :data:`~nexa_mfrr_eam.xml.namespaces.IEC_NAMESPACE_V74` (IEC v7.4)

Element names for the three unit name fields differ between versions:

* v7.2: ``quantity_Measure_Unit.name``, ``energyPrice_Measure_Unit.name``
* v7.4: ``quantity_Measurement_Unit.name``, ``energyPrice_Measurement_Unit.name``

The deserializer detects the version from the namespace URI and reads whichever
element name is correct for that version.

Datetime formats
----------------
* ``createdDateTime``: ``YYYY-MM-DDTHH:MM:SSZ`` (with seconds, ESMP_DateTime)
* ``timeInterval start/end``: ``YYYY-MM-DDTHH:MMZ`` (no seconds, YMDHM_DateTime)
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from lxml import etree

from nexa_mfrr_eam.exceptions import NexaMFRREAMError
from nexa_mfrr_eam.types import (
    BidDocumentModel,
    BidTimeSeriesModel,
    LinkedBidTimeSeriesModel,
    PeriodModel,
    PointModel,
    ReasonModel,
)
from nexa_mfrr_eam.xml.namespaces import (
    ENERGY_PRICE_UNIT_ELEMENT,
    KNOWN_NAMESPACES,
    QUANTITY_UNIT_ELEMENT,
    version_for_namespace,
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _q(tag: str, ns: str) -> str:
    """Return the namespace-qualified tag ``{ns}tag``."""
    return f"{{{ns}}}{tag}"


def _child_text(el: etree._Element, tag: str, ns: str) -> str | None:
    """Return text of the first matching child, or ``None`` if absent."""
    child = el.find(_q(tag, ns))
    if child is None:
        return None
    return child.text or ""


def _req_text(el: etree._Element, tag: str, ns: str) -> str:
    """Return text of a required child element.

    Raises:
        NexaMFRREAMError: If the element is missing or has no text.
    """
    text = _child_text(el, tag, ns)
    if text is None:
        raise NexaMFRREAMError(
            f"Required element <{tag}> not found in <{etree.QName(el.tag).localname}>"
        )
    return text


def _child_attr(el: etree._Element, tag: str, ns: str, attr: str) -> str | None:
    """Return an attribute value from the first matching child, or ``None``."""
    child = el.find(_q(tag, ns))
    if child is None:
        return None
    return child.get(attr)


def _parse_datetime_created(s: str) -> datetime:
    """Parse ``YYYY-MM-DDTHH:MM:SSZ`` (ESMP_DateTime) to UTC datetime."""
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _parse_datetime_interval(s: str) -> datetime:
    """Parse ``YYYY-MM-DDTHH:MMZ`` (YMDHM_DateTime) to UTC datetime."""
    return datetime.strptime(s, "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC)


# ---------------------------------------------------------------------------
# Model parsers
# ---------------------------------------------------------------------------


def _parse_point(point_el: etree._Element, ns: str) -> PointModel:
    """Parse a ``Point`` element into a :class:`PointModel`."""
    position_text = _req_text(point_el, "position", ns)
    quantity_text = _req_text(point_el, "quantity.quantity", ns)

    min_qty_text = _child_text(point_el, "minimum_Quantity.quantity", ns)
    price_text = _child_text(point_el, "energy_Price.amount", ns)

    return PointModel(
        position=int(position_text),
        quantity=Decimal(quantity_text),
        minimum_quantity=Decimal(min_qty_text) if min_qty_text else None,
        energy_price=Decimal(price_text) if price_text else None,
    )


def _parse_period(period_el: etree._Element, ns: str) -> PeriodModel:
    """Parse a ``Period`` element into a :class:`PeriodModel`."""
    ti_el = period_el.find(_q("timeInterval", ns))
    if ti_el is None:
        raise NexaMFRREAMError("Required element <timeInterval> not found in <Period>")

    start_text = _req_text(ti_el, "start", ns)
    end_text = _req_text(ti_el, "end", ns)
    resolution = _req_text(period_el, "resolution", ns)

    point_el = period_el.find(_q("Point", ns))
    if point_el is None:
        raise NexaMFRREAMError("Required element <Point> not found in <Period>")
    point = _parse_point(point_el, ns)

    return PeriodModel(
        time_interval_start=_parse_datetime_interval(start_text),
        time_interval_end=_parse_datetime_interval(end_text),
        resolution=resolution,
        point=point,
    )


def _parse_reason(reason_el: etree._Element, ns: str) -> ReasonModel:
    """Parse a ``Reason`` element into a :class:`ReasonModel`."""
    code = _req_text(reason_el, "code", ns)
    text = _child_text(reason_el, "text", ns)
    return ReasonModel(code=code, text=text if text else None)


def _parse_linked_bid(linked_el: etree._Element, ns: str) -> LinkedBidTimeSeriesModel:
    """Parse a ``Linked_BidTimeSeries`` element."""
    mrid = _req_text(linked_el, "mRID", ns)

    # status is nested: <status><value>A55</value></status>
    status_el = linked_el.find(_q("status", ns))
    if status_el is None:
        raise NexaMFRREAMError(
            "Required element <status> not found in <Linked_BidTimeSeries>"
        )
    status_value = _req_text(status_el, "value", ns)

    return LinkedBidTimeSeriesModel(mrid=mrid, status_value=status_value)


def _parse_bid_time_series(bts_el: etree._Element, ns: str) -> BidTimeSeriesModel:
    """Parse a ``Bid_TimeSeries`` element into a :class:`BidTimeSeriesModel`."""
    schema_ver = version_for_namespace(ns)
    qty_unit_tag = QUANTITY_UNIT_ELEMENT[schema_ver]
    ep_unit_tag = ENERGY_PRICE_UNIT_ELEMENT[schema_ver]

    mrid = _req_text(bts_el, "mRID", ns)
    auction_mrid = _child_text(bts_el, "auction.mRID", ns)
    business_type = _req_text(bts_el, "businessType", ns)
    acquiring_domain_mrid = _req_text(bts_el, "acquiring_Domain.mRID", ns)
    connecting_domain_mrid = _child_text(bts_el, "connecting_Domain.mRID", ns)
    quantity_measure_unit_name = _req_text(bts_el, qty_unit_tag, ns)
    currency_unit_name = _child_text(bts_el, "currency_Unit.name", ns)
    divisible_code = _req_text(bts_el, "divisible", ns)

    linked_bids_id = _child_text(bts_el, "linkedBidsIdentification", ns)
    multipart_bid_id = _child_text(bts_el, "multipartBidIdentification", ns)
    exclusive_bids_id = _child_text(bts_el, "exclusiveBidsIdentification", ns)

    # status is nested: <status><value>A06</value></status>
    status_value: str | None = None
    status_el = bts_el.find(_q("status", ns))
    if status_el is not None:
        status_value = _child_text(status_el, "value", ns)

    # registeredResource.mRID + codingScheme attribute
    registered_resource_mrid: str | None = None
    registered_resource_coding_scheme: str | None = None
    res_el = bts_el.find(_q("registeredResource.mRID", ns))
    if res_el is not None:
        registered_resource_mrid = res_el.text or None
        registered_resource_coding_scheme = res_el.get("codingScheme")

    flow_direction = _req_text(bts_el, "flowDirection.direction", ns)
    energy_price_measure_unit_name = _child_text(bts_el, ep_unit_tag, ns)
    activation_constraint = _child_text(
        bts_el, "activation_ConstraintDuration.duration", ns
    )
    resting_constraint = _child_text(bts_el, "resting_ConstraintDuration.duration", ns)
    minimum_constraint = _child_text(bts_el, "minimum_ConstraintDuration.duration", ns)
    maximum_constraint = _child_text(bts_el, "maximum_ConstraintDuration.duration", ns)
    standard_market_product = _child_text(
        bts_el, "standard_MarketProduct.marketProductType", ns
    )

    period_el = bts_el.find(_q("Period", ns))
    if period_el is None:
        raise NexaMFRREAMError(
            "Required element <Period> not found in <Bid_TimeSeries>"
        )
    period = _parse_period(period_el, ns)

    reasons = tuple(_parse_reason(r, ns) for r in bts_el.findall(_q("Reason", ns)))
    linked_bid_time_series = tuple(
        _parse_linked_bid(lb, ns)
        for lb in bts_el.findall(_q("Linked_BidTimeSeries", ns))
    )

    inclusive_bids_id = _child_text(bts_el, "inclusiveBidsIdentification", ns)
    psr_type = _child_text(bts_el, "mktPSRType.psrType", ns)
    note = _child_text(bts_el, "Note", ns)

    # Build kwargs, only overriding defaults when we have a parsed value
    kwargs: dict[str, object] = {
        "mrid": mrid,
        "business_type": business_type,
        "acquiring_domain_mrid": acquiring_domain_mrid,
        "divisible_code": divisible_code,
        "flow_direction": flow_direction,
        "period": period,
    }
    if auction_mrid is not None:
        kwargs["auction_mrid"] = auction_mrid
    if connecting_domain_mrid is not None:
        kwargs["connecting_domain_mrid"] = connecting_domain_mrid
    if quantity_measure_unit_name:
        kwargs["quantity_measure_unit_name"] = quantity_measure_unit_name
    if currency_unit_name is not None:
        kwargs["currency_unit_name"] = currency_unit_name
    if linked_bids_id is not None:
        kwargs["linked_bids_identification"] = linked_bids_id
    if multipart_bid_id is not None:
        kwargs["multipart_bid_identification"] = multipart_bid_id
    if exclusive_bids_id is not None:
        kwargs["exclusive_bids_identification"] = exclusive_bids_id
    if status_value is not None:
        kwargs["status_value"] = status_value
    if registered_resource_mrid is not None:
        kwargs["registered_resource_mrid"] = registered_resource_mrid
    if registered_resource_coding_scheme is not None:
        kwargs["registered_resource_coding_scheme"] = registered_resource_coding_scheme
    if energy_price_measure_unit_name is not None:
        kwargs["energy_price_measure_unit_name"] = energy_price_measure_unit_name
    if activation_constraint is not None:
        kwargs["activation_constraint_duration"] = activation_constraint
    if resting_constraint is not None:
        kwargs["resting_constraint_duration"] = resting_constraint
    if minimum_constraint is not None:
        kwargs["minimum_constraint_duration"] = minimum_constraint
    if maximum_constraint is not None:
        kwargs["maximum_constraint_duration"] = maximum_constraint
    if standard_market_product is not None:
        kwargs["standard_market_product_type"] = standard_market_product
    if reasons:
        kwargs["reasons"] = reasons
    if linked_bid_time_series:
        kwargs["linked_bid_time_series"] = linked_bid_time_series
    if inclusive_bids_id is not None:
        kwargs["inclusive_bids_identification"] = inclusive_bids_id
    if psr_type is not None:
        kwargs["psr_type"] = psr_type
    if note is not None:
        kwargs["note"] = note

    return BidTimeSeriesModel(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def deserialize_reserve_bid_document(xml_bytes: bytes) -> BidDocumentModel:
    """Deserialize a ``ReserveBid_MarketDocument`` XML byte string.

    Accepts documents using any of the three known namespace URIs (NBM v7.2,
    IEC v7.2, IEC v7.4).  Element names are resolved from the namespace.

    Args:
        xml_bytes: UTF-8 encoded CIM XML bytes.

    Returns:
        A frozen :class:`~nexa_mfrr_eam.types.BidDocumentModel`.

    Raises:
        NexaMFRREAMError: If the XML is malformed, uses an unknown namespace,
            or is missing required elements.
    """
    try:
        root: etree._Element = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as exc:
        raise NexaMFRREAMError(f"Malformed XML: {exc}") from exc

    # Detect namespace from the root element tag: {namespace}LocalName
    raw_tag: str = root.tag
    if not raw_tag.startswith("{"):
        raise NexaMFRREAMError(
            "XML document has no namespace. Expected one of: "
            + ", ".join(KNOWN_NAMESPACES)
        )
    ns = raw_tag[1 : raw_tag.index("}")]
    if ns not in KNOWN_NAMESPACES:
        raise NexaMFRREAMError(
            f"Unknown XML namespace '{ns}'. Expected one of: "
            + ", ".join(KNOWN_NAMESPACES)
        )

    mrid = _req_text(root, "mRID", ns)
    revision_number = _req_text(root, "revisionNumber", ns)
    document_type = _req_text(root, "type", ns)
    process_type = _req_text(root, "process.processType", ns)

    sender_mrid = _req_text(root, "sender_MarketParticipant.mRID", ns)
    sender_coding_scheme = (
        _child_attr(root, "sender_MarketParticipant.mRID", ns, "codingScheme") or "A01"
    )
    sender_market_role_type = _req_text(
        root, "sender_MarketParticipant.marketRole.type", ns
    )

    receiver_mrid = _req_text(root, "receiver_MarketParticipant.mRID", ns)
    receiver_coding_scheme = (
        _child_attr(root, "receiver_MarketParticipant.mRID", ns, "codingScheme")
        or "A01"
    )
    receiver_market_role_type = _req_text(
        root, "receiver_MarketParticipant.marketRole.type", ns
    )

    created_dt_text = _req_text(root, "createdDateTime", ns)
    created_datetime = _parse_datetime_created(created_dt_text)

    period_ti_el = root.find(_q("reserveBid_Period.timeInterval", ns))
    if period_ti_el is None:
        raise NexaMFRREAMError(
            "Required element <reserveBid_Period.timeInterval> not found"
        )
    reserve_bid_period_start = _parse_datetime_interval(
        _req_text(period_ti_el, "start", ns)
    )
    reserve_bid_period_end = _parse_datetime_interval(
        _req_text(period_ti_el, "end", ns)
    )

    domain_mrid = _req_text(root, "domain.mRID", ns)
    domain_coding_scheme = _child_attr(root, "domain.mRID", ns, "codingScheme") or "A01"

    # Optional subject participant
    subject_mrid: str | None = None
    subject_coding_scheme: str | None = None
    subject_market_role_type: str | None = None
    subject_el = root.find(_q("subject_MarketParticipant.mRID", ns))
    if subject_el is not None:
        subject_mrid = subject_el.text or None
        subject_coding_scheme = subject_el.get("codingScheme")
        subject_market_role_type = _child_text(
            root, "subject_MarketParticipant.marketRole.type", ns
        )

    bid_time_series = tuple(
        _parse_bid_time_series(bts_el, ns)
        for bts_el in root.findall(_q("Bid_TimeSeries", ns))
    )

    return BidDocumentModel(
        mrid=mrid,
        revision_number=revision_number,
        document_type=document_type,
        process_type=process_type,
        sender_mrid=sender_mrid,
        sender_coding_scheme=sender_coding_scheme,
        sender_market_role_type=sender_market_role_type,
        receiver_mrid=receiver_mrid,
        receiver_coding_scheme=receiver_coding_scheme,
        receiver_market_role_type=receiver_market_role_type,
        created_datetime=created_datetime,
        reserve_bid_period_start=reserve_bid_period_start,
        reserve_bid_period_end=reserve_bid_period_end,
        domain_mrid=domain_mrid,
        domain_coding_scheme=domain_coding_scheme,
        subject_mrid=subject_mrid,
        subject_coding_scheme=subject_coding_scheme,
        subject_market_role_type=subject_market_role_type,
        bid_time_series=bid_time_series,
    )
