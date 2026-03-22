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


class BidValidationError(NexaMFRREAMError):
    """Raised when a bid or document fails validation rules.

    Collects all validation errors before raising so the caller can
    see the full list of problems at once.
    """

    def __init__(self, errors: list[str]) -> None:
        """Initialise with a list of human-readable error messages.

        Args:
            errors: One or more validation error descriptions.
        """
        self.errors = errors
        super().__init__("; ".join(errors))
