# nexa-mfrr-nordic-eam

[![CI](https://github.com/phasenexa/nexa-mfrr-nordic-eam/actions/workflows/ci.yml/badge.svg)](https://github.com/phasenexa/nexa-mfrr-nordic-eam/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/phasenexa/nexa-mfrr-nordic-eam/branch/main/graph/badge.svg)](https://codecov.io/gh/phasenexa/nexa-mfrr-nordic-eam)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)


> **This project is a work in progress.** The API, documentation, and feature set are under active development and subject to change. If you want to get involved, receive progress updates, or have feedback, please [open an issue](https://github.com/phasenexa/nexa-mfrr-nordic-eam/issues) or contact the repo admin.

Python library for building, validating, and serializing mFRR energy activation market bids for the Nordic TSOs (Statnett, Fingrid, Energinet, Svenska kraftnat).

Built for the 75% who connect via API and build their own.

## Implementation status

| Module | Status | Notes |
|---|---|---|
| `types.py` | Done | All enums + Pydantic models (BidTimeSeriesModel, BidDocumentModel, etc.) |
| `exceptions.py` | Done | NexaMFRREAMError, InvalidMTUError, NaiveDatetimeError, BidValidationError |
| `config.py` | Done | Global MARI mode, configure(), get_mari_mode() |
| `timing.py` | Done | MTU, GateClosure, gate_closure(), current_mtu(), mtu_range(), evaluate_conditional_availability() |
| `__init__.py` | Done | Public re-exports including Bid, BidDocument, BuiltBidDocument |
| `bids/simple.py` | Done | Bid factory + SimpleBidBuilder with fluent API |
| `bids/validation.py` | Done | Common + TSO-configurable validation rules |
| `bids/complex.py` | Done | ExclusiveGroup, MultipartGroup, InclusiveGroup builders with group-level validation |
| `bids/linked.py` | Done | TechnicalLink builder; conditional link methods on SimpleBidBuilder |
| `xml/namespaces.py` | Done | Namespace URI constants; `SchemaVersion` enum; version-aware element name mapping |
| `xml/serialize.py` | Done | Pydantic models to CIM XML; version-aware element names and ordering; defaults to IEC v7.4 |
| `xml/deserialize.py` | Done | CIM XML to Pydantic models; handles all three namespace URIs (NBM v7.2, IEC v7.2, IEC v7.4) |
| `tso/base.py` | Done | TSOConfig strategy dataclass |
| `tso/statnett.py` | Done | Statnett (NO) configuration |
| `tso/fingrid.py` | Done | Fingrid (FI) configuration; max 2000 bids, supports inclusive bids |
| `tso/energinet.py` | Done | Energinet (DK) configuration; requires_psr_type, local DA model |
| `tso/svk.py` | Done | Svenska kraftnat (SE) configuration |
| `documents/reserve_bid.py` | Done | BidDocument factory + BidDocumentBuilder + BuiltBidDocument |
| `documents/acknowledgement.py` | Planned | ACK/NACK parser for bid submission responses |
| `pandas.py` | Planned | DataFrame to Bid conversion |
| `pricing.py` | Done | GS tax (grunnrenteskatt) price adjustment: `gs_adjusted_price`, `gs_adjust_bids` |
| `link_ordering.py` | Done | Technical link ordering per PowerDesk convention: `assign_technical_links` |
| `examples/` | Done | Jupyter notebooks: Statnett daily bid prep; GS tax pricing; technical link ordering; SVK linked bids; Energinet simple + complex; Fingrid bids + deserialization; Fingrid XML round-trip |

## What this does

This library covers the bid submission side of the mFRR EAM workflow: building bids, validating them against TSO rules, serializing to CIM XML, and parsing the acknowledgement responses.

**Implemented today:**

- **Build simple bids** - Divisible and indivisible bids with full attribute support (volume, price, resource, product type, duration constraints)
- **Technically linked bids** - `TechnicalLink` builder groups bids across MTUs under a shared link ID to prevent double-activation
- **Conditionally linked bids** - `.conditionally_available()`, `.conditionally_unavailable()`, `.link_to()` on the bid builder
- **Complex bid groups** - `ExclusiveGroup`, `MultipartGroup`, `InclusiveGroup` builders with group constraints validated at `build()` time
- **TSO configuration** - All four TSOs configured: Statnett (NO), Fingrid (FI), Energinet (DK), Svenska kraftnat (SE)
- **Validate before you send** - Common and TSO-configurable validation rules, pre-MARI and post-MARI price limits
- **Serialize to CIM XML** - Generates compliant `ReserveBid_MarketDocument` XML with strict XSD element ordering
- **Deserialize from CIM XML** - `deserialize_reserve_bid_document()` parses XML back to `BidDocumentModel`; accepts all three namespace URIs (NBM v7.2, IEC v7.2, IEC v7.4)
- **Timing helpers** - Gate closure calculations, MTU boundaries, DST handling, MARI vs pre-MARI timing
- **GS tax pricing** - `gs_adjusted_price` and `gs_adjust_bids` apply the Norwegian resource rent tax formula with per-direction clamping and Statnett price limit enforcement
- **Technical link ordering** - `assign_technical_links` assigns consistent link UUIDs to bids by price rank following the PowerDesk convention

**Planned:**

- **Parse acknowledgements** - Parse `Acknowledgement_MarketDocument` responses (ACK/NACK with reason codes)
- **Pandas integration** - Build bid portfolios from DataFrames

**Out of scope for this repo:** Activation order handling, activation responses, heartbeat processing, bid availability reports, and allocation result parsing. These are downstream market processes and may be covered by separate repos. See [BID_SUBMISSION.md](docs/BID_SUBMISSION.md) for details on the connection and submission routine.

## Installation

```bash
pip install nexa-mfrr-nordic-eam
```

With Pandas support:

```bash
pip install nexa-mfrr-nordic-eam[pandas]
```

## Quick start

### Submit a simple divisible bid to Statnett

```python
from datetime import datetime, timezone
from nexa_mfrr_eam import (
    Bid, BidDocument, Direction, MarketProductType,
    BiddingZone, TSO, MARIMode,
)

# Create a simple divisible up-regulation bid
bid = (
    Bid.up(volume_mw=50, price_eur=85.50)
    .divisible(min_volume_mw=10)
    .for_mtu("2026-03-21T10:00Z")
    .resource("NOKG90901", coding_scheme="NNO")  # Statnett regulation object
    .product_type(MarketProductType.SCHEDULED_AND_DIRECT)  # A07
    .build()
)

# Wrap in a document targeting Statnett
doc = (
    BidDocument(tso=TSO.STATNETT)
    .sender(party_id="9999909919920", coding_scheme="A10")  # GS1
    .add_bid(bid)
    .build()
)

# Validate against Statnett-specific rules (pre-MARI timing)
errors = doc.validate(mari_mode=MARIMode.PRE_MARI)
if errors:
    for e in errors:
        print(f"  {e}")
else:
    xml_bytes = doc.to_xml()
    # Send xml_bytes via your ECP endpoint to Statnett
```

### Build a multipart bid

Multipart bids are groups of simple bids at different price levels for the same MTU. If the higher-priced component is accepted, all cheaper components must also be accepted.

```python
from nexa_mfrr_eam import Direction, MultipartGroup

group = (
    MultipartGroup(bidding_zone=BiddingZone.NO2)
    .direction(Direction.UP)
    .for_mtu("2026-03-21T10:00Z")
    .resource("NOKG90901", coding_scheme="NNO")
    .add_component(volume_mw=20, price_eur=50.00)
    .add_component(volume_mw=15, price_eur=75.00)
    .add_component(volume_mw=10, price_eur=120.00)
    .build()
)

doc = (
    BidDocument(tso=TSO.STATNETT)
    .sender(party_id="9999909919920", coding_scheme="A10")
    .add_bids(group)
    .build()
)
```

### Build an exclusive group

Only one bid in the group can be activated. Useful when you have alternative resources that cannot run simultaneously.

```python
from nexa_mfrr_eam import ExclusiveGroup

group = (
    ExclusiveGroup(bidding_zone=BiddingZone.NO2)
    .for_mtu("2026-03-21T10:00Z")
    .add_bid(
        Bid.up(volume_mw=30, price_eur=60.00)
        .indivisible()
        .resource("NOKG90901", coding_scheme="NNO")
    )
    .add_bid(
        Bid.up(volume_mw=50, price_eur=80.00)
        .divisible(min_volume_mw=10)
        .resource("NOKG90902", coding_scheme="NNO")
    )
    .product_type(MarketProductType.SCHEDULED_ONLY)
    .build()
)
```

### Build technically linked bids across MTUs

Technical linking ensures a resource is not double-activated when a bid in one MTU is activated via direct activation and is still ramping during the next MTU.

```python
from nexa_mfrr_eam import TechnicalLink

link = (
    TechnicalLink(bidding_zone=BiddingZone.SE3)
    .resource("REG-OBJ-SE-001", coding_scheme="A01")  # EIC
    .add_mtu(
        mtu="2026-03-21T10:00Z",
        direction=Direction.UP,
        volume_mw=25,
        price_eur=90.00,
        product_type=MarketProductType.SCHEDULED_AND_DIRECT,
    )
    .add_mtu(
        mtu="2026-03-21T10:15Z",
        direction=Direction.UP,
        volume_mw=25,
        price_eur=90.00,
        product_type=MarketProductType.SCHEDULED_AND_DIRECT,
    )
    .add_mtu(
        mtu="2026-03-21T10:30Z",
        direction=Direction.UP,
        volume_mw=25,
        price_eur=90.00,
        product_type=MarketProductType.SCHEDULED_AND_DIRECT,
    )
    .build()
)
```

### Build conditional links

Conditional linking adjusts bid availability in QH0 based on activation outcomes in QH-1 or QH-2.

```python
from nexa_mfrr_eam import ConditionalStatus

# "Make my bid in 10:30 unavailable if the linked bid in 10:15 was activated"
bid_qh_minus_1 = (
    Bid.up(volume_mw=30, price_eur=70.00)
    .divisible(min_volume_mw=5)
    .for_mtu("2026-03-21T10:15Z")
    .resource("NOKG90901", coding_scheme="NNO")
    .build()
)

bid_qh_0 = (
    Bid.up(volume_mw=30, price_eur=70.00)
    .divisible(min_volume_mw=5)
    .for_mtu("2026-03-21T10:30Z")
    .resource("NOKG90901", coding_scheme="NNO")
    .conditionally_available()  # A65
    .link_to(bid_qh_minus_1, status=ConditionalStatus.NOT_AVAILABLE_IF_ACTIVATED)  # A55
    .build()
)
```

### National attributes: maximum duration and resting time

```python
from nexa_mfrr_eam import TechnicalLink, Direction

# A hydro unit that can only run for 90 minutes and needs 60 minutes rest
link = (
    TechnicalLink(bidding_zone=BiddingZone.NO2)
    .resource("NOKG-HYDRO-01", coding_scheme="NNO")
    .max_duration(minutes=90)
    .resting_time(minutes=60)
    .add_mtu("2026-03-21T10:00Z", Direction.UP, 40, 55.00)
    .add_mtu("2026-03-21T10:15Z", Direction.UP, 40, 55.00)
    .add_mtu("2026-03-21T10:30Z", Direction.UP, 40, 55.00)
    .add_mtu("2026-03-21T10:45Z", Direction.UP, 40, 55.00)
    .add_mtu("2026-03-21T11:00Z", Direction.UP, 40, 55.00)
    .add_mtu("2026-03-21T11:15Z", Direction.UP, 40, 55.00)
    .build()
)
```

### Build a bid portfolio from a Pandas DataFrame

> **Not yet implemented.** `bids_from_dataframe` is planned in `pandas.py`.

```python
import pandas as pd
from nexa_mfrr_eam.pandas import bids_from_dataframe

df = pd.DataFrame({
    "mtu_start":  pd.to_datetime(["2026-03-21T10:00Z", "2026-03-21T10:15Z", "2026-03-21T10:30Z"]),
    "direction":  ["up", "up", "up"],
    "volume_mw":  [50, 45, 55],
    "price_eur":  [72.30, 74.10, 69.50],
    "min_volume":  [10, 10, 10],
    "resource":   ["NOKG90901"] * 3,
})

bids = bids_from_dataframe(
    df,
    bidding_zone=BiddingZone.NO2,
    resource_coding_scheme="NNO",
    product_type=MarketProductType.SCHEDULED_AND_DIRECT,
    technical_link=True,
)

doc = (
    BidDocument(tso=TSO.STATNETT)
    .sender(party_id="9999909919920", coding_scheme="A10")
    .add_bids(bids)
    .build()
)
```

### MARI mode toggle

Product characteristics change when connecting to MARI. Toggle this globally or per-validation:

```python
from nexa_mfrr_eam import MARIMode, configure

# Set globally
configure(mari_mode=MARIMode.POST_MARI)

# Or per-validation
errors = doc.validate(mari_mode=MARIMode.POST_MARI)

# Key differences:
# - BSP GCT moves from QH-45 to QH-25
# - Max price moves from 10,000 to 15,000 EUR/MWh (later 99,999)
# - Timing changes for TSO GCT, AOF run, etc.
```

## Timing and DX helpers

### Gate closure calculator

```python
from nexa_mfrr_eam.timing import gate_closure, MARIMode

# When do I need to submit bids for a given MTU?
mtu_start = datetime(2026, 3, 21, 10, 0, tzinfo=timezone.utc)

gc = gate_closure(mtu_start, mari_mode=MARIMode.PRE_MARI)
print(f"BSP GCT (BEGCT): {gc.bsp_gct}")        # 09:15:00 UTC (QH-45)
print(f"TSO GCT: {gc.tso_gct}")                  # 09:45:00 UTC (QH-15)
print(f"Is gate open now? {gc.is_gate_open()}")

gc_mari = gate_closure(mtu_start, mari_mode=MARIMode.POST_MARI)
print(f"BSP GCT (MARI): {gc_mari.bsp_gct}")     # 09:35:00 UTC (QH-25)
```

### MTU boundaries

```python
from nexa_mfrr_eam.timing import current_mtu, mtu_range

now = datetime.now(timezone.utc)
mtu = current_mtu(now)
print(f"Current MTU: {mtu.start} to {mtu.end}")

# Generate MTU start times for a date range
mtus = mtu_range("2026-03-21T00:00Z", "2026-03-22T00:00Z")
print(f"MTUs in day: {len(mtus)}")  # 96

# DST-aware: handles 23-hour and 25-hour days
mtus_short = mtu_range("2026-03-29T00:00Z", "2026-03-30T00:00Z", tz="CET")
print(f"MTUs on DST transition day: {len(mtus_short)}")  # 92
```

### Bid document size checker

The max is 4000 time series per message (2000 for Fingrid) and 100 messages per MTU:

```python
from nexa_mfrr_eam import BidDocument

doc = (
    BidDocument(tso=TSO.STATNETT)
    .sender(party_id="9999909919920", coding_scheme="A10")
    .add_bids(my_large_bid_list)
    .build()
)

print(f"Bids in document: {doc.time_series_count}")
errors = doc.validate(mari_mode=MARIMode.PRE_MARI)
# errors will include a message if the TSO limit is exceeded
```

## Schema notes

The library targets the IEC 62325-451-7 ReserveBid schema. Three schema versions are accepted by Statnett's test environment:

| Version | Namespace | Element style |
|---|---|---|
| NBM v7.2 | `urn:iec62325:ediel:nbm:reservebiddocument:7:2` | Short names (`quantity_Measure_Unit.name`) |
| IEC v7.2 | `urn:iec62325.351:tc57wg16:451-7:reservebiddocument:7:2` | Short names |
| IEC v7.4 | `urn:iec62325.351:tc57wg16:451-7:reservebiddocument:7:4` | Long names (`quantity_Measurement_Unit.name`) |

v7.4 adds `mktPSRType.psrType` natively and is required for inclusive bid validation on Statnett. The library defaults to v7.4 for serialization and accepts all three during deserialization.

The `status` element is nested: `<status><value>A06</value></status>`. All party/area/resource IDs carry a required `codingScheme` attribute.

Denmark uses a schema variant with additional elements (`mktPSRType.psrType` mandatory, `Note` optional) not present in the v7.2 XSDs.

## TSO-specific feature matrix

| Feature | Statnett (NO) | Fingrid (FI) | Energinet (DK) | Svenska kraftnat (SE) |
|---|---|---|---|---|
| Min bid volume | 10 MW (5-9 MW exception) | 1 MW | 1 MW | 1 MW |
| Exclusive groups | Yes | Yes | Yes | Yes |
| Inclusive groups | Yes | Yes | No | No |
| Multipart bids | Yes | Yes | Yes | Yes |
| Technical linking | Yes | Yes | Yes | Yes |
| Conditional linking | Yes (incl. Z04 for period shift) | Yes (incl. inclusive bids) | Yes (no A71/A72) | Yes |
| Max duration | Yes | No | Yes | Yes |
| Resting time | Yes | No | Yes | Yes |
| Period shift | Yes | No | No | No |
| Faster activation | Yes | No | No | No |
| Non-standard (mFRR-D) | Yes | No | No | No |
| Non-standard (other) | Yes | No | No | Yes (overbelastning) |
| Change product type | A05 <-> A07 | A05 <-> A07 | No | A05 <-> A07 |
| Cut-off time for msgs | 15 min | None specified | None specified | 6 min |
| Sender coding scheme | A01, A10 | A01, A10 | A01, A10 | A01, A10, NSE |
| Resource coding scheme | NNO | A01 | A01 | A01, NSE |
| Max bids per message | 4000 | 2000 | 4000 | 4000 |
| Fallback portal | FiftyWeb | Vaksi Web | BRP Self Service Portal | FiftyWeb |

## ECP/EDX setup

This library generates CIM XML documents. To send them, you need an ECP/EDX endpoint deployed in the Nordic Energy Messaging (NEM) network. See [docs/BID_SUBMISSION.md](docs/BID_SUBMISSION.md) for the full connection and submission routine, including ECP message types, service codes, and MADES transport details.

The short version:

1. **Register as a BSP** with your connecting TSO
2. **Deploy an ECP endpoint** (Docker images from ENTSO-E Docker Hub)
3. **Configure message paths** from [ediel.org](https://ediel.org/nordic-ecp-edx-group-nex/)
4. **Test in NEM-TEST/PREPROD** before production

```python
from nexa_mfrr_eam import BidDocument, TSO

doc = BidDocument(tso=TSO.STATNETT).sender(party_id="...", coding_scheme="A10").add_bid(bid).build()
xml_bytes = doc.to_xml()

# Send xml_bytes via your ECP endpoint (FSSF, AMQP, or MADES SOAP)
```

## Bidding zone EIC codes

The library maps these automatically, but for reference:

| Zone | EIC Code | Country |
|---|---|---|
| NO1 | 10YNO-1--------2 | Norway |
| NO2 | 10YNO-2--------T | Norway |
| NO3 | 10YNO-3--------J | Norway |
| NO4 | 10YNO-4--------9 | Norway |
| NO5 | 10Y1001A1001A48H | Norway |
| SE1 | 10Y1001A1001A44P | Sweden |
| SE2 | 10Y1001A1001A45N | Sweden |
| SE3 | 10Y1001A1001A46L | Sweden |
| SE4 | 10Y1001A1001A47J | Sweden |
| DK1 | 10YDK-1--------W | Denmark |
| DK2 | 10YDK-2--------M | Denmark |
| FI | 10YFI-1--------U | Finland |

Control area EIC codes (document-level `domain.mRID`): Energinet `10Y1001A1001A796`, Fingrid `10YFI-1--------U`, Statnett `10YNO-0--------C`, SVK `10YSE-1--------K`.

Nordic Market Area (bid-level `acquiring_Domain.mRID`): `10Y1001A1001A91G`.

TSO receiver EIC codes (`receiver_MarketParticipant.mRID`): Statnett `10X1001A1001A38Y`, Fingrid `10X1001A1001A264`, Energinet `10X1001A1001A248`, SVK `10X1001A1001A418`.

## Project structure

```
nexa-mfrr-nordic-eam/
  docs/
    BID_SUBMISSION.md          # Connection and bid submission routine
  examples/
    statnett_bid_preparation.ipynb
    svk_linked_bids.ipynb
    energinet_simple_bids.ipynb
    energinet_complex_bids.ipynb
    fingrid_bids_and_deserialization.ipynb
    fingrid_xml_roundtrip.ipynb
    gs_tax_pricing.ipynb
    technical_link_ordering.ipynb
    data/
  src/nexa_mfrr_eam/
    __init__.py              # Public API re-exports
    types.py                 # Enums, Pydantic models
    config.py                # MARI mode, TSO configuration
    exceptions.py            # Typed exceptions
    bids/
      __init__.py
      simple.py              # Simple bid builder
      complex.py             # Exclusive, inclusive, multipart builders
      linked.py              # Technical and conditional link builders
      validation.py          # Common + TSO-specific validation
    documents/
      __init__.py
      reserve_bid.py         # ReserveBid_MarketDocument builder + serializer
      acknowledgement.py     # Acknowledgement_MarketDocument parser
    xml/
      __init__.py
      namespaces.py          # Namespace URIs, version-aware element mapping
      serialize.py           # Pydantic models -> CIM XML
      deserialize.py         # CIM XML -> Pydantic models
      schemas/               # Vendored XSD files (v7.2, v7.4)
    tso/
      __init__.py
      base.py                # Base TSO configuration
      energinet.py           # DK-specific rules
      fingrid.py             # FI-specific rules
      statnett.py            # NO-specific rules
      svk.py                 # SE-specific rules
    timing.py                # MTU calc, gate closures, DST
    pricing.py               # GS tax (grunnrenteskatt) price adjustment
    link_ordering.py         # Technical link ordering per PowerDesk convention
    pandas.py                # DataFrame -> Bid conversion
  tests/
    conftest.py
    fixtures/                # Example XML files
    test_bids.py
    test_complex.py
    test_config.py
    test_documents.py
    test_link_ordering.py
    test_linked.py
    test_pricing.py
    test_timing.py
    test_tso_fingrid.py
    test_xml_deserialize.py
    test_xml_serialize.py
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Issues and PRs welcome.

This project follows trunk-based development with a protected main branch and squash-only merges.

## License

MIT

## Links

- [mFRR EAM Implementation Guide (nordicbalancingmodel.net)](https://nordicbalancingmodel.net/implementation-guides/)
- [Fifty integration portal (BSP testing)](https://integration.fifty.eu)
- [ENTSO-E ECCo SP / ECP](https://www.entsoe.eu/ecco-sp/)
- [Nordic ECP/EDX Group (NEX) at ediel.org](https://ediel.org/nordic-ecp-edx-group-nex/)
- [ENTSO-E EIC Code Registry](https://www.entsoe.eu/data/energy-identification-codes-eic/)
- [MARI - Manually Activated Reserves Initiative](https://www.entsoe.eu/network_codes/eb/mari/)