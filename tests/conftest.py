"""Shared pytest fixtures and configuration."""

import datetime

import pytest

UTC = datetime.UTC


@pytest.fixture()
def mtu_10h() -> datetime.datetime:
    """Return a well-known MTU start: 2026-03-21T10:00Z."""
    return datetime.datetime(2026, 3, 21, 10, 0, tzinfo=UTC)


@pytest.fixture()
def mtu_10h15() -> datetime.datetime:
    """Return a well-known MTU start: 2026-03-21T10:15Z."""
    return datetime.datetime(2026, 3, 21, 10, 15, tzinfo=UTC)
