"""Typed exception hierarchy for nexa-mfrr-nordic-eam.

All exceptions inherit from :class:`NexaMFRREAMError`.
"""


class NexaMFRREAMError(Exception):
    """Base exception for all nexa-mfrr-nordic-eam errors."""


class InvalidMTUError(NexaMFRREAMError):
    """Raised when an invalid MTU datetime is provided.

    MTU datetimes must fall on 15-minute boundaries (minutes 0, 15, 30, 45)
    with seconds and microseconds both zero.
    """


class NaiveDatetimeError(NexaMFRREAMError):
    """Raised when a naive (timezone-unaware) datetime is provided.

    All datetimes in this library must be timezone-aware UTC.
    """
