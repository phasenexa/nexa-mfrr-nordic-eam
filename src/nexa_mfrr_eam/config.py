"""Global configuration for the nexa-mfrr-nordic-eam library.

Provides a module-level MARI mode setting that affects validation rules,
timing calculations, and price limits throughout the library.
"""

from nexa_mfrr_eam.types import MARIMode

_global_mari_mode: MARIMode = MARIMode.PRE_MARI


def configure(mari_mode: MARIMode = MARIMode.PRE_MARI) -> None:
    """Set the global MARI mode for the library.

    Args:
        mari_mode: The MARI mode to use globally. Defaults to
            :attr:`MARIMode.PRE_MARI`.

    Example:
        >>> from nexa_mfrr_eam import configure, MARIMode
        >>> configure(mari_mode=MARIMode.POST_MARI)
    """
    global _global_mari_mode
    _global_mari_mode = mari_mode


def get_mari_mode() -> MARIMode:
    """Return the currently configured global MARI mode.

    Returns:
        The active :class:`MARIMode` setting.

    Example:
        >>> from nexa_mfrr_eam import get_mari_mode, MARIMode
        >>> get_mari_mode()
        <MARIMode.PRE_MARI: 'pre_mari'>
    """
    return _global_mari_mode
