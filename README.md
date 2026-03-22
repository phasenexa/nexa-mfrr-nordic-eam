# nexa-mfrr-nordic-eam

[![CI](https://github.com/phasenexa/nexa-mfrr-nordic-eam/actions/workflows/ci.yml/badge.svg)](https://github.com/phasenexa/nexa-mfrr-nordic-eam/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/phasenexa/nexa-mfrr-nordic-eam/branch/main/graph/badge.svg)](https://codecov.io/gh/phasenexa/nexa-mfrr-nordic-eam)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)


> **This project is a work in progress.** The API, documentation, and feature set are under active development and subject to change. If you want to get involved, receive progress updates, or have feedback, please [open an issue](https://github.com/phasenexa/nexa-mfrr-nordic-eam/issues) or contact the repo admin.

Python library for submitting mFRR energy activation market bids to the Nordic TSOs (Statnett, Fingrid, Energinet, Svenska kraftnat).

Built for the 75% who connect via API and build their own.

## Implementation status

| Module | Status | Notes |
|---|---|---|
| `types.py` | ✅ Done | All enums + Pydantic models (BidTimeSeriesModel, BidDocumentModel, etc.) |
| `exceptions.py` | ✅ Done | NexaMFRREAMError, InvalidMTUError, NaiveDatetimeError, BidValidationError |
| `config.py` | ✅ Done | Global MARI mode, configure(), get_mari_mode() |
| `timing.py` | ✅ Done | MTU, GateClosure, gate_closure(), current_mtu(), mtu_range(), evaluate_conditional_availability() |
| `__init__.py` | ✅ Done | Public re-exports including Bid, BidDocument, BuiltBidDocument |
| `bids/simple.py` | ✅ Done | Bid factory + SimpleBidBuilder with fluent API |
| `bids/validation.py` | ✅ Done | Common + TSO-configurable validation rules |
| `bids/complex.py` | 🔲 Planned | Exclusive, inclusive, multipart group builders |
| `bids/linked.py` | 🔲 Planned | Technical and conditional link builders |
| `xml/namespaces.py` | ✅ Done | NBM and IEC namespace URI constants |
| `xml/serialize.py` | ✅ Done | Pydantic models → CIM XML (XSD-compliant element ordering) |
| `xml/deserialize.py` | 🔲 Planned | CIM XML → Pydantic models |
| `tso/base.py` | ✅ Done | TSOConfig strategy dataclass |
| `tso/statnett.py` | ✅ Done | Statnett (NO) configuration |
| `tso/fingrid.py` | 🔲 Planned | Fingrid (FI) configuration |
| `tso/energinet.py` | 🔲 Planned | Energinet (DK) configuration |
| `tso/svk.py` | 🔲 Planned | Svenska kraftnat (SE) configuration |
| `documents/reserve_bid.py` | ✅ Done | BidDocument factory + BidDocumentBuilder + BuiltBidDocument |
| `documents/activation.py` | 🔲 Planned | Activation parser + response builder |
| `documents/acknowledgement.py` | 🔲 Planned | ACK parser |
| `documents/bid_availability.py` | 🔲 Planned | Availability parser |
| `documents/allocation_result.py` | 🔲 Planned | Allocation result parser |
| `heartbeat.py` | 🔲 Planned | Heartbeat detection + response |
| `pandas.py` | 🔲 Planned | DataFrame → Bid conversion |
| `examples/` | ✅ Done | Jupyter notebook: Statnett daily bid preparation with GS tax |

## What this does

This library handles the full BSP workflow for the Nordic mFRR energy activation market:

- **Build bids** - Simple, complex (exclusive, inclusive, multipart), and linked (technical, conditional) bids with full attribute support
- **Validate before you send** - TSO-specific and common validation rules, pre-MARI and post-MARI
- **Serialize to CIM XML** - Generates compliant `ReserveBid_MarketDocument` XML per the NBM ReserveBid schema
- **Parse TSO responses** - Acknowledgements, activation orders, bid availability reports, allocation results
- **Handle activations** - Build activation response documents, track activation state
- **Heartbeat responder** - Automatic heartbeat processing for Statnett and Svenska kraftnat
- **Timing helpers** - Gate closure calculations, MTU boundaries, MARI vs pre-MARI timing
- **Pandas integration** - Build bid portfolios from DataFrames

What it does **not** do: manage your ECP/EDX endpoint. That is infrastructure you deploy and operate separately (see [ECP/EDX Setup](#ecpedx-setup) below). This library generates the XML documents you send through your endpoint.

## Installation

```bash
pip install nexa-mfrr-nordic-eam
```

With Pandas support:

```bash
pip install nexa-mfrr-nordic-eam[pandas]
```

## Quick start

> **Note:** Only the simple bid builder, document builder, serializer, and timing helpers are currently implemented. The examples for complex bids, linked bids, activation parsing, and Pandas integration show the intended API and will work once those modules are complete.

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
from nexa_mfrr_eam import MultipartGroup

group = (
    MultipartGroup.up(bidding_zone=BiddingZone.NO2)
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
    .add_group(group)
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

### National attributes: Statnett period shift

```python
from nexa_mfrr_eam import PeriodShiftPosition

# Standard product bid that can also be used for period shift
bid = (
    Bid.up(volume_mw=20, price_eur=65.00)
    .indivisible()
    .for_mtu("2026-03-21T10:00Z")
    .resource("NOKG90901", coding_scheme="NNO")
    .period_shift(PeriodShiftPosition.END_OF_PERIOD)  # Z65
    .build()
)

# Period-shift-only bid (no standard product participation)
ps_bid = (
    Bid.up(volume_mw=15)  # No price for period shift only
    .indivisible()
    .for_mtu("2026-03-21T10:00Z")
    .resource("NOKG90901", coding_scheme="NNO")
    .product_type(MarketProductType.PERIOD_SHIFT_ONLY)  # Z01
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

### National attributes: faster activation (Statnett)

```python
# A battery that can ramp in 2 minutes (FAT = 3 min including 1 min prep)
bid = (
    Bid.up(volume_mw=10, price_eur=200.00)
    .indivisible()
    .for_mtu("2026-03-21T10:00Z")
    .resource("NOKG-BATT-01", coding_scheme="NNO")
    .product_type(MarketProductType.SCHEDULED_AND_DIRECT)
    .faster_activation(minutes=3)  # PT3M
    .build()
)
```

### Energinet: direct activation (local model)

Denmark uses a different direct activation model where the DA bid and its linked bid in the next quarter are two separate bids with potentially different prices.

```python
# Direct activatable bid for current QH
da_bid = (
    Bid.up(volume_mw=25, price_eur=100.00)
    .divisible(min_volume_mw=5)
    .for_mtu("2026-03-21T10:00Z")
    .resource("DK1-RES-001", coding_scheme="A01")
    .product_type(MarketProductType.SCHEDULED_AND_DIRECT)
    .build()
)

# Linked bid for next QH (can have different price/volume)
next_qh_bid = (
    Bid.up(volume_mw=30, price_eur=95.00)
    .divisible(min_volume_mw=5)
    .for_mtu("2026-03-21T10:15Z")
    .resource("DK1-RES-001", coding_scheme="A01")
    .product_type(MarketProductType.SCHEDULED_AND_DIRECT)
    .build()
)

# Technical link ensures next_qh_bid activates if da_bid is direct-activated
link = TechnicalLink.from_bids([da_bid, next_qh_bid], bidding_zone=BiddingZone.DK1)
```

### Statnett non-standard bids: mFRR-D (disturbance reserve)

```python
from nexa_mfrr_eam import NonStandardType

link = (
    TechnicalLink(bidding_zone=BiddingZone.NO2)
    .resource("NOKG-DFR-01", coding_scheme="NNO")
    .non_standard(NonStandardType.DISTURBANCE_RESERVE)  # Z74
    .add_mtu("2026-03-21T10:00Z", Direction.UP, 100, 45.00)
    .add_mtu("2026-03-21T10:15Z", Direction.UP, 100, 45.00)
    .build()
)
```

### Build a bid portfolio from a Pandas DataFrame

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
    # Automatically creates a technical link across consecutive MTUs
    technical_link=True,
)

doc = (
    BidDocument(tso=TSO.STATNETT)
    .sender(party_id="9999909919920", coding_scheme="A10")
    .add_bids(bids)
    .build()
)
```

### Handling activation orders

```python
from nexa_mfrr_eam import ActivationDocument

# Parse the activation order XML received from your ECP endpoint
order = ActivationDocument.from_xml(activation_xml_bytes)

# Check if it is a heartbeat
if order.is_heartbeat:
    # Respond to heartbeat (required for Statnett and Svenska kraftnat)
    response = order.heartbeat_response(status="activated")
    response_xml = response.to_xml()
    # Send response_xml back via ECP
else:
    # Real activation order
    for ts in order.time_series:
        print(f"Bid {ts.bid_id}: {ts.quantity_mw} MW {ts.direction}")
        print(f"  Period: {ts.start} to {ts.end}")
        print(f"  Type: {order.activation_type}")  # scheduled, direct, period_shift, etc.

    # Build response - confirm all activations
    response = order.respond_all_activated()

    # Or selectively mark some as unavailable
    response = (
        order.build_response()
        .activate(ts.bid_id for ts in order.time_series[:2])
        .unavailable(
            order.time_series[2].bid_id,
            reason="B59",  # Unavailability of reserve providing unit
            text="Generator tripped",
        )
        .build()
    )

    response_xml = response.to_xml()
    # Send via ECP within 2 minutes
```

### Parsing allocation results

```python
from nexa_mfrr_eam import AllocationResult

result = AllocationResult.from_xml(allocation_xml_bytes)

for ts in result.time_series:
    print(f"Bid {ts.bid_id}")
    print(f"  Activated: {ts.quantity_mw} MW at {ts.price_eur} EUR/MWh")
    print(f"  Direction: {ts.direction}")
    print(f"  Reason: {ts.activation_reasons}")  # e.g. ["B49", "Z58"] = Balancing + Scheduled
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
print(f"Activation orders at: {gc.activation}")   # 09:52:30 UTC (QH-7.5)
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

### Conditional link availability evaluator

After the AOF runs, determine if your conditional bids are available:

```python
from nexa_mfrr_eam.timing import evaluate_conditional_availability

# Your bid in QH0 is conditionally available (A65) with link:
# "Not available if linked bid in QH-1 was activated" (A55)
is_available = evaluate_conditional_availability(
    bid_status="A65",  # conditionally available
    links=[
        {"linked_bid_activated": True, "condition": "A55"},
    ],
)
print(f"Bid available: {is_available}")  # False
```

### Bid document size checker

The max is 4000 time series per message and 100 messages per MTU:

```python
from nexa_mfrr_eam import BidDocument

doc = BidDocument(tso=TSO.STATNETT).sender(party_id="9999909919920", coding_scheme="A10")
for bid in my_large_bid_list:
    doc.add_bid(bid)

# Check if we need to split
if doc.time_series_count > 4000:
    documents = doc.split()  # Auto-splits into multiple documents
    for d in documents:
        xml = d.build().to_xml()
        # Send each via ECP
```

## Schema notes

The library targets the NBM (Nordic Balancing Model) variant of the IEC 62325-451-7 ReserveBid schema. There are some important details to be aware of:

**Schema versions and namespaces**: The vendored XSD uses namespace `urn:iec62325:ediel:nbm:reservebiddocument:7:2` while the Statnett example XML uses namespace `urn:iec62325.351:tc57wg16:451-7:reservebiddocument:7:2`. The implementation guide references schema version 7.4. The library handles all known namespace variants during parsing and uses the NBM namespace for serialization by default (configurable per TSO).

**Element naming**: The XSD uses `quantity_Measure_Unit.name` and `energyPrice_Measure_Unit.name` (without "ment" suffix). The implementation guide text inconsistently uses `quantity_Measurement_Unit.name`. The library follows the XSD and example XML.

**Status element structure**: In the XML, the `status` element contains a nested `<value>` element, not a flat string. For example: `<status><value>A06</value></status>`.

**Resource coding schemes**: The `registeredResource.mRID` element requires a `codingScheme` attribute. Known schemes: A01 (EIC), NNO (Norwegian national / NOKG codes), NSE (Swedish national). The Statnett example uses NNO.

**Sender/receiver coding schemes**: Supported schemes per the implementation guide section 6.6: A01 (EIC), A10 (GS1), NSE (Swedish national). The Statnett example uses A10 (GS1) for the sender.

**Denmark-specific schema**: The implementation guide notes that Denmark "currently uses a specific version of the schema." The fields `mktPSRType.psrType` (mandatory for DK) and `Note` (optional, DK only) are not present in the standard NBM XSD. Request the Denmark-specific schema from Energinet.

**Optional fields in XSD not discussed in the implementation guide**: The XSD includes several optional elements: `blockBid`, `priority`, `stepIncrementQuantity`, `validity_Period.timeInterval`, `original_MarketProduct.marketProductType`, `provider_MarketParticipant.mRID`, `price_Measure_Unit.name`, `ProcuredFor_MarketParticipant`, `SharedWith_MarketParticipant`, `ExchangedWith_MarketParticipant`, `AvailableBiddingZone_Domain`, and `marketAgreement.*`. These may be relevant for future MARI integration or capacity market cross-references.

**XSD cardinality vs implementation guide**: The XSD allows multiple `Period` elements per `BidTimeSeries` and multiple `Point` elements per `Series_Period`. The implementation guide restricts both to exactly one. The library enforces the implementation guide restriction by default.

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
| Slower activation | No | No | Yes | No |
| Non-standard (mFRR-D) | Yes | No | No | No |
| Non-standard (other) | Yes | No | No | Yes (overbelastning) |
| Heartbeat | Yes (T-12, T-7.5, T-3) | No | No | Yes (every 5 min) |
| Direct activation | Yes | Yes | Local model (separate bids) | Yes |
| Change product type | A05 <-> A07 | A05 <-> A07 | No | A05 <-> A07 |
| Cut-off time for msgs | 15 min | None specified | None specified | 6 min |
| Locational info | Yes (NOKG/NOG) | Yes (resource) | Yes (substations) | Yes |
| Voluntary bid ID | No | Yes (Reason A95) | No | No |
| Sender coding scheme | A01, A10 | A01, A10 | A01, A10 | A01, A10, NSE |
| Resource coding scheme | NNO | A01 | A01 | A01, NSE |
| Fallback portal | FiftyWeb | Vaksi Web | BRP Self Service Portal | FiftyWeb |

## ECP/EDX setup

This library generates the CIM XML documents. To actually send them, you need an ECP/EDX endpoint deployed in the Nordic Energy Messaging (NEM) network.

**This is infrastructure you must set up with your TSO.** The process is:

1. **Register as a BSP** with your connecting TSO (Statnett, Fingrid, Energinet, or Svenska kraftnat)
2. **Request ECP/EDX documentation** from your TSO
3. **Deploy an ECP endpoint** - ENTSO-E software, available as Docker images from the ENTSO-E Docker Hub
4. **Register your endpoint** with your TSO's Central Directory (CD)
5. **Configure message paths** - download from ediel.org for your TSO:
   - Statnett: https://ediel.org/nordic-ecp-edx-group-nex/nex-statnett/
   - Fingrid: https://ediel.org/nordic-ecp-edx-group-nex/fingrid/
   - Energinet: https://ediel.org/nordic-ecp-edx-group-nex/energinet/
   - Svenska kraftnat: https://ediel.org/nordic-ecp-edx-group-nex/svenska-kraftnat/
6. **Test connectivity** in NEM-TEST/PREPROD before going to NEM-PROD

ECP supports multiple integration channels: AMQP(S), MADES Web Service, and FSSF (File System Shared Folder). EDX adds SFTP, SCP, and additional web service options. Third-party managed service providers (e.g. Tietoevry's BIX EIX) can operate the endpoint on your behalf.

The NEX (Nordic ECP/EDX Group) installation guide is available at ediel.org.

### Integration pattern

```python
# Pseudocode - your actual integration depends on your ECP setup
from nexa_mfrr_eam import BidDocument, TSO

doc = BidDocument(tso=TSO.STATNETT).sender(party_id="...", coding_scheme="A10").add_bid(bid).build()
xml_bytes = doc.to_xml()

# Option 1: Write to ECP's FSSF inbox folder
Path("/ecp/outbox/").write_bytes(xml_bytes)

# Option 2: Post via AMQP to your local ECP broker
channel.basic_publish(exchange="", routing_key="ecp.outbox", body=xml_bytes)

# Option 3: Use MADES web service
# POST to your ECP endpoint's MADES interface
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

Control area EIC codes (used in document-level `domain.mRID`):

| TSO | Control Area EIC |
|---|---|
| Energinet | 10Y1001A1001A796 |
| Fingrid | 10YFI-1--------U |
| Statnett | 10YNO-0--------C |
| Svenska kraftnat | 10YSE-1--------K |

Nordic Market Area (used in bid-level `acquiring_Domain.mRID`): `10Y1001A1001A91G`

TSO receiver EIC codes (used in `receiver_MarketParticipant.mRID`):

| TSO | Receiver EIC |
|---|---|
| Statnett | 10X1001A1001A38Y |

(Other TSO receiver EICs should be confirmed with each TSO during onboarding.)

## What you need that this library cannot provide

The following information is **not publicly documented** in the mFRR EAM implementation guide and must be obtained directly from your connecting TSO:

1. **ECP/EDX endpoint setup credentials and certificates** - your TSO issues registration keystores and passwords
2. **ECP endpoint URLs / broker addresses** - provided per TSO during onboarding, not published
3. **Test environment access** - NEM-TEST/PREPROD endpoints, separate from production
4. **Your BSP party ID** - either an EIC code (A01) or GS1 number (A10), depending on TSO
5. **Resource object codes** - Statnett uses NNO coding scheme (NOKG/NOG codes); other TSOs use EIC or national identifiers
6. **Denmark's specific ReserveBid schema version** - the implementation guide notes Denmark uses a specific version; request from Energinet
7. **NMEG additional code lists** - referenced in the implementation guide but not included; request from your TSO
8. **Service codes for mFRR EAM on ECP** - the addressing convention (e.g. `SERVICE-<code>`) for mFRR EAM specifically
9. **National Terms and Conditions** - each TSO publishes specific T&Cs that BSPs must comply with
10. **Fingrid IP whitelisting requirements** - Fingrid only allows Nordic IPs plus Azure West Europe; contact them if your endpoint is elsewhere
11. **TSO receiver EIC codes** - the Statnett example uses `10X1001A1001A38Y`; confirm the others with each TSO

Example XML messages are referenced as available at [nordicbalancingmodel.net](https://nordicbalancingmodel.net/implementation-guides/) but are separate downloads.

## Project structure

```
nexa-mfrr-nordic-eam/
  src/nexa_mfrr_eam/
    __init__.py              # Public API re-exports
    types.py                 # Enums, Pydantic models for all bid types
    config.py                # MARI mode, TSO configuration
    exceptions.py            # Typed exceptions
    bids/
      __init__.py
      simple.py              # Simple bid builder
      complex.py             # Exclusive, inclusive, multipart group builders
      linked.py              # Technical and conditional link builders
      validation.py          # Common + TSO-specific validation rules
    documents/
      __init__.py
      reserve_bid.py         # ReserveBid_MarketDocument builder + serializer
      activation.py          # Activation_MarketDocument parser + response builder
      bid_availability.py    # BidAvailability_MarketDocument parser
      allocation_result.py   # ReserveAllocationResult_MarketDocument parser
      acknowledgement.py     # Acknowledgement_MarketDocument parser
    xml/
      __init__.py
      namespaces.py          # Namespace URI handling (NBM, IEC, per-TSO variants)
      serialize.py           # Pydantic models -> CIM XML
      deserialize.py         # CIM XML -> Pydantic models
      schemas/               # XSD files for validation (vendored)
    tso/
      __init__.py
      base.py                # Base TSO configuration and rules
      energinet.py           # DK-specific rules, DA model, schema version
      fingrid.py             # FI-specific rules, voluntary bid ID
      statnett.py            # NO-specific rules, period shift, mFRR-D, heartbeat
      svk.py                 # SE-specific rules, overbelastning, heartbeat
    timing.py                # MTU calc, gate closures, DST, MARI timing
    heartbeat.py             # Heartbeat detection + response generation
    pandas.py                # DataFrame -> Bid conversion utilities
  tests/
    conftest.py
    fixtures/                # VCR cassettes, example XML files
    test_bids.py
    test_complex.py
    test_linked.py
    test_validation.py
    test_documents.py
    test_timing.py
    test_pandas.py
    test_tso_specific.py
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Issues and PRs welcome.

This project follows trunk-based development with a protected main branch and squash-only merges.

## License

MIT

## Links

- [mFRR EAM Implementation Guide (nordicbalancingmodel.net)](https://nordicbalancingmodel.net/implementation-guides/)
- [ENTSO-E ECCo SP / ECP](https://www.entsoe.eu/ecco-sp/)
- [Nordic ECP/EDX Group (NEX) at ediel.org](https://ediel.org/nordic-ecp-edx-group-nex/)
- [ENTSO-E EIC Code Registry](https://www.entsoe.eu/data/energy-identification-codes-eic/)
- [MARI - Manually Activated Reserves Initiative](https://www.entsoe.eu/network_codes/eb/mari/)
