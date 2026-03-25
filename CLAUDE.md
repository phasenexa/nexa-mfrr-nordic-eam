# CLAUDE.md - nexa-mfrr-nordic-eam

## What this project is

A Python library for building, validating, and serializing mFRR energy activation market (EAM) bids for the four Nordic TSOs: Statnett (Norway), Fingrid (Finland), Energinet (Denmark), and Svenska kraftnat (Sweden). The library also parses acknowledgement documents returned by the TSOs after bid submission.

The Python package name is `nexa_mfrr_eam` (not `nexa_mfrr`) to avoid conflicts with other Phase Nexa mFRR-related packages.

The target users are BSP (Balancing Service Provider) developers who connect to the mFRR EAM via ECP/EDX and build their own trading infrastructure. The library does NOT manage ECP/EDX connectivity itself - it produces and consumes the CIM XML documents that travel over ECP.

### Scope

In scope: bid building, validation, CIM XML serialization/deserialization of ReserveBid_MarketDocument, and parsing of Acknowledgement_MarketDocument responses.

Out of scope (may be covered by separate repos): activation order handling, activation response building, heartbeat processing, bid availability reports, allocation result parsing. These are downstream market processes that occur after bid submission.

## Domain context

The mFRR EAM went live on 4 March 2025 as part of the Nordic Balancing Model (NBM). It operates on 15-minute Market Time Units (MTUs). There are 96 MTUs per day. BSPs submit bids to their connecting TSO, the TSO filters and forwards bids to the Activation Optimization Function (AOF), which selects bids for activation.

The market will transition to the European MARI platform at a later date. This changes timing parameters, price limits, and some validation rules. The library must support both pre-MARI and post-MARI configurations via a toggle.

### Key timing (pre-MARI)

- BSP GCT (gate closure): QH-45 (45 minutes before the quarter-hour)
- TSO GCT: QH-15
- AOF run: QH-14

### Key timing (post-MARI)

- BSP GCT: QH-25
- TSO GCT: QH-12
- AOF run: QH-10

### Price limits

- Pre-MARI: -10,000 to +10,000 EUR/MWh
- Post-MARI: -15,000 to +15,000 EUR/MWh (later -99,999 to +99,999)
- Granularity: 0.01 EUR

### Volume limits

- Min bid: 1 MW (except Statnett: 10 MW, with 5-9 MW exception for one bid per resource/direction/MTU)
- Max bid: 9,999 MW (technical limit)
- Granularity: 1 MW

## Architecture

### Module layout

- `types.py` - All enums and Pydantic models. Imported by everything. No external API dependencies.
- `config.py` - Global configuration: MARI mode toggle, default TSO settings.
- `exceptions.py` - Typed exception hierarchy. All exceptions inherit from `NexaMFRREAMError`.
- `bids/` - Bid builders using a fluent API pattern. `simple.py` for simple bids, `complex.py` for exclusive/inclusive/multipart groups, `linked.py` for technical and conditional links, `validation.py` for all validation rules.
- `documents/` - `reserve_bid.py` for building outgoing ReserveBid documents. `acknowledgement.py` for parsing incoming ACK/NACK responses.
- `xml/` - Serialization and deserialization between Pydantic models and IEC CIM XML. Uses `lxml` for XML generation. XSD schemas vendored in `xml/schemas/`. `namespaces.py` handles the multiple namespace URIs and schema versions.
- `tso/` - TSO-specific configuration and validation overrides. Each TSO module defines which national attributes are supported, specific validation rules, and any schema deviations.
- `timing.py` - Pure functions for MTU calculations, gate closure times, DST handling, MARI timing differences.
- `pricing.py` - GS tax (grunnrenteskatt) price adjustment. `gs_adjusted_price` for single MTU, `gs_adjust_bids` for batch adjustment of `BidTimeSeriesModel` lists. Applies formula `tier + rate*(DA-tier)` with per-direction clamping and Statnett price limits.
- `link_ordering.py` - Technical link ordering. `assign_technical_links` assigns consistent UUID link IDs to bids by price rank across MTUs.
- `pandas.py` - Optional module (guarded import). Converts DataFrames to bid objects.

### Key design decisions

1. **Fluent builder API** - Bids are constructed via method chaining. This is the public API surface. Internally, builders produce Pydantic models.
2. **Pydantic for all data models** - Every bid, document, time series, etc. is a Pydantic BaseModel. Validation happens at the model level (structural) and at the document level (business rules).
3. **TSO as strategy pattern** - Each TSO module provides a configuration object that the validation and serialization layers consume. No if/else chains on TSO name.
4. **MARI mode as enum** - `MARIMode.PRE_MARI` and `MARIMode.POST_MARI`. Affects validation rules, timing calculations, and price limits. Can be set globally or passed per-call.
5. **Immutable after build** - Once `.build()` is called, the resulting object is frozen. Modifications require creating a new builder.
6. **UUIDs generated automatically** - Document mRIDs, bid mRIDs, link IDs are all auto-generated as UUID v4 unless explicitly provided.

## CIM XML schema details

### Schema versions

Three ReserveBid schema versions are in active use. Statnett's test environment accepts all three:

| Version | Namespace URI | Element naming style | Notes |
|---|---|---|---|
| NBM v7.2 | `urn:iec62325:ediel:nbm:reservebiddocument:7:2` | `quantity_Measure_Unit.name` (short) | Nordic-specific XSD. `inclusiveBidsIdentification` is an extension element. |
| IEC v7.2 | `urn:iec62325.351:tc57wg16:451-7:reservebiddocument:7:2` | `quantity_Measure_Unit.name` (short) | Used in Statnett example XML. Same element names as NBM v7.2. |
| IEC v7.4 | `urn:iec62325.351:tc57wg16:451-7:reservebiddocument:7:4` | `quantity_Measurement_Unit.name` (long) | Adds `mktPSRType.psrType` natively. `inclusiveBidsIdentification` promoted from extension to standard. Required for inclusive bids on Statnett. |

The element naming difference between versions:

| v7.2 (NBM and IEC) | v7.4 (IEC) |
|---|---|
| `quantity_Measure_Unit.name` | `quantity_Measurement_Unit.name` |
| `price_Measure_Unit.name` | `price_Measurement_Unit.name` |
| `energyPrice_Measure_Unit.name` | `energyPrice_Measurement_Unit.name` |

The implementation guide tables use v7.4 naming. The Statnett example XML uses v7.2 naming. Both are correct for their version.

The serializer must know which version it targets. Default should be v7.4 (widest compatibility, inclusive bids work). The deserializer must accept all three namespace URIs and handle either element naming convention.

### Status element structure

The `status` field on `BidTimeSeries` is a nested element, not a simple string:

```xml
<status>
    <value>A06</value>
</status>
```

### Coding scheme attributes

Several elements carry a `codingScheme` attribute. The XSD defines this as required on `AreaID_String`, `PartyID_String`, and `ResourceID_String` types. Known coding scheme values:

- `A01` - EIC
- `A10` - GS1
- `NNO` - Norwegian national (NOKG/NOG codes, used in Statnett example)
- `NSE` - Swedish national
- `NDK` - Danish national
- `NFI` - Finnish national

### Element order in BidTimeSeries

Must follow the XSD sequence. The v7.2 and v7.4 orderings differ slightly (v7.4 moves `inclusiveBidsIdentification` and adds `mktPSRType.psrType` before `Period`). The serializer must emit elements in the correct order for the target version.

v7.2 (NBM) order places `inclusiveBidsIdentification` last (after `ExchangedWith_MarketParticipant`).

v7.4 order places `inclusiveBidsIdentification` and `mktPSRType.psrType` before `Period`.

### Fields in XSD not discussed in the implementation guide

- `blockBid` (ESMPBoolean), `priority` (integer), `stepIncrementQuantity` (decimal)
- `validity_Period.timeInterval`, `original_MarketProduct.marketProductType`
- `provider_MarketParticipant.mRID`, `price_Measure(ment)_Unit.name`
- `ProcuredFor_MarketParticipant`, `SharedWith_MarketParticipant`, `ExchangedWith_MarketParticipant`
- `AvailableBiddingZone_Domain`, `marketAgreement.*`

Modelled in types.py as optional fields. Not exposed in the builder API unless there is a known use case.

### Denmark-specific fields

- `mktPSRType.psrType` - mandatory for DK per implementation guide. Present natively in v7.4 XSD. Not in v7.2 NBM XSD (was a Denmark-only extension).
- `Note` - optional, DK only. Not in any standard XSD.

### CIM document types (in scope)

| Document | Direction | Schema | Purpose |
|---|---|---|---|
| ReserveBid_MarketDocument | BSP -> TSO | v7.2 / v7.4 | Submit/update/cancel bids |
| Acknowledgement_MarketDocument | TSO -> BSP | IEC v8.1 | ACK/NACK for bid documents |

### XML datetime formats

- `ESMP_DateTime` (createdDateTime): `YYYY-MM-DDTHH:MM:SSZ` (with seconds)
- `YMDHM_DateTime` (time intervals): `YYYY-MM-DDTHH:MMZ` (no seconds)

### XML string length limits (from XSD)

- `ID_String`: max 60 characters
- `PartyID_String`: max 16 characters
- `AreaID_String`: max 18 characters
- `ResourceID_String`: max 60 characters
- `ReasonText_String`: max 512 characters
- `ESMPVersion_String`: pattern `[1-9]([0-9]){0,2}` (1-999)
- `Amount_Decimal`: 17 total digits
- `Position_Integer`: 1-999999

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

- **Technical link**: prevents double-activation across consecutive QHs. Works for both simple and complex bids. All components must share the same link ID within an MTU. UUID required for the link ID.
- **Conditional link**: adjusts availability in QH0 based on activation outcome in QH-1/QH-2. Only for simple bids (except Statnett Z04 for period shift, Fingrid for inclusive bids). Max 3 links to QH-1 and 3 to QH-2.

## TSO-specific implementation notes

### Energinet (Denmark)

- BRP acts as BSP (use A46 role regardless)
- Only scheduled activation type allowed (no direct) until MARI
- Local direct activation model: DA bid + linked bid in next QH are separate, can have different price/volume
- Cannot change market product type on update (must cancel + resubmit)
- `mktPSRType.psrType` is mandatory (B16 solar, B18 wind offshore, B19 wind onshore, B20 other)
- `Note` attribute available for BRP custom text - NOT in standard XSD
- Conditional bid types A71 and A72 not supported
- Uses a specific schema version - confirm namespace and XSD with Energinet

### Fingrid (Finland)

- BEGOT is 30 days
- Max 2000 bids per message (stricter than the common 4000 limit)
- Supports inclusive bids (used for aggregated bids, same proportion selected)
- Conditional linking allowed for inclusive bids (special rules - see implementation guide section 4.2)
- Voluntary secondary bid ID via Reason element (code A95, text max 100 chars, restricted character set)
- Can change product type between A05 and A07

### Statnett (Norway)

- Richest feature set: period shift, faster activation, mFRR-D, other non-standard, inclusive bids
- Min bid 10 MW (exception: one bid 5-9 MW per resource/direction/MTU)
- 15-minute cut-off: bid documents older than 15 min silently dropped (no NACK)
- Period shift: Z64 (beginning), Z65 (end) via Reason element. Conditional linking with Z04 status.
- Period shift only bids: product type Z01, must be indivisible, no price
- Faster activation: specify FAT including 1 min prep time (e.g. PT3M for 2 min ramp)
- Non-standard bids (A02): mFRR-D (Z74) and Other (Z83), must be simple technically-linked
- Resource coding scheme: NNO (NOKG/NOG national codes)
- Sender coding scheme in example: A10 (GS1)
- Receiver EIC: 10X1001A1001A38Y
- Can change product type between A05 and A07

### Svenska kraftnat (Sweden)

- 6-minute cut-off: bid documents older than 6 min silently dropped
- Overbelastningshantering vid storning (non-standard A02): reason code Z74, indivisible, technically linked, must have activation time specified
- Can change product type between A05 and A07

## Build and test

```bash
make install    # Install dev dependencies
make test       # Run pytest
make lint       # Run ruff
make typecheck  # Run mypy
make ci         # Run all checks (lint + typecheck + test)
```

### Test fixtures

Example XML messages should be placed in `tests/fixtures/`. The vendored Statnett example (`SN_Simple_ReserveBid_MarketDocument.xml`) is the reference for XML round-trip testing. Additional examples from nordicbalancingmodel.net should be downloaded and added.

### Test strategy

- Unit tests for all bid builders (simple, complex, linked)
- Unit tests for validation rules (common + per-TSO)
- XML round-trip tests: build Pydantic model -> serialize to XML -> validate against XSD -> deserialize -> compare to original model
- Unit tests for timing calculations (MTU boundaries, gate closures, DST transitions)
- Verify generated XML element ordering matches XSD sequence for both v7.2 and v7.4
- Test all three namespace URIs during deserialization
- Test acknowledgement document parsing

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
- Follow XSD element ordering strictly in serializer output

## Implementation order

1. `types.py` - All enums and Pydantic models
2. `exceptions.py` - Exception hierarchy (base: `NexaMFRREAMError`)
3. `config.py` - Global config, MARI mode
4. `timing.py` - MTU calculations, gate closures
5. `xml/namespaces.py` - Namespace URI constants, version-aware element name mapping
6. `tso/base.py` + individual TSO modules - TSO configuration objects
7. `bids/simple.py` - Simple bid builder
8. `bids/complex.py` - Complex group builders
9. `bids/linked.py` - Link builders
10. `bids/validation.py` - Validation rules
11. `xml/serialize.py` - Pydantic -> XML (version-aware element names and ordering)
12. `xml/deserialize.py` - XML -> Pydantic (handles all namespace URIs and both naming conventions)
13. `documents/reserve_bid.py` - BidDocument builder
14. `documents/acknowledgement.py` - ACK parser
15. `pandas.py` - DataFrame integration
16. `__init__.py` - Public API re-exports

## Common pitfalls

- **Denmark BRP/BSP distinction**: In Denmark, BRPs act as BSPs. Always use market role A46 (BSP) in documents.
- **Revision number is always 1**: Do not increment. Each update is a new document with a new mRID.
- **Bid mRID is permanent**: When updating a bid, use the ORIGINAL bid time series mRID. New mRID = new bid.
- **Cannot change bid from simple to complex**: Must cancel and resubmit.
- **Cannot change bid period or resource**: Must cancel and resubmit.
- **Complex bids cannot be partially cancelled**: Cancel all components, or convert to simple first.
- **Conditional links to cancelled bids become invalid**: The BSP is responsible for maintaining valid links.
- **Technical link IDs must be unique within an MTU**: Only one simple or one complex bid per link ID per MTU.
- **Period shift only bids (Z01) have no price**: The `energy_Price.amount` element must be omitted.
- **Statnett/SVK cut-off times are silent**: Old messages are dropped with no NACK sent.
- **DST handling**: Full day in UTC is 23:00-23:00 (winter) or 22:00-22:00 (summer). Transition days have 92 or 100 MTUs.
- **XML element ordering**: The XSD defines a strict `xs:sequence`. Elements emitted out of order will fail schema validation.
- **Element names differ between schema versions**: v7.2 uses `quantity_Measure_Unit.name`, v7.4 uses `quantity_Measurement_Unit.name`. The serializer must match the target version.
- **Namespace mismatch**: Three namespace URIs are in use. The deserializer must accept all.
- **Fingrid max 2000 bids per message**: Stricter than the common 4000 limit.
- **UUID length**: UUIDs are 36 characters. The `ID_String` max is 60 characters. UUIDs fit but leave no room for prefixes.
- **Inclusive bids require v7.4 or NBM v7.2**: IEC v7.2 has `inclusiveBidsIdentification` as an extension, not a standard element. Statnett's test environment requires v7.4 or NBM v7.2 for inclusive bid validation.

## Definition of Done

- Track our implementation status in @README.md
- Update tests to include new/changed work, aim for >80% code coverage, but prioritise good tests
- Run tests and ensure they pass using `make ci`
- Update README and/or docs to document the new behaviour/feature
- Check if Makefile (and `make ci`) is missing any common operations (for new functionality added)
- Add anything needed in @.gitignore to avoid checking in secrets, or temp files/logs
- Never commit API keys, tokens, or credentials
