# CLAUDE.md - nexa-mfrr-nordic-eam

## What this project is

A Python library for building, validating, and serializing mFRR energy activation market (EAM) bids for the four Nordic TSOs: Statnett (Norway), Fingrid (Finland), Energinet (Denmark), and Svenska kraftnat (Sweden). The library also parses TSO response documents (acknowledgements, activation orders, bid availability reports, allocation results).

The target users are BSP (Balancing Service Provider) developers who connect to the mFRR EAM via ECP/EDX and build their own trading infrastructure. The library does NOT manage ECP/EDX connectivity itself - it produces and consumes the CIM XML documents that travel over ECP.

## Domain context

The mFRR EAM went live on 4 March 2025 as part of the Nordic Balancing Model (NBM). It operates on 15-minute Market Time Units (MTUs). There are 96 MTUs per day. BSPs submit bids to their connecting TSO, the TSO filters and forwards bids to the Activation Optimization Function (AOF), which selects bids for activation. Activation orders are sent back to BSPs via CIM XML documents over ECP.

The market will transition to the European MARI platform at a later date. This changes timing parameters, price limits, and some validation rules. The library must support both pre-MARI and post-MARI configurations via a toggle.

### Key timing (pre-MARI)
- BSP GCT (gate closure): QH-45 (45 minutes before the quarter-hour)
- TSO GCT: QH-15
- AOF run: QH-14
- Activation orders sent to BSPs: QH-7.5

### Key timing (post-MARI)
- BSP GCT: QH-25
- TSO GCT: QH-12
- AOF run: QH-10
- Activation orders: QH-7.5 (unchanged)

### Price limits
- Pre-MARI: -10,000 to +10,000 EUR/MWh
- Post-MARI: -15,000 to +15,000 EUR/MWh (later -99,999 to +99,999)
- Granularity: 0.01 EUR

### Volume limits
- Min bid: 1 MW (except Statnett: 10 MW, with 5-9 MW exception for one bid per resource/direction/MTU)
- Max bid: 9,999 MW (technical limit)
- Granularity: 1 MW
- Activation granularity: 1 MW (0.1 MW for pro-rata at Statnett and SVK)

## Architecture

### Module layout

- `types.py` - All enums and Pydantic models. This is imported by everything. No external API dependencies.
- `config.py` - Global configuration: MARI mode toggle, default TSO settings.
- `exceptions.py` - Typed exception hierarchy. All exceptions inherit from `NexaMFRRError`.
- `bids/` - Bid builders using a fluent API pattern. `simple.py` for simple bids, `complex.py` for exclusive/inclusive/multipart groups, `linked.py` for technical and conditional links, `validation.py` for all validation rules.
- `documents/` - One module per CIM document type. Each has a builder (for outgoing docs) and parser (for incoming docs). Uses Pydantic models internally.
- `xml/` - Serialization and deserialization between Pydantic models and IEC CIM XML. Uses `lxml` for XML generation. XSD schemas vendored in `xml/schemas/`.
- `tso/` - TSO-specific configuration and validation overrides. Each TSO module defines which national attributes are supported, specific validation rules, heartbeat behaviour, and any schema deviations.
- `timing.py` - Pure functions for MTU calculations, gate closure times, DST handling, MARI timing differences.
- `heartbeat.py` - Heartbeat detection (checks for ACTIVATION_HEARTBEAT time series) and response generation.
- `pandas.py` - Optional module (guarded import). Converts DataFrames to bid objects.

### Key design decisions

1. **Fluent builder API** - Bids are constructed via method chaining. This is the public API surface. Internally, builders produce Pydantic models.
2. **Pydantic for all data models** - Every bid, document, time series, etc. is a Pydantic BaseModel. Validation happens at the model level (structural) and at the document level (business rules).
3. **TSO as strategy pattern** - Each TSO module provides a configuration object that the validation and serialization layers consume. No if/else chains on TSO name.
4. **MARI mode as enum** - `MARIMode.PRE_MARI` and `MARIMode.POST_MARI`. Affects validation rules, timing calculations, and price limits. Can be set globally or passed per-call.
5. **Immutable after build** - Once `.build()` is called, the resulting object is frozen. Modifications require creating a new builder.
6. **UUIDs generated automatically** - Document mRIDs, bid mRIDs, link IDs are all auto-generated as UUID v4 unless explicitly provided.

### CIM XML documents

All documents follow IEC 62325-451-7. The key documents:

| Document | Direction | Schema | Purpose |
|---|---|---|---|
| ReserveBid_MarketDocument | BSP -> TSO | v7.4 | Submit/update/cancel bids |
| Activation_MarketDocument | TSO -> BSP | v6.2 | Activation orders (incl. heartbeat) |
| Activation_MarketDocument | BSP -> TSO | v6.2 | Activation response |
| BidAvailability_MarketDocument | TSO -> BSP | v1.1 | Bid availability reports |
| ReserveAllocationResult_MarketDocument | TSO -> BSP | v6.4 | Activation settlement results |
| Acknowledgement_MarketDocument | Both | v8.1 | ACK/NACK for any document |

### XML serialization rules

- All datetimes in UTC, ISO 8601: `YYYY-MM-DDTHH:MM:SSZ`
- Time intervals: `Start: YYYY-MM-DDTHH:MMZ / End: YYYY-MM-DDTHH:MMZ`
- Duration format: ISO 8601 duration, e.g. `PT15M`, `PT45M`, `PT3M`
- Document mRID: UUID v4
- Revision number: always `1`
- Namespace: use the IEC namespace for each document type
- Currency: always `EUR`
- Measurement unit: `MAW` (megawatt) for quantity, `MWH` for energy price

## Bid types reference

### Simple bids
- One price, one volume, one MTU (15 min period)
- Divisible (A01) with optional minimum volume, or indivisible (A02)
- Market product type: A05 (scheduled only), A07 (scheduled + direct), A02 (non-standard), Z01 (period shift only)

### Complex bids (groups of simple bids for same MTU)
- **Exclusive group**: only one bid can be activated. All must have same product type, period, bidding zone. Cannot be part of multipart or inclusive.
- **Inclusive group** (NO, FI only): if one activates, all must activate. All must have same price, direction, product type, period, zone. Cannot be part of exclusive or multipart.
- **Multipart**: multiple price levels. All must have different prices, same direction, product type, period, zone. Cannot be part of exclusive or inclusive.

### Linked bids (across MTUs)
- **Technical link**: prevents double-activation across consecutive QHs. Works for both simple and complex bids. All components must share the same link ID within an MTU.
- **Conditional link**: adjusts availability in QH0 based on activation outcome in QH-1/QH-2. Only for simple bids (except Statnett Z04 for period shift, Fingrid for inclusive bids). Max 3 links to QH-1 and 3 to QH-2.

## TSO-specific implementation notes

### Energinet (Denmark)
- BRP acts as BSP (use A46 role regardless)
- No heartbeat
- Only scheduled activation type allowed (no direct) until MARI
- Local direct activation model: DA bid + linked bid in next QH are separate, can have different price/volume
- Cannot change market product type on update (must cancel + resubmit)
- `mktPSRType.psrType` is mandatory (production type: B16 solar, B18 wind offshore, B19 wind onshore, B20 other)
- `Note` attribute available for BRP custom text (passed through to activation document)
- Conditional bid types A71 and A72 not supported
- Uses a specific schema version for ReserveBid - check with Energinet
- Activation response must be within 2 min; late responses rejected with negative ACK
- BSP NOT accountable if "Unavailable" response accepted within time limit

### Fingrid (Finland)
- No heartbeat
- BEGOT is 30 days
- Max 2000 bids per message
- Supports inclusive bids (used for aggregated bids, same proportion selected)
- Conditional linking allowed for inclusive bids (special rules - see implementation guide section 4.2)
- Voluntary secondary bid ID via Reason element (code A95)
- Can change product type between A05 and A07
- Rounds partial activation volumes to next full MW (or 0.1 MW for aggregated)
- Activation response: BSP accountable regardless of response

### Statnett (Norway)
- Richest feature set: period shift, faster activation, mFRR-D, other non-standard, inclusive bids
- Min bid 10 MW (exception: one bid 5-9 MW per resource/direction/MTU)
- 15-minute cut-off: bid documents older than 15 min silently dropped (no NACK)
- Heartbeat at T-12, T-7.5 (if no activation), T-3
- Missing heartbeat response: bids set unavailable for upcoming MTUs (see table in impl guide 4.3.2)
- Period shift: Z64 (beginning), Z65 (end) via Reason element. Conditional linking with Z04 status.
- Period shift only bids: product type Z01, must be indivisible, no price
- Faster activation: specify FAT including 1 min prep time (e.g. PT3M for 2 min ramp)
- Deactivation: TSO sends updated activation with earlier end time, same order ID
- Non-standard bids (A02): mFRR-D (Z74) and Other (Z83), must be simple technically-linked
- Can change product type between A05 and A07
- Activation response: BSP accountable regardless of response

### Svenska kraftnat (Sweden)
- 6-minute cut-off: bid documents older than 6 min silently dropped
- Heartbeat every 5 minutes (xx:02, xx:07, xx:12, ...)
- Missing heartbeat: bids unavailable for upcoming 2 quarters
- Overbelastningshantering vid storning (non-standard A02): reason code Z74, indivisible, technically linked, must have activation time specified
- No electronic ordering for non-standard; activated by phone
- BSP can split activation response into multiple messages
- BSP must validate activation timeseries mRID against previously submitted bids
- Can change product type between A05 and A07
- Activation response: BSP accountable regardless of response

## Build and test

```bash
make install    # Install dev dependencies
make test       # Run pytest
make lint       # Run ruff
make typecheck  # Run mypy
make ci         # Run all checks (lint + typecheck + test)
```

### Test fixtures

Example XML messages should be placed in `tests/fixtures/`. Use VCR cassettes where applicable. The nordicbalancingmodel.net site has example messages available for download.

### Test strategy

- Unit tests for all bid builders (simple, complex, linked)
- Unit tests for validation rules (common + per-TSO)
- Unit tests for XML serialization round-trips (build -> serialize -> deserialize -> compare)
- Unit tests for timing calculations (MTU boundaries, gate closures, DST transitions)
- Unit tests for heartbeat detection and response
- Integration tests with example XML from nordicbalancingmodel.net

## Style and conventions

- Python 3.11+
- Pydantic v2 for all models
- lxml for XML generation and parsing
- ruff for linting and formatting
- mypy for type checking (strict mode)
- pytest for testing
- All public API types re-exported from `__init__.py`
- Docstrings on all public classes and methods (Google style)
- No abbreviations in public API names except well-known domain terms (MTU, BSP, TSO, EIC, mFRR, etc.)
- Use `datetime` with timezone-aware UTC throughout. Never use naive datetimes.
- All XML element names and CIM codes documented with their meaning in comments

## Implementation order

1. `types.py` - All enums (Direction, MarketProductType, BiddingZone, TSO, MARIMode, ConditionalStatus, NonStandardType, PeriodShiftPosition, ActivationType) and Pydantic models (BidModel, BidTimeSeriesModel, DocumentModel, etc.)
2. `exceptions.py` - Exception hierarchy
3. `config.py` - Global config, MARI mode
4. `timing.py` - MTU calculations, gate closures
5. `tso/base.py` + individual TSO modules - TSO configuration objects
6. `bids/simple.py` - Simple bid builder
7. `bids/complex.py` - Complex group builders
8. `bids/linked.py` - Link builders
9. `bids/validation.py` - Validation rules
10. `xml/serialize.py` - Pydantic -> XML
11. `xml/deserialize.py` - XML -> Pydantic
12. `documents/reserve_bid.py` - BidDocument builder
13. `documents/activation.py` - Activation parser + response builder
14. `documents/acknowledgement.py` - ACK parser
15. `documents/bid_availability.py` - Availability parser
16. `documents/allocation_result.py` - Allocation result parser
17. `heartbeat.py` - Heartbeat handling
18. `pandas.py` - DataFrame integration
19. `__init__.py` - Public API re-exports

## Common pitfalls

- **Denmark BRP/BSP distinction**: In Denmark, BRPs act as BSPs. Always use market role A46 (BSP) in documents.
- **Revision number is always 1**: Do not increment. Each update is a new document with a new mRID.
- **Bid mRID is permanent**: When updating a bid, use the ORIGINAL bid time series mRID. New mRID = new bid.
- **Cannot change bid from simple to complex**: Must cancel and resubmit.
- **Cannot change bid period or resource**: Must cancel and resubmit.
- **Complex bids cannot be partially cancelled**: Cancel all components, or convert to simple first.
- **Conditional links to cancelled bids become invalid**: The BSP is responsible for maintaining valid links.
- **Technical link IDs must be unique within an MTU**: Only one simple or one complex bid per link ID per MTU.
- **Period shift only bids (Z01) have no price**: The price element must be omitted.
- **Statnett/SVK cut-off times are silent**: Old messages are dropped with no NACK sent.
- **Heartbeat response with A11 (Unavailable)**: Statnett treats this as missing heartbeat.
- **DST handling**: Full day in UTC is 23:00-23:00 (winter) or 22:00-22:00 (summer). Transition days have 92 or 100 MTUs.