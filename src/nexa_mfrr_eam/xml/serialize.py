"""Serialize BidDocumentModel to CIM XML using lxml.

Element names and ordering follow the XSD sequence defined in CLAUDE.md.
The reference file ``SN_Simple_ReserveBid_MarketDocument.xml`` is the
canonical example this serializer targets.

Datetime formats
----------------
* ``createdDateTime``: ``YYYY-MM-DDTHH:MM:SSZ`` (with seconds, per ESMP_DateTime)
* ``timeInterval start/end``: ``YYYY-MM-DDTHH:MMZ`` (no seconds, per YMDHM_DateTime)
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from lxml import etree

from nexa_mfrr_eam.types import BidDocumentModel, BidTimeSeriesModel
from nexa_mfrr_eam.xml.namespaces import DEFAULT_SERIALIZE_NAMESPACE


def _fmt_created(dt: datetime) -> str:
    """Format a datetime as ``YYYY-MM-DDTHH:MM:SSZ`` (with seconds).

    Args:
        dt: A timezone-aware UTC datetime.

    Returns:
        ISO 8601 string with seconds and Z suffix.
    """
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _fmt_interval(dt: datetime) -> str:
    """Format a datetime as ``YYYY-MM-DDTHH:MMZ`` (no seconds).

    Args:
        dt: A timezone-aware UTC datetime.

    Returns:
        ISO 8601 string without seconds, with Z suffix.
    """
    return dt.strftime("%Y-%m-%dT%H:%MZ")


def _fmt_decimal(value: Decimal) -> str:
    """Format a Decimal for XML, avoiding scientific notation.

    Args:
        value: The decimal value to format.

    Returns:
        Fixed-point string representation.
    """
    return format(value, "f")


def _sub(parent: etree._Element, tag: str, text: str) -> etree._Element:
    """Create a child element with text content.

    Args:
        parent: Parent XML element.
        tag: Element tag name.
        text: Text content.

    Returns:
        The newly created element.
    """
    el: etree._Element = etree.SubElement(parent, tag)
    el.text = text
    return el


def _sub_attr(
    parent: etree._Element,
    tag: str,
    text: str,
    attr: str,
    attr_val: str,
) -> etree._Element:
    """Create a child element with an attribute and text content.

    Args:
        parent: Parent XML element.
        tag: Element tag name.
        text: Text content.
        attr: Attribute name.
        attr_val: Attribute value.

    Returns:
        The newly created element.
    """
    el: etree._Element = etree.SubElement(parent, tag, {attr: attr_val})
    el.text = text
    return el


def _serialize_bid_time_series(
    parent: etree._Element,
    ts: BidTimeSeriesModel,
) -> None:
    """Append a ``Bid_TimeSeries`` element to *parent*.

    Element ordering follows the mandatory XSD sequence (CLAUDE.md).

    Args:
        parent: The ``ReserveBid_MarketDocument`` root element.
        ts: The bid time series model to serialize.
    """
    bts: etree._Element = etree.SubElement(parent, "Bid_TimeSeries")

    # 1. mRID
    _sub(bts, "mRID", ts.mrid)

    # 2. auction.mRID (optional)
    if ts.auction_mrid:
        _sub(bts, "auction.mRID", ts.auction_mrid)

    # 3. businessType
    _sub(bts, "businessType", ts.business_type)

    # 4. acquiring_Domain.mRID
    _sub_attr(
        bts, "acquiring_Domain.mRID", ts.acquiring_domain_mrid, "codingScheme", "A01"
    )

    # 5. connecting_Domain.mRID (optional)
    if ts.connecting_domain_mrid is not None:
        _sub_attr(
            bts,
            "connecting_Domain.mRID",
            ts.connecting_domain_mrid,
            "codingScheme",
            "A01",
        )

    # 7. quantity_Measure_Unit.name
    _sub(bts, "quantity_Measure_Unit.name", ts.quantity_measure_unit_name)

    # 8. currency_Unit.name (optional but present in reference XML)
    if ts.currency_unit_name:
        _sub(bts, "currency_Unit.name", ts.currency_unit_name)

    # 10. divisible
    _sub(bts, "divisible", ts.divisible_code)

    # 11. linkedBidsIdentification (optional)
    if ts.linked_bids_identification is not None:
        _sub(bts, "linkedBidsIdentification", ts.linked_bids_identification)

    # 12. multipartBidIdentification (optional)
    if ts.multipart_bid_identification is not None:
        _sub(bts, "multipartBidIdentification", ts.multipart_bid_identification)

    # 13. exclusiveBidsIdentification (optional)
    if ts.exclusive_bids_identification is not None:
        _sub(bts, "exclusiveBidsIdentification", ts.exclusive_bids_identification)

    # 15. status (optional; nested <value> child per XSD)
    if ts.status_value:
        status_el: etree._Element = etree.SubElement(bts, "status")
        _sub(status_el, "value", ts.status_value)

    # 17. registeredResource.mRID (optional)
    if ts.registered_resource_mrid is not None:
        scheme = ts.registered_resource_coding_scheme or "A01"
        _sub_attr(
            bts,
            "registeredResource.mRID",
            ts.registered_resource_mrid,
            "codingScheme",
            scheme,
        )

    # 18. flowDirection.direction
    _sub(bts, "flowDirection.direction", ts.flow_direction)

    # 20. energyPrice_Measure_Unit.name (optional per XSD, present in reference)
    if ts.energy_price_measure_unit_name:
        _sub(bts, "energyPrice_Measure_Unit.name", ts.energy_price_measure_unit_name)

    # 24. activation_ConstraintDuration.duration (optional)
    if ts.activation_constraint_duration is not None:
        _sub(
            bts,
            "activation_ConstraintDuration.duration",
            ts.activation_constraint_duration,
        )

    # 25. resting_ConstraintDuration.duration (optional)
    if ts.resting_constraint_duration is not None:
        _sub(
            bts,
            "resting_ConstraintDuration.duration",
            ts.resting_constraint_duration,
        )

    # 26. minimum_ConstraintDuration.duration (optional)
    if ts.minimum_constraint_duration is not None:
        _sub(
            bts,
            "minimum_ConstraintDuration.duration",
            ts.minimum_constraint_duration,
        )

    # 27. maximum_ConstraintDuration.duration (optional)
    if ts.maximum_constraint_duration is not None:
        _sub(
            bts,
            "maximum_ConstraintDuration.duration",
            ts.maximum_constraint_duration,
        )

    # 28. standard_MarketProduct.marketProductType (optional)
    if ts.standard_market_product_type is not None:
        _sub(
            bts,
            "standard_MarketProduct.marketProductType",
            ts.standard_market_product_type,
        )

    # 31. Period (1..*)
    period_el: etree._Element = etree.SubElement(bts, "Period")
    ti_el: etree._Element = etree.SubElement(period_el, "timeInterval")
    _sub(ti_el, "start", _fmt_interval(ts.period.time_interval_start))
    _sub(ti_el, "end", _fmt_interval(ts.period.time_interval_end))
    _sub(period_el, "resolution", ts.period.resolution)

    point_el: etree._Element = etree.SubElement(period_el, "Point")
    _sub(point_el, "position", str(ts.period.point.position))
    _sub(point_el, "quantity.quantity", _fmt_decimal(ts.period.point.quantity))
    if ts.period.point.minimum_quantity is not None:
        _sub(
            point_el,
            "minimum_Quantity.quantity",
            _fmt_decimal(ts.period.point.minimum_quantity),
        )
    if ts.period.point.energy_price is not None:
        _sub(
            point_el,
            "energy_Price.amount",
            _fmt_decimal(ts.period.point.energy_price),
        )

    # 33. Reason (0..*)
    for reason in ts.reasons:
        reason_el: etree._Element = etree.SubElement(bts, "Reason")
        _sub(reason_el, "code", reason.code)
        if reason.text is not None:
            _sub(reason_el, "text", reason.text)

    # 34. Linked_BidTimeSeries (0..*)
    for linked in ts.linked_bid_time_series:
        linked_el: etree._Element = etree.SubElement(bts, "Linked_BidTimeSeries")
        _sub(linked_el, "mRID", linked.mrid)
        linked_status_el: etree._Element = etree.SubElement(linked_el, "status")
        _sub(linked_status_el, "value", linked.status_value)

    # 38. inclusiveBidsIdentification (optional, last element per standard XSD)
    if ts.inclusive_bids_identification is not None:
        _sub(bts, "inclusiveBidsIdentification", ts.inclusive_bids_identification)

    # Denmark-specific schema extensions (not in standard NBM XSD).
    # Position is after inclusiveBidsIdentification pending the DK XSD.
    if ts.psr_type is not None:
        _sub(bts, "mktPSRType.psrType", ts.psr_type)
    if ts.note is not None:
        _sub(bts, "Note", ts.note)


def serialize_reserve_bid_document(
    doc: BidDocumentModel,
    pretty_print: bool = True,
    namespace: str = DEFAULT_SERIALIZE_NAMESPACE,
) -> bytes:
    """Serialize a :class:`~nexa_mfrr_eam.types.BidDocumentModel` to XML bytes.

    The output follows the element ordering required by the XSD and matches the
    Statnett reference file structure.

    Args:
        doc: The document model to serialize.
        pretty_print: Whether to indent the XML output.
        namespace: The XML namespace URI to use as the default namespace.

    Returns:
        UTF-8 encoded XML bytes with an XML declaration.
    """
    # lxml accepts None as a key for the default namespace; lxml-stubs types
    # nsmap as Mapping[str, str] and does not model this, so we cast.
    from typing import Any

    _nsmap: Any = {None: namespace}
    root: etree._Element = etree.Element("ReserveBid_MarketDocument", nsmap=_nsmap)

    # Document header elements
    _sub(root, "mRID", doc.mrid)
    _sub(root, "revisionNumber", doc.revision_number)
    _sub(root, "type", doc.document_type)
    _sub(root, "process.processType", doc.process_type)

    _sub_attr(
        root,
        "sender_MarketParticipant.mRID",
        doc.sender_mrid,
        "codingScheme",
        doc.sender_coding_scheme,
    )
    _sub(root, "sender_MarketParticipant.marketRole.type", doc.sender_market_role_type)

    _sub_attr(
        root,
        "receiver_MarketParticipant.mRID",
        doc.receiver_mrid,
        "codingScheme",
        doc.receiver_coding_scheme,
    )
    _sub(
        root,
        "receiver_MarketParticipant.marketRole.type",
        doc.receiver_market_role_type,
    )

    _sub(root, "createdDateTime", _fmt_created(doc.created_datetime))

    period_ti: etree._Element = etree.SubElement(root, "reserveBid_Period.timeInterval")
    _sub(period_ti, "start", _fmt_interval(doc.reserve_bid_period_start))
    _sub(period_ti, "end", _fmt_interval(doc.reserve_bid_period_end))

    _sub_attr(
        root, "domain.mRID", doc.domain_mrid, "codingScheme", doc.domain_coding_scheme
    )

    if doc.subject_mrid is not None:
        _sub_attr(
            root,
            "subject_MarketParticipant.mRID",
            doc.subject_mrid,
            "codingScheme",
            doc.subject_coding_scheme or "A01",
        )
        if doc.subject_market_role_type is not None:
            _sub(
                root,
                "subject_MarketParticipant.marketRole.type",
                doc.subject_market_role_type,
            )

    for ts in doc.bid_time_series:
        _serialize_bid_time_series(root, ts)

    return etree.tostring(
        root,
        pretty_print=pretty_print,
        xml_declaration=True,
        encoding="UTF-8",
    )
