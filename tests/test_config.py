"""Tests for nexa_mfrr_eam.config module."""

from __future__ import annotations

import nexa_mfrr_eam.config as config_module
import pytest
from nexa_mfrr_eam.config import configure, get_mari_mode
from nexa_mfrr_eam.types import MARIMode


@pytest.fixture(autouse=True)
def reset_config() -> None:
    """Reset global MARI mode to PRE_MARI before each test."""
    configure(MARIMode.PRE_MARI)


def test_configure_post_mari_sets_global() -> None:
    configure(MARIMode.POST_MARI)
    assert get_mari_mode() is MARIMode.POST_MARI


def test_configure_default_resets_to_pre_mari() -> None:
    configure(MARIMode.POST_MARI)
    configure()  # no-arg reset
    assert get_mari_mode() is MARIMode.PRE_MARI


def test_get_mari_mode_returns_current() -> None:
    assert get_mari_mode() is MARIMode.PRE_MARI
    configure(MARIMode.POST_MARI)
    assert get_mari_mode() is MARIMode.POST_MARI


def test_import_smoke() -> None:
    from nexa_mfrr_eam import MARIMode as m
    from nexa_mfrr_eam import configure as c
    from nexa_mfrr_eam import get_mari_mode as g

    assert callable(c)
    assert callable(g)
    assert m.PRE_MARI is not None


def test_global_state_is_module_level() -> None:
    configure(MARIMode.POST_MARI)
    assert config_module._global_mari_mode is MARIMode.POST_MARI
