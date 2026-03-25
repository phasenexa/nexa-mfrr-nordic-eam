"""Tests for the Fingrid (FI) TSO configuration."""

from __future__ import annotations

from nexa_mfrr_eam.tso import FINGRID_CONFIG, get_tso_config
from nexa_mfrr_eam.types import TSO


def test_receiver_mrid() -> None:
    assert FINGRID_CONFIG.receiver_mrid == "10X1001A1001A264"


def test_domain_mrid() -> None:
    assert FINGRID_CONFIG.domain_mrid == "10YFI-1--------U"


def test_min_bid_mw() -> None:
    assert FINGRID_CONFIG.min_bid_mw == 1


def test_max_bids_per_message_is_2000() -> None:
    """Fingrid enforces a stricter 2000 bid limit per message."""
    assert FINGRID_CONFIG.max_bids_per_message == 2000


def test_supports_inclusive_bids() -> None:
    """Fingrid supports inclusive bids for aggregated resources."""
    assert FINGRID_CONFIG.supports_inclusive_bids is True


def test_no_period_shift() -> None:
    assert FINGRID_CONFIG.supports_period_shift is False


def test_resource_coding_scheme_is_eic() -> None:
    assert FINGRID_CONFIG.resource_coding_scheme == "A01"


def test_psr_type_not_required() -> None:
    assert FINGRID_CONFIG.requires_psr_type is False


def test_get_tso_config_returns_fingrid_config() -> None:
    assert get_tso_config(TSO.FINGRID) is FINGRID_CONFIG
