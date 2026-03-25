"""XML namespace URI constants and version-aware element name mapping.

Three namespace URIs are in active use for ``ReserveBid_MarketDocument``:

* :data:`NBM_NAMESPACE` – Nordic-specific XSD from nordicbalancingmodel.net (v7.2).
* :data:`IEC_NAMESPACE` – IEC 62325-451-7 v7.2, used in the Statnett example XML.
* :data:`IEC_NAMESPACE_V74` – IEC 62325-451-7 v7.4, the default for serialization.

All three must be accepted during deserialization.  Serialization defaults to v7.4
because it has the widest compatibility and ``inclusiveBidsIdentification`` is a
standard element (not an extension).

Element names differ between v7.2 and v7.4 for the three unit name fields:

=================================  =================================
v7.2 (NBM and IEC)                 v7.4 (IEC)
=================================  =================================
``quantity_Measure_Unit.name``     ``quantity_Measurement_Unit.name``
``price_Measure_Unit.name``        ``price_Measurement_Unit.name``
``energyPrice_Measure_Unit.name``  ``energyPrice_Measurement_Unit.name``
=================================  =================================
"""

from __future__ import annotations

from enum import Enum

# ---------------------------------------------------------------------------
# Namespace URI constants
# ---------------------------------------------------------------------------

NBM_NAMESPACE: str = "urn:iec62325:ediel:nbm:reservebiddocument:7:2"
"""Namespace from the vendored NBM XSD (nordicbalancingmodel.net variant, v7.2)."""

IEC_NAMESPACE: str = "urn:iec62325.351:tc57wg16:451-7:reservebiddocument:7:2"
"""Namespace from the Statnett example XML (IEC 62325-451-7 v7.2)."""

IEC_NAMESPACE_V74: str = "urn:iec62325.351:tc57wg16:451-7:reservebiddocument:7:4"
"""Namespace for IEC 62325-451-7 v7.4 (default for serialization)."""

KNOWN_NAMESPACES: tuple[str, ...] = (NBM_NAMESPACE, IEC_NAMESPACE, IEC_NAMESPACE_V74)
"""All namespace URIs accepted during deserialization."""

# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------


class SchemaVersion(str, Enum):
    """Target schema version for serialization.

    Affects:
    * The namespace URI written to the root element.
    * The element names used for the three unit name fields.
    * The position of ``inclusiveBidsIdentification`` and ``mktPSRType.psrType``
      relative to ``Period`` in ``Bid_TimeSeries``.
    """

    V72 = "7.2"
    """IEC/NBM v7.2 — short element names, ``inclusiveBidsIdentification`` last."""

    V74 = "7.4"
    """IEC v7.4 — long element names, ``inclusiveBidsIdentification`` before Period."""


# ---------------------------------------------------------------------------
# Version-to-namespace mapping
# ---------------------------------------------------------------------------

NAMESPACE_FOR_VERSION: dict[SchemaVersion, str] = {
    SchemaVersion.V72: IEC_NAMESPACE,
    SchemaVersion.V74: IEC_NAMESPACE_V74,
}
"""Maps a :class:`SchemaVersion` to the namespace URI used for serialization."""

# ---------------------------------------------------------------------------
# Version-aware element name mapping
# ---------------------------------------------------------------------------

#: Element name for ``quantity_Measure(ment)_Unit.name`` by version.
QUANTITY_UNIT_ELEMENT: dict[SchemaVersion, str] = {
    SchemaVersion.V72: "quantity_Measure_Unit.name",
    SchemaVersion.V74: "quantity_Measurement_Unit.name",
}

#: Element name for ``price_Measure(ment)_Unit.name`` by version.
PRICE_UNIT_ELEMENT: dict[SchemaVersion, str] = {
    SchemaVersion.V72: "price_Measure_Unit.name",
    SchemaVersion.V74: "price_Measurement_Unit.name",
}

#: Element name for ``energyPrice_Measure(ment)_Unit.name`` by version.
ENERGY_PRICE_UNIT_ELEMENT: dict[SchemaVersion, str] = {
    SchemaVersion.V72: "energyPrice_Measure_Unit.name",
    SchemaVersion.V74: "energyPrice_Measurement_Unit.name",
}

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_SCHEMA_VERSION: SchemaVersion = SchemaVersion.V74
"""Schema version used when serializing outgoing documents."""

DEFAULT_SERIALIZE_NAMESPACE: str = NAMESPACE_FOR_VERSION[DEFAULT_SCHEMA_VERSION]
"""Namespace URI used when serializing outgoing documents (kept for back-compat)."""


def version_for_namespace(namespace: str) -> SchemaVersion:
    """Return the :class:`SchemaVersion` that corresponds to *namespace*.

    Args:
        namespace: A namespace URI from a parsed XML document.

    Returns:
        :data:`SchemaVersion.V74` for the v7.4 URI; :data:`SchemaVersion.V72`
        for both v7.2 URIs (NBM and IEC share the same element names).
    """
    if namespace == IEC_NAMESPACE_V74:
        return SchemaVersion.V74
    return SchemaVersion.V72
