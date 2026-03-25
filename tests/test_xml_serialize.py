"""Tests for the CIM XML serializer (xml/serialize.py)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from lxml import etree
from nexa_mfrr_eam.types import (
    BidDocumentModel,
    BidTimeSeriesModel,
    PeriodModel,
    PointModel,
    ReasonModel,
)
from nexa_mfrr_eam.xml.namespaces import (
    IEC_NAMESPACE,
    IEC_NAMESPACE_V74,
    SchemaVersion,
)
from nexa_mfrr_eam.xml.serialize import serialize_reserve_bid_document

MTU_DT = datetime(2026, 3, 21, 10, 0, tzinfo=UTC)
MTU_END = MTU_DT + timedelta(minutes=15)
SENDER_ID = "9999909919920"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_doc_model(
    bids: list[BidTimeSeriesModel] | None = None,
    subject: bool = True,
) -> BidDocumentModel:
    if bids is None:
        point = PointModel(
            quantity=Decimal("20"),
            minimum_quantity=Decimal("10"),
            energy_price=Decimal("50"),
        )
        period = PeriodModel(
            time_interval_start=MTU_DT,
            time_interval_end=MTU_END,
            point=point,
        )
        bid = BidTimeSeriesModel(
            mrid=str(uuid.uuid4()),
            divisible_code="A01",
            flow_direction="A01",
            connecting_domain_mrid="10YNO-2--------T",
            registered_resource_mrid="NOKG90901",
            registered_resource_coding_scheme="NNO",
            standard_market_product_type="A07",
            period=period,
        )
        bids = [bid]

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


def _parse_xml(xml_bytes: bytes) -> etree._Element:
    return etree.fromstring(xml_bytes)


# ---------------------------------------------------------------------------
# Output format
# ---------------------------------------------------------------------------


class TestSerializeFormat:
    def test_returns_bytes(self) -> None:
        doc = _build_doc_model()
        result = serialize_reserve_bid_document(doc)
        assert isinstance(result, bytes)

    def test_starts_with_xml_declaration(self) -> None:
        doc = _build_doc_model()
        result = serialize_reserve_bid_document(doc)
        assert result.startswith(b"<?xml version='1.0' encoding='UTF-8'?>")

    def test_root_element_name(self) -> None:
        doc = _build_doc_model()
        root = _parse_xml(serialize_reserve_bid_document(doc))
        assert etree.QName(root.tag).localname == "ReserveBid_MarketDocument"

    def test_uses_iec_v74_namespace_by_default(self) -> None:
        doc = _build_doc_model()
        result = serialize_reserve_bid_document(doc)
        assert IEC_NAMESPACE_V74.encode() in result

    def test_v72_schema_version_uses_iec_v72_namespace(self) -> None:
        doc = _build_doc_model()
        result = serialize_reserve_bid_document(doc, schema_version=SchemaVersion.V72)
        assert IEC_NAMESPACE.encode() in result

    def test_pretty_print_false_no_newlines(self) -> None:
        doc = _build_doc_model()
        result = serialize_reserve_bid_document(doc, pretty_print=False)
        # Without pretty_print, there should be fewer newlines
        assert result.count(b"\n") < 10


# ---------------------------------------------------------------------------
# Document header elements
# ---------------------------------------------------------------------------


class TestDocumentHeader:
    def setup_method(self) -> None:
        doc = _build_doc_model()
        raw = serialize_reserve_bid_document(doc)
        ns = IEC_NAMESPACE_V74
        self.root = _parse_xml(raw)
        self.ns = ns

    def _find(self, tag: str) -> etree._Element | None:
        return self.root.find(f"{{{self.ns}}}{tag}")

    def _text(self, tag: str) -> str | None:
        el = self._find(tag)
        return el.text if el is not None else None

    def test_mrid_present(self) -> None:
        assert self._text("mRID") == "36247cbe-6a29-462d-8ef1-1695edbe0863"

    def test_revision_number(self) -> None:
        assert self._text("revisionNumber") == "1"

    def test_document_type(self) -> None:
        assert self._text("type") == "A37"

    def test_process_type(self) -> None:
        assert self._text("process.processType") == "A47"

    def test_sender_mrid_text(self) -> None:
        el = self._find("sender_MarketParticipant.mRID")
        assert el is not None
        assert el.text == SENDER_ID

    def test_sender_mrid_coding_scheme(self) -> None:
        el = self._find("sender_MarketParticipant.mRID")
        assert el is not None
        assert el.get("codingScheme") == "A10"

    def test_receiver_mrid_text(self) -> None:
        el = self._find("receiver_MarketParticipant.mRID")
        assert el is not None
        assert el.text == "10X1001A1001A38Y"

    def test_receiver_coding_scheme(self) -> None:
        el = self._find("receiver_MarketParticipant.mRID")
        assert el is not None
        assert el.get("codingScheme") == "A01"

    def test_created_datetime_format(self) -> None:
        # Must include seconds: YYYY-MM-DDTHH:MM:SSZ
        text = self._text("createdDateTime")
        assert text == "2026-03-21T09:00:00Z"

    def test_domain_mrid(self) -> None:
        el = self._find("domain.mRID")
        assert el is not None
        assert el.text == "10YNO-0--------C"
        assert el.get("codingScheme") == "A01"

    def test_subject_mrid_present(self) -> None:
        el = self._find("subject_MarketParticipant.mRID")
        assert el is not None
        assert el.text == SENDER_ID

    def test_subject_absent_when_none(self) -> None:
        doc = _build_doc_model(subject=False)
        root = _parse_xml(serialize_reserve_bid_document(doc))
        ns = IEC_NAMESPACE_V74
        el = root.find(f"{{{ns}}}subject_MarketParticipant.mRID")
        assert el is None

    def test_reserve_bid_period_start(self) -> None:
        ti = self._find("reserveBid_Period.timeInterval")
        assert ti is not None
        ns = self.ns
        start = ti.find(f"{{{ns}}}start")
        assert start is not None
        # No seconds in interval format
        assert start.text == "2026-03-21T10:00Z"

    def test_reserve_bid_period_no_seconds(self) -> None:
        ti = self._find("reserveBid_Period.timeInterval")
        assert ti is not None
        ns = self.ns
        start = ti.find(f"{{{ns}}}start")
        assert start is not None
        assert ":00Z" not in (start.text or "")[14:]  # no seconds at HH:MM part


# ---------------------------------------------------------------------------
# BidTimeSeries elements
# ---------------------------------------------------------------------------


class TestBidTimeSeries:
    def setup_method(self) -> None:
        doc = _build_doc_model()
        raw = serialize_reserve_bid_document(doc)
        ns = IEC_NAMESPACE_V74
        self.root = _parse_xml(raw)
        self.ns = ns
        self.bts = self.root.find(f"{{{ns}}}Bid_TimeSeries")
        assert self.bts is not None

    def _text(self, tag: str) -> str | None:
        ns = self.ns
        el = self.bts.find(f"{{{ns}}}{tag}")  # type: ignore[union-attr]
        return el.text if el is not None else None

    def test_business_type(self) -> None:
        assert self._text("businessType") == "B74"

    def test_acquiring_domain_mrid(self) -> None:
        ns = self.ns
        el = self.bts.find(f"{{{ns}}}acquiring_Domain.mRID")  # type: ignore[union-attr]
        assert el is not None
        assert el.text == "10Y1001A1001A91G"
        assert el.get("codingScheme") == "A01"

    def test_connecting_domain_mrid(self) -> None:
        ns = self.ns
        el = self.bts.find(f"{{{ns}}}connecting_Domain.mRID")  # type: ignore[union-attr]
        assert el is not None
        assert el.text == "10YNO-2--------T"
        assert el.get("codingScheme") == "A01"

    def test_quantity_measure_unit(self) -> None:
        assert self._text("quantity_Measurement_Unit.name") == "MAW"

    def test_currency_unit(self) -> None:
        assert self._text("currency_Unit.name") == "EUR"

    def test_divisible_code(self) -> None:
        assert self._text("divisible") == "A01"

    def test_status_is_nested(self) -> None:
        ns = self.ns
        status_el = self.bts.find(f"{{{ns}}}status")  # type: ignore[union-attr]
        assert status_el is not None
        value_el = status_el.find(f"{{{ns}}}value")
        assert value_el is not None
        assert value_el.text == "A06"

    def test_registered_resource_mrid(self) -> None:
        ns = self.ns
        el = self.bts.find(f"{{{ns}}}registeredResource.mRID")  # type: ignore[union-attr]
        assert el is not None
        assert el.text == "NOKG90901"
        assert el.get("codingScheme") == "NNO"

    def test_flow_direction(self) -> None:
        assert self._text("flowDirection.direction") == "A01"

    def test_energy_price_measure_unit(self) -> None:
        assert self._text("energyPrice_Measurement_Unit.name") == "MWH"

    def test_standard_market_product_type(self) -> None:
        assert self._text("standard_MarketProduct.marketProductType") == "A07"

    def test_auction_mrid(self) -> None:
        assert self._text("auction.mRID") == "MFRR_ENERGY_ACTIVATION_MARKET"


# ---------------------------------------------------------------------------
# Period element
# ---------------------------------------------------------------------------


class TestPeriodElement:
    def setup_method(self) -> None:
        doc = _build_doc_model()
        raw = serialize_reserve_bid_document(doc)
        ns = IEC_NAMESPACE_V74
        root = _parse_xml(raw)
        bts = root.find(f"{{{ns}}}Bid_TimeSeries")
        assert bts is not None
        self.period = bts.find(f"{{{ns}}}Period")
        assert self.period is not None
        self.ns = ns

    def test_time_interval_start(self) -> None:
        ns = self.ns
        ti = self.period.find(f"{{{ns}}}timeInterval")  # type: ignore[union-attr]
        assert ti is not None
        start = ti.find(f"{{{ns}}}start")
        assert start is not None
        assert start.text == "2026-03-21T10:00Z"

    def test_time_interval_end(self) -> None:
        ns = self.ns
        ti = self.period.find(f"{{{ns}}}timeInterval")  # type: ignore[union-attr]
        assert ti is not None
        end = ti.find(f"{{{ns}}}end")
        assert end is not None
        assert end.text == "2026-03-21T10:15Z"

    def test_resolution(self) -> None:
        ns = self.ns
        res = self.period.find(f"{{{ns}}}resolution")  # type: ignore[union-attr]
        assert res is not None
        assert res.text == "PT15M"

    def test_point_position(self) -> None:
        ns = self.ns
        point = self.period.find(f"{{{ns}}}Point")  # type: ignore[union-attr]
        assert point is not None
        pos = point.find(f"{{{ns}}}position")
        assert pos is not None
        assert pos.text == "1"

    def test_point_quantity(self) -> None:
        ns = self.ns
        point = self.period.find(f"{{{ns}}}Point")  # type: ignore[union-attr]
        assert point is not None
        qty = point.find(f"{{{ns}}}quantity.quantity")
        assert qty is not None
        assert qty.text == "20"

    def test_point_minimum_quantity_divisible(self) -> None:
        ns = self.ns
        point = self.period.find(f"{{{ns}}}Point")  # type: ignore[union-attr]
        assert point is not None
        min_qty = point.find(f"{{{ns}}}minimum_Quantity.quantity")
        assert min_qty is not None
        assert min_qty.text == "10"

    def test_point_energy_price(self) -> None:
        ns = self.ns
        point = self.period.find(f"{{{ns}}}Point")  # type: ignore[union-attr]
        assert point is not None
        price = point.find(f"{{{ns}}}energy_Price.amount")
        assert price is not None
        assert price.text == "50"

    def test_minimum_quantity_absent_for_indivisible(self) -> None:
        point = PointModel(quantity=Decimal("20"), energy_price=Decimal("50"))
        period = PeriodModel(
            time_interval_start=MTU_DT,
            time_interval_end=MTU_END,
            point=point,
        )
        bid = BidTimeSeriesModel(
            mrid=str(uuid.uuid4()),
            divisible_code="A02",
            flow_direction="A01",
            period=period,
        )
        doc = BidDocumentModel(
            sender_mrid=SENDER_ID,
            sender_coding_scheme="A10",
            receiver_mrid="10X1001A1001A38Y",
            created_datetime=MTU_DT,
            reserve_bid_period_start=MTU_DT,
            reserve_bid_period_end=MTU_END,
            domain_mrid="10YNO-0--------C",
            bid_time_series=(bid,),
        )
        raw = serialize_reserve_bid_document(doc)
        ns = IEC_NAMESPACE_V74
        root = _parse_xml(raw)
        bts = root.find(f"{{{ns}}}Bid_TimeSeries")
        assert bts is not None
        period_el = bts.find(f"{{{ns}}}Period")
        assert period_el is not None
        pt = period_el.find(f"{{{ns}}}Point")
        assert pt is not None
        min_qty = pt.find(f"{{{ns}}}minimum_Quantity.quantity")
        assert min_qty is None


# ---------------------------------------------------------------------------
# Optional/constraint elements
# ---------------------------------------------------------------------------


class TestOptionalElements:
    def _serialize_with_constraints(self, **kwargs: str | None) -> bytes:
        point = PointModel(quantity=Decimal("20"), minimum_quantity=Decimal("10"))
        period = PeriodModel(
            time_interval_start=MTU_DT,
            time_interval_end=MTU_END,
            point=point,
        )
        bid = BidTimeSeriesModel(
            mrid=str(uuid.uuid4()),
            divisible_code="A01",
            flow_direction="A01",
            period=period,
            **kwargs,  # type: ignore[arg-type]
        )
        doc = BidDocumentModel(
            sender_mrid=SENDER_ID,
            sender_coding_scheme="A10",
            receiver_mrid="10X1001A1001A38Y",
            created_datetime=MTU_DT,
            reserve_bid_period_start=MTU_DT,
            reserve_bid_period_end=MTU_END,
            domain_mrid="10YNO-0--------C",
            bid_time_series=(bid,),
        )
        return serialize_reserve_bid_document(doc)

    def test_activation_constraint_duration_present(self) -> None:
        raw = self._serialize_with_constraints(activation_constraint_duration="PT3M")
        assert b"activation_ConstraintDuration.duration" in raw
        assert b"PT3M" in raw

    def test_resting_constraint_duration_present(self) -> None:
        raw = self._serialize_with_constraints(resting_constraint_duration="PT60M")
        assert b"resting_ConstraintDuration.duration" in raw

    def test_maximum_constraint_duration_present(self) -> None:
        raw = self._serialize_with_constraints(maximum_constraint_duration="PT90M")
        assert b"maximum_ConstraintDuration.duration" in raw

    def test_linked_bids_identification_present(self) -> None:
        link_id = str(uuid.uuid4())
        raw = self._serialize_with_constraints(linked_bids_identification=link_id)
        assert b"linkedBidsIdentification" in raw

    def test_connecting_domain_absent_when_none(self) -> None:
        raw = self._serialize_with_constraints()
        assert b"connecting_Domain.mRID" not in raw

    def test_inclusive_bids_identification_serialized_v72(self) -> None:
        raw_v72 = serialize_reserve_bid_document(
            _build_doc_model(
                bids=[
                    BidTimeSeriesModel(
                        mrid=str(uuid.uuid4()),
                        divisible_code="A01",
                        flow_direction="A01",
                        period=PeriodModel(
                            time_interval_start=MTU_DT,
                            time_interval_end=MTU_END,
                            point=PointModel(
                                quantity=Decimal("20"),
                                energy_price=Decimal("50"),
                            ),
                        ),
                        inclusive_bids_identification="INCL-GROUP-001",
                    )
                ]
            ),
            schema_version=SchemaVersion.V72,
        )
        assert b"inclusiveBidsIdentification" in raw_v72
        assert b"INCL-GROUP-001" in raw_v72

    def test_psr_type_serialized_v72(self) -> None:
        raw_v72 = serialize_reserve_bid_document(
            _build_doc_model(
                bids=[
                    BidTimeSeriesModel(
                        mrid=str(uuid.uuid4()),
                        divisible_code="A01",
                        flow_direction="A01",
                        period=PeriodModel(
                            time_interval_start=MTU_DT,
                            time_interval_end=MTU_END,
                            point=PointModel(
                                quantity=Decimal("20"),
                                energy_price=Decimal("50"),
                            ),
                        ),
                        psr_type="B19",
                    )
                ]
            ),
            schema_version=SchemaVersion.V72,
        )
        assert b"mktPSRType.psrType" in raw_v72
        assert b"B19" in raw_v72


# ---------------------------------------------------------------------------
# Reason elements
# ---------------------------------------------------------------------------


class TestReasonElements:
    def test_reason_code_and_text_serialized(self) -> None:
        point = PointModel(quantity=Decimal("20"), minimum_quantity=Decimal("10"))
        period = PeriodModel(
            time_interval_start=MTU_DT,
            time_interval_end=MTU_END,
            point=point,
        )
        bid = BidTimeSeriesModel(
            mrid=str(uuid.uuid4()),
            divisible_code="A01",
            flow_direction="A01",
            period=period,
            reasons=(ReasonModel(code="A95", text="voluntary-bid-id-001"),),
        )
        doc = BidDocumentModel(
            sender_mrid=SENDER_ID,
            sender_coding_scheme="A10",
            receiver_mrid="10X1001A1001A38Y",
            created_datetime=MTU_DT,
            reserve_bid_period_start=MTU_DT,
            reserve_bid_period_end=MTU_END,
            domain_mrid="10YNO-0--------C",
            bid_time_series=(bid,),
        )
        raw = serialize_reserve_bid_document(doc)
        assert b"Reason" in raw
        assert b"A95" in raw
        assert b"voluntary-bid-id-001" in raw


# ---------------------------------------------------------------------------
# XSD element ordering
# ---------------------------------------------------------------------------


class TestElementOrdering:
    """Verify that key elements appear in XSD-mandated order."""

    def test_bid_time_series_element_order(self) -> None:
        doc = _build_doc_model()
        raw = serialize_reserve_bid_document(doc)
        ns = IEC_NAMESPACE_V74
        root = _parse_xml(raw)
        bts = root.find(f"{{{ns}}}Bid_TimeSeries")
        assert bts is not None

        tags = [etree.QName(child.tag).localname for child in bts]

        def pos(tag: str) -> int:
            try:
                return tags.index(tag)
            except ValueError:
                return -1

        # mRID before businessType before acquiring_Domain.mRID
        assert pos("mRID") < pos("businessType")
        assert pos("businessType") < pos("acquiring_Domain.mRID")
        # divisible before status
        assert pos("divisible") < pos("status")
        # status before flowDirection.direction
        assert pos("status") < pos("flowDirection.direction")
        # flowDirection before energyPrice_Measurement_Unit.name (v7.4 long name)
        assert pos("flowDirection.direction") < pos("energyPrice_Measurement_Unit.name")
        # standard_MarketProduct before Period
        assert pos("standard_MarketProduct.marketProductType") < pos("Period")
