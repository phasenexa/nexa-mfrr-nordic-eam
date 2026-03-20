# nexa-mfrr-nordic-eam

Python library for submitting mFRR energy activation market bids to the Nordic TSOs (Statnett, Fingrid, Energinet, Svenska kraftnat).

Built for the 75% who connect via API and build their own.

## What this does

This library handles the full BSP workflow for the Nordic mFRR energy activation market:

- **Build bids** - Simple, complex (exclusive, inclusive, multipart), and linked (technical, conditional) bids with full attribute support
- **Validate before you send** - TSO-specific and common validation rules, pre-MARI and post-MARI
- **Serialize to CIM XML** - Generates compliant `ReserveBid_MarketDocument` XML (IEC 62325-451-7 v7.4)
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

### Submit a simple divisible bid to Statnett

```python
from datetime import datetime, timezone
from nexa_mfrr import (
    Bid, BidDocument, Direction, MarketProductType,
    BiddingZone, TSO, MARIMode,
)

# Create a simple divisible up-regulation bid
bid = (
    Bid.up(volume_mw=50, price_eur=85.50)
    .divisible(min_volume_mw=10)
    .for_mtu("2026-03-21T10:00Z")
    .resource("NOKG-1234")  # Statnett regulation object code
    .product_type(MarketProductType.SCHEDULED_AND_DIRECT)  # A07
    .build()
)

# Wrap in a document targeting Statnett
doc = (
    BidDocument(tso=TSO.STATNETT)
    .sender(eic="10X1234567890123")  # Your BSP EIC code
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
from nexa_mfrr import MultipartGroup

group = (
    MultipartGroup.up(bidding_zone=BiddingZone.NO1)
    .for_mtu("2026-03-21T10:00Z")
    .resource("NOKG-1234")
    .add_component(volume_mw=20, price_eur=50.00)
    .add_component(volume_mw=15, price_eur=75.00)
    .add_component(volume_mw=10, price_eur=120.00)
    .build()
)

doc = (
    BidDocument(tso=TSO.STATNETT)
    .sender(eic="10X1234567890123")
    .add_group(group)
    .build()
)
```

### Build an exclusive group

Only one bid in the group can be activated. Useful when you have alternative resources that cannot run simultaneously.

```python
from nexa_mfrr import ExclusiveGroup

group = (
    ExclusiveGroup(bidding_zone=BiddingZone.NO1)
    .for_mtu("2026-03-21T10:00Z")
    .add_bid(
        Bid.up(volume_mw=30, price_eur=60.00)
        .indivisible()
        .resource("NOKG-1234")
    )
    .add_bid(
        Bid.up(volume_mw=50, price_eur=80.00)
        .divisible(min_volume_mw=10)
        .resource("NOKG-5678")
    )
    .product_type(MarketProductType.SCHEDULED_ONLY)
    .build()
)
```

### Build technically linked bids across MTUs

Technical linking ensures a resource is not double-activated when a bid in one MTU is activated via direct activation and is still ramping during the next MTU.

```python
from nexa_mfrr import TechnicalLink

link = (
    TechnicalLink(bidding_zone=BiddingZone.SE3)
    .resource("REG-OBJ-SE-001")
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
from nexa_mfrr import ConditionalLink, ConditionalStatus

# "Make my bid in 10:30 unavailable if the linked bid in 10:15 was activated"
bid_qh_minus_1 = (
    Bid.up(volume_mw=30, price_eur=70.00)
    .divisible(min_volume_mw=5)
    .for_mtu("2026-03-21T10:15Z")
    .resource("NOKG-1234")
    .build()
)

bid_qh_0 = (
    Bid.up(volume_mw=30, price_eur=70.00)
    .divisible(min_volume_mw=5)
    .for_mtu("2026-03-21T10:30Z")
    .resource("NOKG-1234")
    .conditionally_available()  # A65
    .link_to(bid_qh_minus_1, status=ConditionalStatus.NOT_AVAILABLE_IF_ACTIVATED)  # A55
    .build()
)
```

### National attributes: Statnett period shift

```python
from nexa_mfrr import PeriodShiftPosition

# Standard product bid that can also be used for period shift
bid = (
    Bid.up(volume_mw=20, price_eur=65.00)
    .indivisible()
    .for_mtu("2026-03-21T10:00Z")
    .resource("NOKG-1234")
    .period_shift(PeriodShiftPosition.END_OF_PERIOD)  # Z65
    .build()
)

# Period-shift-only bid (no standard product participation)
ps_bid = (
    Bid.up(volume_mw=15)  # No price for period shift only
    .indivisible()
    .for_mtu("2026-03-21T10:00Z")
    .resource("NOKG-1234")
    .product_type(MarketProductType.PERIOD_SHIFT_ONLY)  # Z01
    .build()
)
```

### National attributes: maximum duration and resting time

```python
# A hydro unit that can only run for 90 minutes and needs 60 minutes rest
link = (
    TechnicalLink(bidding_zone=BiddingZone.NO1)
    .resource("NOKG-HYDRO-01")
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
    .resource("NOKG-BATT-01")
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
    .resource("DK1-RES-001")
    .product_type(MarketProductType.SCHEDULED_AND_DIRECT)
    .build()
)

# Linked bid for next QH (can have different price/volume)
next_qh_bid = (
    Bid.up(volume_mw=30, price_eur=95.00)
    .divisible(min_volume_mw=5)
    .for_mtu("2026-03-21T10:15Z")
    .resource("DK1-RES-001")
    .product_type(MarketProductType.SCHEDULED_AND_DIRECT)
    .build()
)

# Technical link ensures next_qh_bid activates if da_bid is direct-activated
link = TechnicalLink.from_bids([da_bid, next_qh_bid], bidding_zone=BiddingZone.DK1)
```

### Statnett non-standard bids: mFRR-D (disturbance reserve)

```python
from nexa_mfrr import NonStandardType

link = (
    TechnicalLink(bidding_zone=BiddingZone.NO1)
    .resource("NOKG-DFR-01")
    .non_standard(NonStandardType.DISTURBANCE_RESERVE)  # Z74
    .add_mtu("2026-03-21T10:00Z", Direction.UP, 100, 45.00)
    .add_mtu("2026-03-21T10:15Z", Direction.UP, 100, 45.00)
    .build()
)
```

### Build a bid portfolio from a Pandas DataFrame

```python
import pandas as pd
from nexa_mfrr.pandas import bids_from_dataframe

df = pd.DataFrame({
    "mtu_start":  pd.to_datetime(["2026-03-21T10:00Z", "2026-03-21T10:15Z", "2026-03-21T10:30Z"]),
    "direction":  ["up", "up", "up"],
    "volume_mw":  [50, 45, 55],
    "price_eur":  [72.30, 74.10, 69.50],
    "min_volume":  [10, 10, 10],
    "resource":   ["NOKG-1234"] * 3,
})

bids = bids_from_dataframe(
    df,
    bidding_zone=BiddingZone.NO1,
    product_type=MarketProductType.SCHEDULED_AND_DIRECT,
    # Automatically creates a technical link across consecutive MTUs
    technical_link=True,
)

doc = (
    BidDocument(tso=TSO.STATNETT)
    .sender(eic="10X1234567890123")
    .add_bids(bids)
    .build()
)
```

### Handling activation orders

```python
from nexa_mfrr import ActivationDocument, ActivationResponse

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
from nexa_mfrr import AllocationResult

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
from nexa_mfrr import MARIMode, configure

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
from nexa_mfrr.timing import gate_closure, mtu_boundaries, MARIMode

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
from nexa_mfrr.timing import current_mtu, next_mtu, mtu_range

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
from nexa_mfrr.timing import evaluate_conditional_availability

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

The max is 4000 time series per message and 100 messages per MTU. This helper warns you before you hit limits:

```python
from nexa_mfrr import BidDocument

doc = BidDocument(tso=TSO.STATNETT).sender(eic="10X123...")
for bid in my_large_bid_list:
    doc.add_bid(bid)

# Check if we need to split
if doc.time_series_count > 4000:
    documents = doc.split()  # Auto-splits into multiple documents
    for d in documents:
        xml = d.build().to_xml()
        # Send each via ECP
```

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
| Fallback portal | FiftyWeb | Vaksi Web | BRP Self Service Portal | FiftyWeb |

## ECP/EDX setup

This library generates the CIM XML documents. To actually send them, you need an ECP/EDX endpoint deployed in the Nordic Energy Messaging (NEM) network.

**This is infrastructure you must set up with your TSO.** The process is:

1. **Register as a BSP** with your connecting TSO (Statnett, Fingrid, Energinet, or Svenska kraftnat)
2. **Request ECP/EDX documentation** from your TSO - the implementation guide for ECP can be requested directly
3. **Deploy an ECP endpoint** - this is ENTSO-E software, available as Docker images from the ENTSO-E Docker Hub
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
from nexa_mfrr import BidDocument, TSO

doc = BidDocument(tso=TSO.STATNETT).sender(eic="10X...").add_bid(bid).build()
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

Control area EIC codes (used in document headers):

| TSO | Control Area EIC |
|---|---|
| Energinet | 10Y1001A1001A796 |
| Fingrid | 10YFI-1--------U |
| Statnett | 10YNO-0--------C |
| Svenska kraftnat | 10YSE-1--------K |

Nordic Market Area: `10Y1001A1001A91G`

## What you need that this library cannot provide

The following information is **not publicly documented** in the mFRR EAM implementation guide and must be obtained directly from your connecting TSO:

1. **ECP/EDX endpoint setup credentials and certificates** - your TSO issues registration keystores and passwords
2. **ECP endpoint URLs / broker addresses** - provided per TSO during onboarding, not published
3. **Test environment access** - NEM-TEST/PREPROD endpoints, separate from production
4. **Your BSP EIC code** - issued through the ENTSO-E EIC code registry, or national equivalent
5. **Resource object codes** - Statnett uses NOKG/NOG codes; other TSOs use EIC or national identifiers
6. **Denmark's specific ReserveBid schema version** - the implementation guide notes Denmark uses a specific version; request from Energinet
7. **NMEG additional code lists** - referenced in the implementation guide but not included; request from your TSO
8. **Service codes for mFRR EAM on ECP** - the addressing convention (e.g. `SERVICE-<code>`) for mFRR EAM specifically
9. **National Terms and Conditions** - each TSO publishes specific T&Cs that BSPs must comply with
10. **Fingrid IP whitelisting requirements** - Fingrid only allows Nordic IPs plus Azure West Europe; contact them if your endpoint is elsewhere

Example XML messages are referenced as available at [nordicbalancingmodel.net](https://nordicbalancingmodel.net/implementation-guides/) but are separate downloads.

## Project structure

```
nexa-mfrr-nordic-eam/
  src/nexa_mfrr/
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