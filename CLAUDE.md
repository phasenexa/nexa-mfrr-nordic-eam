# CLAUDE.md - nexa-mfrr-nordic-eam

## What this project is

A Python library for building, validating, and serializing mFRR energy activation market (EAM) bids for the four Nordic TSOs: Statnett (Norway), Fingrid (Finland), Energinet (Denmark), and Svenska kraftnat (Sweden). The library also parses TSO response documents (acknowledgements, activation orders, bid availability reports, allocation results).

The Python package name is `nexa_mfrr_eam` (not `nexa_mfrr`) to avoid conflicts with other Phase Nexa mFRR-related packages.

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
- `exceptions.py` - Typed exception hierarchy. All exceptions inherit from `NexaMFRREAMError`.
- `bids/` - Bid builders using a fluent API pattern. `simple.py` for simple bids, `complex.py` for exclusive/inclusive/multipart groups, `linked.py` for technical and conditional links, `validation.py` for all validation rules.
- `documents/` - One module per CIM document type. Each has a builder (for outgoing docs) and parser (for incoming docs). Uses Pydantic models internally.
- `xml/` - Serialization and deserialization between Pydantic models and IEC CIM XML. Uses `lxml` for XML generation. XSD schemas vendored in `xml/schemas/`. `namespaces.py` handles the multiple namespace URIs in use.
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

## CIM XML schema details

### XSD validation findings

The vendored XSD (`nbm-ediel-reservebiddocument-7-2.xsd`) uses namespace `urn:iec62325:ediel:nbm:reservebiddocument:7:2`. The Statnett example XML uses a different namespace: `urn:iec62325.351:tc57wg16:451-7:reservebiddocument:7:2`. Both must be handled during deserialization.

**Critical element name discrepancies** between the implementation guide and the actual XSD/example XML:

- XSD/XML: `quantity_Measure_Unit.name` -- Implementation guide text: `quantity_Measurement_Unit.name`
- XSD/XML: `energyPrice_Measure_Unit.name` -- Implementation guide text: `energyPrice_Measurement_Unit.name`

Always follow the XSD and example XML, not the implementation guide prose.

**Status element is nested**, not flat:

```xml
<status>
    <value>A06</value>
</status>
```

**Coding scheme attributes**: Several elements carry a `codingScheme` attribute. The XSD defines this as required on `AreaID_String`, `PartyID_String`, and `ResourceID_String` types. Known coding scheme values:

- `A01` - EIC
- `A10` - GS1
- `NNO` - Norwegian national (NOKG/NOG codes, used in Statnett example)
- `NSE` - Swedish national

**Element order in BidTimeSeries** (must follow this XSD sequence):

1. mRID
2. auction.mRID (optional)
3. businessType
4. acquiring_Domain.mRID
5. connecting_Domain.mRID
6. provider_MarketParticipant.mRID (optional)
7. quantity_Measure_Unit.name
8. currency_Unit.name (optional)
9. price_Measure_Unit.name (optional)
10. divisible
11. linkedBidsIdentification (optional)
12. multipartBidIdentification (optional)
13. exclusiveBidsIdentification (optional)
14. blockBid (optional)
15. status (optional, contains nested `<value>`)
16. priority (optional)
17. registeredResource.mRID (optional)
18. flowDirection.direction
19. stepIncrementQuantity (optional)
20. energyPrice_Measure_Unit.name (optional)
21. marketAgreement.type (optional)
22. marketAgreement.mRID (optional)
23. marketAgreement.createdDateTime (optional)
24. activation_ConstraintDuration.duration (optional)
25. resting_ConstraintDuration.duration (optional)
26. minimum_ConstraintDuration.duration (optional)
27. maximum_ConstraintDuration.duration (optional)
28. standard_MarketProduct.marketProductType (optional)
29. original_MarketProduct.marketProductType (optional)
30. validity_Period.timeInterval (optional)
31. Period (1..*)
32. AvailableBiddingZone_Domain (0..*)
33. Reason (0..*)
34. Linked_BidTimeSeries (0..*)
35. ProcuredFor_MarketParticipant (optional)
36. SharedWith_MarketParticipant (0..*)
37. ExchangedWith_MarketParticipant (0..*)
38. inclusiveBidsIdentification (optional, last element)

This element ordering is MANDATORY for XML schema compliance. The serializer must emit elements in this exact sequence.

**Fields present in XSD but not discussed in the implementation guide**:

- `blockBid` (ESMPBoolean)
- `priority` (integer)
- `stepIncrementQuantity` (decimal)
- `validity_Period.timeInterval`
- `original_MarketProduct.marketProductType`
- `provider_MarketParticipant.mRID`
- `price_Measure_Unit.name`
- `ProcuredFor_MarketParticipant`
- `SharedWith_MarketParticipant` (unbounded)
- `ExchangedWith_MarketParticipant` (unbounded)
- `AvailableBiddingZone_Domain` (unbounded)
- `marketAgreement.type`, `marketAgreement.mRID`, `marketAgreement.createdDateTime`

These should be modelled in types.py as optional fields but not exposed in the builder API unless there is a known use case.

**Denmark-specific fields NOT in the standard XSD**:

- `mktPSRType.psrType` (mandatory for DK per implementation guide)
- `Note` (optional, DK only)

These are in Denmark's specific schema version. The Energinet TSO module must handle a different XSD or extend the serializer.

### CIM document types

| Document | Direction | Schema | Purpose |
|---|---|---|---|
| ReserveBid_MarketDocument | BSP -> TSO | NBM v7.2 (vendored XSD), impl guide ref v7.4 | Submit/update/cancel bids |
| Activation_MarketDocument | TSO -> BSP | IEC v6.2 | Activation orders (incl. heartbeat) |
| Activation_MarketDocument | BSP -> TSO | IEC v6.2 | Activation response |
| BidAvailability_MarketDocument | TSO -> BSP | v1.1 | Bid availability reports |
| ReserveAllocationResult_MarketDocument | TSO -> BSP | IEC v6.4 | Activation settlement results |
| Acknowledgement_MarketDocument | Both | IEC v8.1 | ACK/NACK for any document |

### XML datetime formats

Two formats are used:

- `ESMP_DateTime` (createdDateTime): `YYYY-MM-DDTHH:MM:SSZ` (with seconds)
- `YMDHM_DateTime` (time intervals): `YYYY-MM-DDTHH:MMZ` (no seconds)

The XSD enforces these via regex patterns. The serializer must use the correct format for each field.

### XML string length limits (from XSD)

- `ID_String`: max 60 characters (mRID, auction.mRID, link IDs, etc.)
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
- No heartbeat
- Only scheduled activation type allowed (no direct) until MARI
- Local direct activation model: DA bid + linked bid in next QH are separate, can have different price/volume
- Cannot change market product type on update (must cancel + resubmit)
- `mktPSRType.psrType` is mandatory (B16 solar, B18 wind offshore, B19 wind onshore, B20 other) - NOT in standard XSD
- `Note` attribute available for BRP custom text (passed through to activation document) - NOT in standard XSD
- Conditional bid types A71 and A72 not supported
- Uses a specific schema version - confirm namespace and XSD with Energinet
- Activation response must be within 2 min; late responses rejected with negative ACK
- BSP NOT accountable if "Unavailable" response accepted within time limit

### Fingrid (Finland)

- No heartbeat
- BEGOT is 30 days
- Max 2000 bids per message (stricter than the common 4000 limit)
- Supports inclusive bids (used for aggregated bids, same proportion selected)
- Conditional linking allowed for inclusive bids (special rules - see implementation guide section 4.2)
- Voluntary secondary bid ID via Reason element (code A95, text max 100 chars, restricted character set)
- Can change product type between A05 and A07
- Rounds partial activation volumes to next full MW (or 0.1 MW for aggregated)
- Activation response: BSP accountable regardless of response

### Statnett (Norway)

- Richest feature set: period shift, faster activation, mFRR-D, other non-standard, inclusive bids
- Min bid 10 MW (exception: one bid 5-9 MW per resource/direction/MTU)
- 15-minute cut-off: bid documents older than 15 min silently dropped (no NACK)
- Heartbeat at T-12, T-7.5 (if no activation), T-3
- Missing heartbeat response: bids set unavailable for upcoming MTUs (see table in impl guide 4.3.2)
- Heartbeat response with A11 (Unavailable) treated as missing response
- Period shift: Z64 (beginning), Z65 (end) via Reason element. Conditional linking with Z04 status.
- Period shift only bids: product type Z01, must be indivisible, no price
- Faster activation: specify FAT including 1 min prep time (e.g. PT3M for 2 min ramp)
- Deactivation: TSO sends updated activation with earlier end time, same order ID
- Non-standard bids (A02): mFRR-D (Z74) and Other (Z83), must be simple technically-linked
- Resource coding scheme: NNO (NOKG/NOG national codes)
- Sender coding scheme in example: A10 (GS1)
- Receiver EIC: 10X1001A1001A38Y
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

Example XML messages should be placed in `tests/fixtures/`. The vendored Statnett example (`SN_Simple_ReserveBid_MarketDocument.xml`) is the reference for XML round-trip testing. Additional examples from nordicbalancingmodel.net should be downloaded and added.

### Test strategy

- Unit tests for all bid builders (simple, complex, linked)
- Unit tests for validation rules (common + per-TSO)
- XML round-trip tests: build Pydantic model -> serialize to XML -> validate against XSD -> deserialize -> compare to original model
- Unit tests for timing calculations (MTU boundaries, gate closures, DST transitions)
- Unit tests for heartbeat detection and response
- Verify generated XML element ordering matches XSD sequence
- Test both namespace URIs during deserialization

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

1. `types.py` - All enums (Direction, MarketProductType, BiddingZone, TSO, MARIMode, ConditionalStatus, NonStandardType, PeriodShiftPosition, ActivationType, CodingScheme) and Pydantic models (BidModel, BidTimeSeriesModel, DocumentModel, etc.)
2. `exceptions.py` - Exception hierarchy (base: `NexaMFRREAMError`)
3. `config.py` - Global config, MARI mode
4. `timing.py` - MTU calculations, gate closures
5. `xml/namespaces.py` - Namespace URI constants and handling
6. `tso/base.py` + individual TSO modules - TSO configuration objects
7. `bids/simple.py` - Simple bid builder
8. `bids/complex.py` - Complex group builders
9. `bids/linked.py` - Link builders
10. `bids/validation.py` - Validation rules
11. `xml/serialize.py` - Pydantic -> XML (must follow XSD element order)
12. `xml/deserialize.py` - XML -> Pydantic (must handle both namespace URIs)
13. `documents/reserve_bid.py` - BidDocument builder
14. `documents/activation.py` - Activation parser + response builder
15. `documents/acknowledgement.py` - ACK parser
16. `documents/bid_availability.py` - Availability parser
17. `documents/allocation_result.py` - Allocation result parser
18. `heartbeat.py` - Heartbeat handling
19. `pandas.py` - DataFrame integration
20. `__init__.py` - Public API re-exports

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
- **Heartbeat response with A11 (Unavailable)**: Statnett treats this as missing heartbeat.
- **DST handling**: Full day in UTC is 23:00-23:00 (winter) or 22:00-22:00 (summer). Transition days have 92 or 100 MTUs.
- **XML element ordering**: The XSD defines a strict `xs:sequence`. Elements emitted out of order will fail schema validation. The serializer must follow the exact order listed in this document.
- **Namespace mismatch**: The NBM XSD namespace and the Statnett example namespace differ. The deserializer must accept both.
- **Element names follow XSD, not implementation guide prose**: Use `quantity_Measure_Unit.name` not `quantity_Measurement_Unit.name`.
- **Fingrid max 2000 bids per message**: Stricter than the common 4000 limit.
- **UUID length**: UUIDs are 36 characters. The `ID_String` max is 60 characters. UUIDs fit but leave no room for prefixes.

## Definition of Done

- Track our implementation status in @README.md
- Update tests to include new/changed work, aim for >80% code coverage, but prioritise good tests
- Run tests and ensure they pass using `make ci`
- Update README and/or docs to document the new behaviour/feature
- Check if Makefile (and `make ci`) is missing any common operations (for new functionality added)
- Add anything needed in @.gitignore to avoid checking in secrets, or temp files/logs
- Never commit API keys, tokens, or credentials
