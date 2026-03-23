"""ReserveBid_MarketDocument builder.

Entry point is the :func:`BidDocument` factory function, which returns a
:class:`BidDocumentBuilder`.  Call :meth:`~BidDocumentBuilder.build` to get a
:class:`BuiltBidDocument` that can be validated and serialized to XML.

Example::

    from nexa_mfrr_eam import Bid, BidDocument, MARIMode, TSO

    doc = (
        BidDocument(tso=TSO.STATNETT)
        .sender(party_id="9999909919920", coding_scheme="A10")
        .add_bid(bid)
        .build()
    )
    errors = doc.validate(mari_mode=MARIMode.PRE_MARI)
    xml_bytes = doc.to_xml()
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

from nexa_mfrr_eam.bids.validation import validate_document
from nexa_mfrr_eam.exceptions import BidValidationError
from nexa_mfrr_eam.tso import get_tso_config
from nexa_mfrr_eam.types import (
    TSO,
    BidDocumentModel,
    BidTimeSeriesModel,
    MARIMode,
)
from nexa_mfrr_eam.xml.serialize import serialize_reserve_bid_document


class BidDocumentBuilder:
    """Mutable builder for a ReserveBid_MarketDocument.

    Do not instantiate directly; use :func:`BidDocument` instead.
    """

    def __init__(self, tso: TSO) -> None:
        """Initialise the builder for the given TSO.

        Args:
            tso: The target TSO.
        """
        self._tso = tso
        self._tso_config = get_tso_config(tso)
        self._sender_mrid: str | None = None
        self._sender_coding_scheme: str | None = None
        self._bids: list[BidTimeSeriesModel] = []
        self._requires_psr_type: bool = self._tso_config.requires_psr_type

    def sender(self, party_id: str, coding_scheme: str) -> BidDocumentBuilder:
        """Set the sender (BSP) party identifier.

        Args:
            party_id: BSP party ID (EIC code or GS1 number).
            coding_scheme: Coding scheme (``"A01"`` EIC or ``"A10"`` GS1).

        Returns:
            This builder (for method chaining).
        """
        self._sender_mrid = party_id
        self._sender_coding_scheme = coding_scheme
        return self

    def add_bid(self, bid: BidTimeSeriesModel) -> BidDocumentBuilder:
        """Add a single bid time series to the document.

        Args:
            bid: A :class:`~nexa_mfrr_eam.types.BidTimeSeriesModel` produced
                by a bid builder.

        Returns:
            This builder (for method chaining).
        """
        self._bids.append(bid)
        return self

    def add_bids(self, bids: Iterable[BidTimeSeriesModel]) -> BidDocumentBuilder:
        """Add multiple bid time series to the document.

        Args:
            bids: An iterable of
                :class:`~nexa_mfrr_eam.types.BidTimeSeriesModel` objects.

        Returns:
            This builder (for method chaining).
        """
        self._bids.extend(bids)
        return self

    def build(self) -> BuiltBidDocument:
        """Validate mandatory fields and return an immutable document.

        Returns:
            A :class:`BuiltBidDocument` ready for validation and serialization.

        Raises:
            :class:`~nexa_mfrr_eam.exceptions.BidValidationError`: If sender
                or bids are missing.
        """
        errors: list[str] = []
        if self._sender_mrid is None or self._sender_coding_scheme is None:
            errors.append("sender() must be called before build()")
        if not self._bids:
            errors.append("At least one bid must be added before build()")
        if errors:
            raise BidValidationError(errors)

        # Type-narrowed after checks
        sender_mrid: str = self._sender_mrid  # type: ignore[assignment]
        sender_scheme: str = self._sender_coding_scheme  # type: ignore[assignment]

        now = datetime.now(tz=UTC)

        # Compute reserveBid_Period from the union of all bid periods
        all_starts = [b.period.time_interval_start for b in self._bids]
        all_ends = [b.period.time_interval_end for b in self._bids]
        period_start = min(all_starts)
        period_end = max(all_ends)

        model = BidDocumentModel(
            mrid=str(uuid.uuid4()),
            revision_number="1",
            document_type="A37",
            process_type="A47",
            sender_mrid=sender_mrid,
            sender_coding_scheme=sender_scheme,
            sender_market_role_type="A46",
            receiver_mrid=self._tso_config.receiver_mrid,
            receiver_coding_scheme="A01",
            receiver_market_role_type="A34",
            created_datetime=now,
            reserve_bid_period_start=period_start,
            reserve_bid_period_end=period_end,
            domain_mrid=self._tso_config.domain_mrid,
            domain_coding_scheme="A01",
            subject_mrid=sender_mrid,
            subject_coding_scheme=sender_scheme,
            subject_market_role_type="A46",
            bid_time_series=tuple(self._bids),
        )
        return BuiltBidDocument(
            model,
            self._tso,
            self._tso_config.min_bid_mw,
            self._tso_config.max_bids_per_message,
            self._requires_psr_type,
        )


class BuiltBidDocument:
    """An immutable ReserveBid_MarketDocument ready for validation and XML output.

    Returned by :meth:`BidDocumentBuilder.build`.
    """

    def __init__(
        self,
        model: BidDocumentModel,
        tso: TSO,
        min_bid_mw: int,
        max_bids_per_message: int,
        requires_psr_type: bool = False,
    ) -> None:
        """Initialise the built document.

        Args:
            model: The frozen document model.
            tso: The target TSO.
            min_bid_mw: TSO minimum bid volume in MW.
            max_bids_per_message: TSO maximum BidTimeSeries per document.
            requires_psr_type: Whether ``mktPSRType.psrType`` is mandatory.
        """
        self._model = model
        self._tso = tso
        self._min_bid_mw = min_bid_mw
        self._max_bids_per_message = max_bids_per_message
        self._requires_psr_type = requires_psr_type

    @property
    def model(self) -> BidDocumentModel:
        """Return the underlying frozen document model."""
        return self._model

    @property
    def time_series_count(self) -> int:
        """Return the number of BidTimeSeries in this document."""
        return len(self._model.bid_time_series)

    def validate(self, mari_mode: MARIMode | None = None) -> list[str]:
        """Validate the document against common and TSO-specific rules.

        Args:
            mari_mode: MARI mode to use for price limit checks.  If ``None``
                the global setting from :func:`~nexa_mfrr_eam.config.get_mari_mode`
                is used.

        Returns:
            A (possibly empty) list of human-readable error strings.
        """
        if mari_mode is None:
            from nexa_mfrr_eam.config import get_mari_mode

            mari_mode = get_mari_mode()

        return validate_document(
            self._model,
            mari_mode=mari_mode,
            min_bid_mw=self._min_bid_mw,
            max_bids_per_message=self._max_bids_per_message,
            requires_psr_type=self._requires_psr_type,
        )

    def to_xml(self, pretty_print: bool = True) -> bytes:
        """Serialize this document to CIM XML bytes.

        Args:
            pretty_print: Whether to indent the output.  Defaults to ``True``.

        Returns:
            UTF-8 encoded XML bytes beginning with an XML declaration.
        """
        return serialize_reserve_bid_document(self._model, pretty_print=pretty_print)


def BidDocument(tso: TSO) -> BidDocumentBuilder:  # noqa: N802  (intentional factory function named as class)
    """Create a :class:`BidDocumentBuilder` targeting the given TSO.

    Args:
        tso: The target TSO (e.g. ``TSO.STATNETT``).

    Returns:
        A fresh :class:`BidDocumentBuilder` instance.

    Example::

        doc = (
            BidDocument(tso=TSO.STATNETT)
            .sender(party_id="9999909919920", coding_scheme="A10")
            .add_bid(bid)
            .build()
        )
    """
    return BidDocumentBuilder(tso)
