"""XML namespace URI constants for CIM mFRR documents.

Two namespace URIs are in use for the ReserveBid_MarketDocument:

* :data:`NBM_NAMESPACE` – used in the vendored XSD from nordicbalancingmodel.net.
* :data:`IEC_NAMESPACE` – used in the Statnett example XML and chosen as the
  default for serialization because it matches the reference file.

Both must be accepted during deserialization.
"""

NBM_NAMESPACE: str = "urn:iec62325:ediel:nbm:reservebiddocument:7:2"
"""Namespace from the vendored NBM XSD (nordicbalancingmodel.net variant)."""

IEC_NAMESPACE: str = "urn:iec62325.351:tc57wg16:451-7:reservebiddocument:7:2"
"""Namespace from the Statnett example XML (IEC 62325-451-7 variant)."""

KNOWN_NAMESPACES: tuple[str, ...] = (NBM_NAMESPACE, IEC_NAMESPACE)
"""All namespace URIs accepted during deserialization."""

DEFAULT_SERIALIZE_NAMESPACE: str = IEC_NAMESPACE
"""Namespace URI used when serializing outgoing documents."""
