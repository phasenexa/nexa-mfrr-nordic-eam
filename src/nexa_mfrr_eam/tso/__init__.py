"""TSO-specific configuration objects for nexa_mfrr_eam.

Each TSO module defines a singleton :class:`~nexa_mfrr_eam.tso.base.TSOConfig`
that the validation and serialization layers consume.  Use
:func:`get_tso_config` to retrieve the config for a given TSO.
"""

from __future__ import annotations

from nexa_mfrr_eam.tso.base import TSOConfig
from nexa_mfrr_eam.tso.statnett import STATNETT_CONFIG
from nexa_mfrr_eam.tso.svk import SVK_CONFIG
from nexa_mfrr_eam.types import TSO


def get_tso_config(tso: TSO) -> TSOConfig:
    """Return the :class:`TSOConfig` for the given TSO.

    Args:
        tso: The target TSO.

    Returns:
        The corresponding :class:`~nexa_mfrr_eam.tso.base.TSOConfig`.

    Raises:
        NotImplementedError: If the TSO does not yet have a config module.
    """
    if tso is TSO.STATNETT:
        return STATNETT_CONFIG
    if tso is TSO.SVK:
        return SVK_CONFIG
    raise NotImplementedError(f"TSO config not yet implemented for {tso}")


__all__ = ["TSOConfig", "get_tso_config", "STATNETT_CONFIG", "SVK_CONFIG"]
