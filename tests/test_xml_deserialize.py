"""Tests for the CIM XML deserializer (xml/deserialize.py)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from nexa_mfrr_eam.exceptions import NexaMFRREAMError
from nexa_mfrr_eam.types import (
    BidDocumentModel,
    BidTimeSeriesModel,
    LinkedBidTimeSeriesModel,
    PeriodModel,
    PointModel,
    ReasonModel,
)
from nexa_mfrr_eam.xml.deserialize import _child_attr, deserialize_reserve_bid_document
from nexa_mfrr_eam.xml.namespaces import IEC_NAMESPACE, NBM_NAMESPACE
from nexa_mfrr_eam.xml.serialize import serialize_reserve_bid_document

MTU_DT = datetime(2026, 3, 21, 10, 0, tzinfo=UTC)
MTU_END = MTU_DT + timedelta(minutes=15)
SENDER_ID = "9999909919920"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _simple_point() -> PointModel:
    return PointModel(
        quantity=Decimal("50"),
        minimum_quantity=Decimal("10"),
        energy_price=Decimal("85.50"),
    )


def _simple_period() -> PeriodModel:
    return PeriodModel(
        time_interval_start=MTU_DT,
        time_interval_end=MTU_END,
        point=_simple_point(),
    )


def _simple_bid(**kwargs: object) -> BidTimeSeriesModel:
    defaults: dict[str, object] = {
        "mrid": str(uuid.uuid4()),
        "divisible_code": "A01",
        "flow_direction": "A01",
        "connecting_domain_mrid": "10YNO-2--------T",
        "registered_resource_mrid": "NOKG90901",
        "registered_resource_coding_scheme": "NNO",
        "standard_market_product_type": "A07",
        "period": _simple_period(),
    }
    defaults.update(kwargs)
    return BidTimeSeriesModel(**defaults)  # type: ignore[arg-type]


def _build_doc(
    bids: list[BidTimeSeriesModel] | None = None,
    subject: bool = True,
) -> BidDocumentModel:
    if bids is None:
        bids = [_simple_bid()]
    return BidDocumentModel(
        mrid="36247cbe-6a29-462d-8ef1-1695edbe0863",
        sender_mrid=SENDER_ID,
        sender_coding_scheme="A10",
        receiver_mrid="10X1001A1001A38Y",
        created_datetime=datetime(2026, 3, 21, 9, 0, 0, tzinfo=UTC),
        reserve_bid_period_start=MTU_DT,
        reserve_bid_period_end=MTU_END,
        domain_mrid="10YNO-0--------C",
        subject_mrid=SENDER_ID if subject else None,
        subject_coding_scheme="A10" if subject else None,
        subject_market_role_type="A46" if subject else None,
        bid_time_series=tuple(bids),
    )


def _roundtrip(
    doc: BidDocumentModel,
    namespace: str = IEC_NAMESPACE,
) -> BidDocumentModel:
    xml_bytes = serialize_reserve_bid_document(doc, namespace=namespace)
    return deserialize_reserve_bid_document(xml_bytes)


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def test_document_mrid_survives(self) -> None:
        doc = _build_doc()
        result = _roundtrip(doc)
        assert result.mrid == doc.mrid

    def test_revision_number_survives(self) -> None:
        doc = _build_doc()
        result = _roundtrip(doc)
        assert result.revision_number == "1"

    def test_sender_fields_survive(self) -> None:
        doc = _build_doc()
        result = _roundtrip(doc)
        assert result.sender_mrid == SENDER_ID
        assert result.sender_coding_scheme == "A10"
        assert result.sender_market_role_type == "A46"

    def test_receiver_fields_survive(self) -> None:
        doc = _build_doc()
        result = _roundtrip(doc)
        assert result.receiver_mrid == "10X1001A1001A38Y"
        assert result.receiver_coding_scheme == "A01"
        assert result.receiver_market_role_type == "A34"

    def test_created_datetime_survives(self) -> None:
        doc = _build_doc()
        result = _roundtrip(doc)
        assert result.created_datetime == datetime(2026, 3, 21, 9, 0, 0, tzinfo=UTC)

    def test_period_survives(self) -> None:
        doc = _build_doc()
        result = _roundtrip(doc)
        assert result.reserve_bid_period_start == MTU_DT
        assert result.reserve_bid_period_end == MTU_END

    def test_domain_mrid_survives(self) -> None:
        doc = _build_doc()
        result = _roundtrip(doc)
        assert result.domain_mrid == "10YNO-0--------C"

    def test_subject_participant_survives(self) -> None:
        doc = _build_doc(subject=True)
        result = _roundtrip(doc)
        assert result.subject_mrid == SENDER_ID
        assert result.subject_coding_scheme == "A10"
        assert result.subject_market_role_type == "A46"

    def test_bid_count_survives(self) -> None:
        bids = [_simple_bid(), _simple_bid()]
        doc = _build_doc(bids=bids)
        result = _roundtrip(doc)
        assert len(result.bid_time_series) == 2

    def test_bid_mrid_survives(self) -> None:
        bid_mrid = str(uuid.uuid4())
        bids = [_simple_bid(mrid=bid_mrid)]
        doc = _build_doc(bids=bids)
        result = _roundtrip(doc)
        assert result.bid_time_series[0].mrid == bid_mrid

    def test_bid_flow_direction_survives(self) -> None:
        doc = _build_doc()
        result = _roundtrip(doc)
        assert result.bid_time_series[0].flow_direction == "A01"

    def test_bid_divisible_code_survives(self) -> None:
        doc = _build_doc()
        result = _roundtrip(doc)
        assert result.bid_time_series[0].divisible_code == "A01"

    def test_bid_resource_survives(self) -> None:
        doc = _build_doc()
        result = _roundtrip(doc)
        ts = result.bid_time_series[0]
        assert ts.registered_resource_mrid == "NOKG90901"
        assert ts.registered_resource_coding_scheme == "NNO"

    def test_period_interval_survives(self) -> None:
        doc = _build_doc()
        result = _roundtrip(doc)
        period = result.bid_time_series[0].period
        assert period.time_interval_start == MTU_DT
        assert period.time_interval_end == MTU_END
        assert period.resolution == "PT15M"

    def test_point_quantity_survives(self) -> None:
        doc = _build_doc()
        result = _roundtrip(doc)
        point = result.bid_time_series[0].period.point
        assert point.quantity == Decimal("50")
        assert point.minimum_quantity == Decimal("10")
        assert point.energy_price == Decimal("85.50")

    def test_standard_market_product_survives(self) -> None:
        doc = _build_doc()
        result = _roundtrip(doc)
        assert result.bid_time_series[0].standard_market_product_type == "A07"


# ---------------------------------------------------------------------------
# Both namespaces accepted
# ---------------------------------------------------------------------------


class TestNamespaces:
    def test_iec_namespace_accepted(self) -> None:
        doc = _build_doc()
        xml_bytes = serialize_reserve_bid_document(doc, namespace=IEC_NAMESPACE)
        result = deserialize_reserve_bid_document(xml_bytes)
        assert result.mrid == doc.mrid

    def test_nbm_namespace_accepted(self) -> None:
        doc = _build_doc()
        xml_bytes = serialize_reserve_bid_document(doc, namespace=NBM_NAMESPACE)
        result = deserialize_reserve_bid_document(xml_bytes)
        assert result.mrid == doc.mrid

    def test_both_namespaces_yield_same_result(self) -> None:
        doc = _build_doc()
        result_iec = _roundtrip(doc, namespace=IEC_NAMESPACE)
        result_nbm = _roundtrip(doc, namespace=NBM_NAMESPACE)
        assert result_iec.mrid == result_nbm.mrid
        assert result_iec.sender_mrid == result_nbm.sender_mrid
        assert len(result_iec.bid_time_series) == len(result_nbm.bid_time_series)

    def test_unknown_namespace_raises(self) -> None:
        xml = (
            b'<?xml version="1.0"?>'
            b'<ReserveBid_MarketDocument xmlns="urn:unknown:ns"/>'
        )
        with pytest.raises(NexaMFRREAMError, match="Unknown XML namespace"):
            deserialize_reserve_bid_document(xml)

    def test_no_namespace_raises(self) -> None:
        xml = b'<?xml version="1.0"?><ReserveBid_MarketDocument/>'
        with pytest.raises(NexaMFRREAMError):
            deserialize_reserve_bid_document(xml)


# ---------------------------------------------------------------------------
# Nested status element
# ---------------------------------------------------------------------------


class TestStatusParsing:
    def test_status_value_parsed_from_nested_element(self) -> None:
        # The serializer emits <status><value>A06</value></status>
        doc = _build_doc()
        result = _roundtrip(doc)
        assert result.bid_time_series[0].status_value == "A06"

    def test_custom_status_value_survives(self) -> None:
        bid = _simple_bid(status_value="A11")
        doc = _build_doc(bids=[bid])
        result = _roundtrip(doc)
        assert result.bid_time_series[0].status_value == "A11"


# ---------------------------------------------------------------------------
# Datetime formats
# ---------------------------------------------------------------------------


class TestDatetimeParsing:
    def test_created_datetime_has_seconds(self) -> None:
        """createdDateTime uses ESMP_DateTime: YYYY-MM-DDTHH:MM:SSZ."""
        doc = _build_doc()
        result = _roundtrip(doc)
        assert result.created_datetime.second == 0
        assert result.created_datetime.tzinfo is UTC

    def test_period_interval_has_no_seconds(self) -> None:
        """timeInterval uses YMDHM_DateTime: YYYY-MM-DDTHH:MMZ (no seconds)."""
        doc = _build_doc()
        result = _roundtrip(doc)
        assert result.reserve_bid_period_start.second == 0
        assert result.reserve_bid_period_start.tzinfo is UTC

    def test_bid_period_interval_is_utc(self) -> None:
        doc = _build_doc()
        result = _roundtrip(doc)
        period = result.bid_time_series[0].period
        assert period.time_interval_start.tzinfo is UTC
        assert period.time_interval_end.tzinfo is UTC


# ---------------------------------------------------------------------------
# Optional fields absent
# ---------------------------------------------------------------------------


class TestOptionalFieldsAbsent:
    def test_no_subject_participant(self) -> None:
        doc = _build_doc(subject=False)
        result = _roundtrip(doc)
        assert result.subject_mrid is None
        assert result.subject_coding_scheme is None
        assert result.subject_market_role_type is None

    def test_no_connecting_domain(self) -> None:
        bid = _simple_bid(connecting_domain_mrid=None)
        doc = _build_doc(bids=[bid])
        result = _roundtrip(doc)
        assert result.bid_time_series[0].connecting_domain_mrid is None

    def test_no_registered_resource(self) -> None:
        bid = _simple_bid(
            registered_resource_mrid=None,
            registered_resource_coding_scheme=None,
        )
        doc = _build_doc(bids=[bid])
        result = _roundtrip(doc)
        ts = result.bid_time_series[0]
        assert ts.registered_resource_mrid is None
        assert ts.registered_resource_coding_scheme is None

    def test_no_standard_market_product(self) -> None:
        bid = _simple_bid(standard_market_product_type=None)
        doc = _build_doc(bids=[bid])
        result = _roundtrip(doc)
        assert result.bid_time_series[0].standard_market_product_type is None

    def test_no_energy_price_on_point(self) -> None:
        point = PointModel(quantity=Decimal("15"))  # no price (period-shift-only)
        period = PeriodModel(
            time_interval_start=MTU_DT,
            time_interval_end=MTU_END,
            point=point,
        )
        bid = _simple_bid(period=period)
        doc = _build_doc(bids=[bid])
        result = _roundtrip(doc)
        assert result.bid_time_series[0].period.point.energy_price is None

    def test_no_minimum_quantity_on_point(self) -> None:
        point = PointModel(quantity=Decimal("20"), energy_price=Decimal("60"))
        period = PeriodModel(
            time_interval_start=MTU_DT,
            time_interval_end=MTU_END,
            point=point,
        )
        bid = _simple_bid(period=period)
        doc = _build_doc(bids=[bid])
        result = _roundtrip(doc)
        assert result.bid_time_series[0].period.point.minimum_quantity is None


# ---------------------------------------------------------------------------
# Optional fields present
# ---------------------------------------------------------------------------


class TestOptionalFieldsPresent:
    def test_auction_mrid_survives(self) -> None:
        bid = _simple_bid(auction_mrid="CUSTOM_AUCTION_ID")
        doc = _build_doc(bids=[bid])
        result = _roundtrip(doc)
        assert result.bid_time_series[0].auction_mrid == "CUSTOM_AUCTION_ID"

    def test_activation_constraint_duration_survives(self) -> None:
        bid = _simple_bid(activation_constraint_duration="PT3M")
        doc = _build_doc(bids=[bid])
        result = _roundtrip(doc)
        assert result.bid_time_series[0].activation_constraint_duration == "PT3M"

    def test_resting_constraint_duration_survives(self) -> None:
        bid = _simple_bid(resting_constraint_duration="PT60M")
        doc = _build_doc(bids=[bid])
        result = _roundtrip(doc)
        assert result.bid_time_series[0].resting_constraint_duration == "PT60M"

    def test_maximum_constraint_duration_survives(self) -> None:
        bid = _simple_bid(maximum_constraint_duration="PT90M")
        doc = _build_doc(bids=[bid])
        result = _roundtrip(doc)
        assert result.bid_time_series[0].maximum_constraint_duration == "PT90M"

    def test_linked_bids_identification_survives(self) -> None:
        link_id = str(uuid.uuid4())
        bid = _simple_bid(linked_bids_identification=link_id)
        doc = _build_doc(bids=[bid])
        result = _roundtrip(doc)
        assert result.bid_time_series[0].linked_bids_identification == link_id

    def test_exclusive_bids_identification_survives(self) -> None:
        group_id = str(uuid.uuid4())
        bid = _simple_bid(exclusive_bids_identification=group_id)
        doc = _build_doc(bids=[bid])
        result = _roundtrip(doc)
        assert result.bid_time_series[0].exclusive_bids_identification == group_id

    def test_multipart_bid_identification_survives(self) -> None:
        group_id = str(uuid.uuid4())
        bid = _simple_bid(multipart_bid_identification=group_id)
        doc = _build_doc(bids=[bid])
        result = _roundtrip(doc)
        assert result.bid_time_series[0].multipart_bid_identification == group_id

    def test_inclusive_bids_identification_survives(self) -> None:
        group_id = str(uuid.uuid4())
        bid = _simple_bid(inclusive_bids_identification=group_id)
        doc = _build_doc(bids=[bid])
        result = _roundtrip(doc)
        assert result.bid_time_series[0].inclusive_bids_identification == group_id


# ---------------------------------------------------------------------------
# Multiple bids
# ---------------------------------------------------------------------------


class TestMultipleBids:
    def test_two_bids_parsed(self) -> None:
        bid1 = _simple_bid(flow_direction="A01")
        bid2 = _simple_bid(flow_direction="A02")
        doc = _build_doc(bids=[bid1, bid2])
        result = _roundtrip(doc)
        assert len(result.bid_time_series) == 2

    def test_bid_order_preserved(self) -> None:
        mrids = [str(uuid.uuid4()) for _ in range(3)]
        bids = [_simple_bid(mrid=m) for m in mrids]
        doc = _build_doc(bids=bids)
        result = _roundtrip(doc)
        assert [ts.mrid for ts in result.bid_time_series] == mrids


# ---------------------------------------------------------------------------
# Linked bids (conditional)
# ---------------------------------------------------------------------------


class TestLinkedBids:
    def test_linked_bid_mrid_parsed(self) -> None:
        linked_mrid = str(uuid.uuid4())
        linked = LinkedBidTimeSeriesModel(mrid=linked_mrid, status_value="A55")
        bid = _simple_bid(linked_bid_time_series=(linked,))
        doc = _build_doc(bids=[bid])
        result = _roundtrip(doc)
        ts = result.bid_time_series[0]
        assert len(ts.linked_bid_time_series) == 1
        assert ts.linked_bid_time_series[0].mrid == linked_mrid

    def test_linked_bid_status_value_from_nested_element(self) -> None:
        """Linked_BidTimeSeries uses nested status element."""
        linked = LinkedBidTimeSeriesModel(mrid=str(uuid.uuid4()), status_value="A55")
        bid = _simple_bid(linked_bid_time_series=(linked,))
        doc = _build_doc(bids=[bid])
        result = _roundtrip(doc)
        assert result.bid_time_series[0].linked_bid_time_series[0].status_value == "A55"

    def test_multiple_linked_bids_parsed(self) -> None:
        links = tuple(
            LinkedBidTimeSeriesModel(mrid=str(uuid.uuid4()), status_value="A56")
            for _ in range(3)
        )
        bid = _simple_bid(linked_bid_time_series=links)
        doc = _build_doc(bids=[bid])
        result = _roundtrip(doc)
        assert len(result.bid_time_series[0].linked_bid_time_series) == 3


# ---------------------------------------------------------------------------
# Reason elements
# ---------------------------------------------------------------------------


class TestReasonElements:
    def test_reason_code_and_text_parsed(self) -> None:
        reason = ReasonModel(code="A95", text="bid-ref-12345")
        bid = _simple_bid(reasons=(reason,))
        doc = _build_doc(bids=[bid])
        result = _roundtrip(doc)
        ts = result.bid_time_series[0]
        assert len(ts.reasons) == 1
        assert ts.reasons[0].code == "A95"
        assert ts.reasons[0].text == "bid-ref-12345"

    def test_reason_code_only_parsed(self) -> None:
        reason = ReasonModel(code="Z64", text=None)
        bid = _simple_bid(reasons=(reason,))
        doc = _build_doc(bids=[bid])
        result = _roundtrip(doc)
        ts = result.bid_time_series[0]
        assert ts.reasons[0].code == "Z64"
        assert ts.reasons[0].text is None

    def test_multiple_reasons_parsed(self) -> None:
        reasons = (
            ReasonModel(code="Z64", text=None),
            ReasonModel(code="A95", text="secondary-id"),
        )
        bid = _simple_bid(reasons=reasons)
        doc = _build_doc(bids=[bid])
        result = _roundtrip(doc)
        parsed_reasons = result.bid_time_series[0].reasons
        assert len(parsed_reasons) == 2
        assert parsed_reasons[0].code == "Z64"
        assert parsed_reasons[1].code == "A95"


# ---------------------------------------------------------------------------
# Denmark-specific fields
# ---------------------------------------------------------------------------


class TestDenmarkSpecificFields:
    def test_psr_type_survives(self) -> None:
        bid = _simple_bid(psr_type="B19")  # wind onshore
        doc = _build_doc(bids=[bid])
        result = _roundtrip(doc)
        assert result.bid_time_series[0].psr_type == "B19"

    def test_note_survives(self) -> None:
        bid = _simple_bid(note="Custom BRP reference")
        doc = _build_doc(bids=[bid])
        result = _roundtrip(doc)
        assert result.bid_time_series[0].note == "Custom BRP reference"

    def test_psr_type_absent_when_not_set(self) -> None:
        doc = _build_doc()
        result = _roundtrip(doc)
        assert result.bid_time_series[0].psr_type is None

    def test_note_absent_when_not_set(self) -> None:
        doc = _build_doc()
        result = _roundtrip(doc)
        assert result.bid_time_series[0].note is None


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestOptionalFieldsPresent2:
    def test_minimum_constraint_duration_survives(self) -> None:
        bid = _simple_bid(minimum_constraint_duration="PT30M")
        doc = _build_doc(bids=[bid])
        result = _roundtrip(doc)
        assert result.bid_time_series[0].minimum_constraint_duration == "PT30M"

    def test_sender_coding_scheme_defaults_to_a01_when_absent(self) -> None:
        """_child_attr returns None when codingScheme attribute is missing."""
        ns = IEC_NAMESPACE
        xml = (
            f'<?xml version="1.0"?>'
            f'<ReserveBid_MarketDocument xmlns="{ns}">'
            f"<mRID>abc123</mRID>"
            f"<revisionNumber>1</revisionNumber>"
            f"<type>A37</type>"
            f"<process.processType>A47</process.processType>"
            f"<sender_MarketParticipant.mRID>9999</sender_MarketParticipant.mRID>"
            f"{_SENDER_ROLE}"
            f"<receiver_MarketParticipant.mRID>10X1001A1001A38Y"
            f"</receiver_MarketParticipant.mRID>"
            f"{_RECEIVER_ROLE}"
            f"<createdDateTime>2026-03-21T09:00:00Z</createdDateTime>"
            f"<reserveBid_Period.timeInterval>"
            f"<start>2026-03-21T10:00Z</start>"
            f"<end>2026-03-21T10:15Z</end>"
            f"</reserveBid_Period.timeInterval>"
            f"<domain.mRID codingScheme='A01'>10YNO-0--------C</domain.mRID>"
            f"<Bid_TimeSeries>"
            f"<mRID>bid-1</mRID>"
            f"<businessType>B74</businessType>"
            f"{_ACQUIRING}"
            f"<quantity_Measure_Unit.name>MAW</quantity_Measure_Unit.name>"
            f"<divisible>A01</divisible>"
            f"<flowDirection.direction>A01</flowDirection.direction>"
            f"<Period>"
            f"<timeInterval>"
            f"<start>2026-03-21T10:00Z</start>"
            f"<end>2026-03-21T10:15Z</end>"
            f"</timeInterval>"
            f"<resolution>PT15M</resolution>"
            f"<Point>"
            f"<position>1</position>"
            f"<quantity.quantity>50</quantity.quantity>"
            f"</Point>"
            f"</Period>"
            f"</Bid_TimeSeries>"
            f"</ReserveBid_MarketDocument>"
        ).encode()
        result = deserialize_reserve_bid_document(xml)
        # codingScheme attribute was absent → should default to "A01"
        assert result.sender_coding_scheme == "A01"


# Short aliases used in hand-crafted XML to stay within line length limits
_SENDER = "<sender_MarketParticipant.mRID codingScheme='A10'>9999"
_SENDER_END = "</sender_MarketParticipant.mRID>"
_SENDER_ROLE = (
    "<sender_MarketParticipant.marketRole.type>A46"
    "</sender_MarketParticipant.marketRole.type>"
)
_RECEIVER = (
    "<receiver_MarketParticipant.mRID codingScheme='A01'>"
    "10X1001A1001A38Y</receiver_MarketParticipant.mRID>"
)
_RECEIVER_ROLE = (
    "<receiver_MarketParticipant.marketRole.type>A34"
    "</receiver_MarketParticipant.marketRole.type>"
)
_ACQUIRING = (
    "<acquiring_Domain.mRID codingScheme='A01'>"
    "10Y1001A1001A91G</acquiring_Domain.mRID>"
)


class TestChildAttrHelper:
    def test_returns_none_when_element_absent(self) -> None:
        """_child_attr returns None when the child element is not found."""
        from lxml import etree

        ns = IEC_NAMESPACE
        el = etree.fromstring(f'<root xmlns="{ns}"><other>x</other></root>'.encode())
        result = _child_attr(el, "missing_element", ns, "codingScheme")
        assert result is None

    def test_returns_attribute_value_when_present(self) -> None:
        from lxml import etree

        ns = IEC_NAMESPACE
        el = etree.fromstring(
            f'<root xmlns="{ns}"><child codingScheme="A10">val</child></root>'.encode()
        )
        result = _child_attr(el, "child", ns, "codingScheme")
        assert result == "A10"


class TestErrorCases:
    def test_malformed_xml_raises(self) -> None:
        with pytest.raises(NexaMFRREAMError, match="Malformed XML"):
            deserialize_reserve_bid_document(b"<not valid xml")

    def test_unknown_namespace_raises_with_message(self) -> None:
        xml = (
            b'<?xml version="1.0"?>'
            b'<ReserveBid_MarketDocument xmlns="urn:some:unknown:namespace"/>'
        )
        with pytest.raises(NexaMFRREAMError, match="Unknown XML namespace"):
            deserialize_reserve_bid_document(xml)

    def test_missing_required_element_raises(self) -> None:
        """_req_text raises when a required child element is absent."""
        ns = IEC_NAMESPACE
        # Document is missing <mRID> entirely
        xml = (
            f'<?xml version="1.0"?>'
            f'<ReserveBid_MarketDocument xmlns="{ns}">'
            f"<revisionNumber>1</revisionNumber>"
            f"</ReserveBid_MarketDocument>"
        ).encode()
        with pytest.raises(NexaMFRREAMError, match="Required element"):
            deserialize_reserve_bid_document(xml)

    def test_missing_reserve_bid_period_time_interval_raises(self) -> None:
        """Missing <reserveBid_Period.timeInterval> raises NexaMFRREAMError."""
        ns = IEC_NAMESPACE
        xml = (
            f'<?xml version="1.0"?>'
            f'<ReserveBid_MarketDocument xmlns="{ns}">'
            f"<mRID>abc123</mRID>"
            f"<revisionNumber>1</revisionNumber>"
            f"<type>A37</type>"
            f"<process.processType>A47</process.processType>"
            f"{_SENDER}9999{_SENDER_END}"
            f"{_SENDER_ROLE}"
            f"{_RECEIVER}"
            f"{_RECEIVER_ROLE}"
            f"<createdDateTime>2026-03-21T09:00:00Z</createdDateTime>"
            f"</ReserveBid_MarketDocument>"
        ).encode()
        with pytest.raises(NexaMFRREAMError, match="reserveBid_Period.timeInterval"):
            deserialize_reserve_bid_document(xml)

    def _minimal_doc_xml(self, ns: str, bts_inner: str) -> bytes:
        """Return a minimal valid document XML with custom BidTimeSeries content."""
        return (
            f'<?xml version="1.0"?>'
            f'<ReserveBid_MarketDocument xmlns="{ns}">'
            f"<mRID>abc123</mRID>"
            f"<revisionNumber>1</revisionNumber>"
            f"<type>A37</type>"
            f"<process.processType>A47</process.processType>"
            f"{_SENDER}{_SENDER_END}"
            f"{_SENDER_ROLE}"
            f"{_RECEIVER}"
            f"{_RECEIVER_ROLE}"
            f"<createdDateTime>2026-03-21T09:00:00Z</createdDateTime>"
            f"<reserveBid_Period.timeInterval>"
            f"<start>2026-03-21T10:00Z</start>"
            f"<end>2026-03-21T10:15Z</end>"
            f"</reserveBid_Period.timeInterval>"
            f"<domain.mRID codingScheme='A01'>10YNO-0--------C</domain.mRID>"
            f"<Bid_TimeSeries>{bts_inner}</Bid_TimeSeries>"
            f"</ReserveBid_MarketDocument>"
        ).encode()

    def test_missing_period_in_bid_time_series_raises(self) -> None:
        """Missing <Period> inside Bid_TimeSeries raises NexaMFRREAMError."""
        bts = (
            "<mRID>bid-1</mRID>"
            "<businessType>B74</businessType>"
            f"{_ACQUIRING}"
            "<quantity_Measure_Unit.name>MAW</quantity_Measure_Unit.name>"
            "<divisible>A01</divisible>"
            "<flowDirection.direction>A01</flowDirection.direction>"
            # <Period> intentionally omitted
        )
        xml = self._minimal_doc_xml(IEC_NAMESPACE, bts)
        with pytest.raises(NexaMFRREAMError, match="Period"):
            deserialize_reserve_bid_document(xml)

    def test_missing_time_interval_in_period_raises(self) -> None:
        """Missing <timeInterval> inside Period raises NexaMFRREAMError."""
        bts = (
            "<mRID>bid-1</mRID>"
            "<businessType>B74</businessType>"
            f"{_ACQUIRING}"
            "<quantity_Measure_Unit.name>MAW</quantity_Measure_Unit.name>"
            "<divisible>A01</divisible>"
            "<flowDirection.direction>A01</flowDirection.direction>"
            "<Period>"
            # <timeInterval> intentionally omitted
            "<resolution>PT15M</resolution>"
            "<Point><position>1</position><quantity.quantity>50</quantity.quantity></Point>"
            "</Period>"
        )
        xml = self._minimal_doc_xml(IEC_NAMESPACE, bts)
        with pytest.raises(NexaMFRREAMError, match="timeInterval"):
            deserialize_reserve_bid_document(xml)

    def test_missing_point_in_period_raises(self) -> None:
        """Missing <Point> inside Period raises NexaMFRREAMError."""
        bts = (
            "<mRID>bid-1</mRID>"
            "<businessType>B74</businessType>"
            f"{_ACQUIRING}"
            "<quantity_Measure_Unit.name>MAW</quantity_Measure_Unit.name>"
            "<divisible>A01</divisible>"
            "<flowDirection.direction>A01</flowDirection.direction>"
            "<Period>"
            "<timeInterval>"
            "<start>2026-03-21T10:00Z</start>"
            "<end>2026-03-21T10:15Z</end>"
            "</timeInterval>"
            "<resolution>PT15M</resolution>"
            # <Point> intentionally omitted
            "</Period>"
        )
        xml = self._minimal_doc_xml(IEC_NAMESPACE, bts)
        with pytest.raises(NexaMFRREAMError, match="Point"):
            deserialize_reserve_bid_document(xml)

    def test_missing_status_in_linked_bid_raises(self) -> None:
        """Missing <status> inside Linked_BidTimeSeries raises NexaMFRREAMError."""
        bts = (
            "<mRID>bid-1</mRID>"
            "<businessType>B74</businessType>"
            f"{_ACQUIRING}"
            "<quantity_Measure_Unit.name>MAW</quantity_Measure_Unit.name>"
            "<divisible>A01</divisible>"
            "<flowDirection.direction>A01</flowDirection.direction>"
            "<Period>"
            "<timeInterval>"
            "<start>2026-03-21T10:00Z</start>"
            "<end>2026-03-21T10:15Z</end>"
            "</timeInterval>"
            "<resolution>PT15M</resolution>"
            "<Point><position>1</position><quantity.quantity>50</quantity.quantity></Point>"
            "</Period>"
            "<Linked_BidTimeSeries>"
            "<mRID>linked-bid-1</mRID>"
            # <status> intentionally omitted
            "</Linked_BidTimeSeries>"
        )
        xml = self._minimal_doc_xml(IEC_NAMESPACE, bts)
        with pytest.raises(NexaMFRREAMError, match="status"):
            deserialize_reserve_bid_document(xml)
