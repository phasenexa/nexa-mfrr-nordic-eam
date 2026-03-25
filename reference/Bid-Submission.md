# Bid Submission Routine

This document describes how mFRR EAM bid documents travel from the BSP to the TSO and how acknowledgements come back. It covers the ECP/EDX messaging infrastructure, the MADES transport layer, service codes, message types, and the end-to-end submission flow.

## Overview

```
nexa-mfrr-nordic-eam (this library)
    |
    |  Bid -> BidDocument -> .to_xml()
    v
ReserveBid_MarketDocument XML (CIM IEC 62325-451-7)
    |
    |  BSP writes to local ECP endpoint
    v
ECP/EDX Endpoint (BSP-operated)
    |
    |  MADES SOAP / AMQP / FSSF
    v
ECP/EDX Network (NEM-PROD or NEM-TEST)
    |
    |  Routed via EDX service catalogue
    v
TSO ECP Endpoint (e.g. Statnett mfrr-bid-coll)
    |
    |  TSO validates, returns ACK/NACK
    v
Acknowledgement_MarketDocument XML
    |
    |  BSP polls or receives via ECP
    v
nexa-mfrr-nordic-eam (this library)
    |
    |  AcknowledgementDocument.from_xml()
    v
Parsed ACK with reason codes
```

This library handles the top and bottom of this flow: building the XML and parsing the ACK. The middle (ECP/EDX transport) is infrastructure the BSP deploys and operates.

## ECP/EDX infrastructure

ECP (Energy Communication Platform) is the ENTSO-E standardized messaging platform. EDX (ENTSO-E Data Exchange) is an optional extension that adds service catalogue routing and additional integration channels.

BSPs must deploy their own ECP endpoint and EDX toolbox. These are available as Docker images from the ENTSO-E Docker Hub. The endpoint connects to the Nordic Energy Messaging (NEM) network, which has separate TEST and PROD environments.

### Onboarding process

1. Register as a BSP with your connecting TSO
2. Request V-codes (ECP endpoint addresses) from your TSO for test and production
3. Install ECP endpoint and EDX toolbox (Docker or standalone)
4. Receive a registration keystore from your TSO to authenticate the endpoint
5. Configure message paths (download from ediel.org for your TSO)
6. Connect to NEM-TEST and run syntax/SIT testing
7. Pass end-to-end testing before moving to NEM-PROD

TSO-specific ECP onboarding pages:
- Statnett: https://ediel.org/nordic-ecp-edx-group-nex/nex-statnett/
- Fingrid: https://ediel.org/nordic-ecp-edx-group-nex/fingrid/
- Energinet: https://ediel.org/nordic-ecp-edx-group-nex/energinet/
- Svenska kraftnat: https://ediel.org/nordic-ecp-edx-group-nex/svenska-kraftnat/

General NEX guide: https://ediel.org/nordic-ecp-edx-group-nex/

### Integration channels

ECP supports several integration channels between your business application and the local ECP endpoint:

- **FSSF** (File System Shared Folder) - write XML files to an outbox directory, read from inbox
- **AMQP(S)** - message broker integration
- **MADES Web Service** - SOAP/MTOM over HTTP(S)

EDX additionally supports SFTP, SCP, and further web service variants.

The simplest integration for a Python application is FSSF (write a file) or AMQP (publish a message). MADES is the native SOAP protocol used between ECP endpoints on the NEM network and is also available as a local integration channel.

## ECP message types for mFRR EAM

The EDX service catalogue defines specific message types for each document exchange. These are the ECP/EDX message type codes used for routing.

### Bid submission (in scope for this library)

| ECP Message Type | Document | Producer | Consumer |
|---|---|---|---|
| `NBM-MFRREAM-CIM-PTA47-MTA37` | ReserveBid_MarketDocument | BSP | TSO (mfrr-bid-coll) |
| `NBM-MFRREAM-CIM-PTA47-MTA37-ACK` | Acknowledgement_MarketDocument | TSO (mfrr-bid-coll) | BSP |

### Activation (out of scope for this library)

| ECP Message Type | Document | Producer | Consumer |
|---|---|---|---|
| `NBM-MFRREAM-CIM-PTA47-MTA39` | Activation_MarketDocument (scheduled) | TSO (mfrr-order) | BSP |
| `NBM-MFRREAM-CIM-PTA47-MTA40` | Activation_MarketDocument (direct) | TSO (mfrr-order) | BSP |
| `NBM-MFRREAM-CIM-PTA47-MTZ37` | Activation_MarketDocument (faster) | TSO (mfrr-order) | BSP |
| `NBM-MFRREAM-CIM-PTA47-MTZ40` | Activation_MarketDocument (period shift) | TSO (mfrr-order) | BSP |
| `NBM-MFRREAM-CIM-PTA47-MTZ43` | Activation_MarketDocument (mFRR-D) | TSO (mfrr-order) | BSP |
| `NBM-MFRREAM-CIM-PTA47-MTZ44` | Activation_MarketDocument (other non-standard) | TSO (mfrr-order) | BSP |
| `NBM-MFRREAM-CIM-PTA47-MTA39-ACK` | Acknowledgement_MarketDocument (ack request) | BSP | TSO (mfrr-order) |
| `NBM-MFRREAM-CIM-PTA47-MTA41` | Activation_MarketDocument (response) | BSP | TSO (mfrr-order) |
| `NBM-MFRREAM-CIM-PTA47-MTA41-ACK` | Acknowledgement_MarketDocument (ack response) | TSO (mfrr-order) | BSP |

### Reports (out of scope for this library)

| ECP Message Type | Document | Producer | Consumer |
|---|---|---|---|
| `NBM-MFRREAM-CIM-PTA47-MTA38` | ReserveAllocationResult_MarketDocument | TSO (bsp-reporter) | BSP |
| `NBM-MFRREAM-CIM-PTA47-MTB45` | BidAvailability_MarketDocument | TSO (bsp-reporter) | BSP |

The message type naming convention is: `NBM-MFRREAM-CIM-PT{processType}-MT{documentType}`. Process type is always A47 (mFRR). Document type codes match the CIM document `type` field (A37 = reserve bid, A39 = scheduled activation, etc.).

## EDX service codes (test environments)

For Statnett BSP testing, the following EDX services are configured:

| Environment | EDX Service Code |
|---|---|
| BSP syntax/SIT testing | `SERVICE-NO-MFRREAM-BSPTEST` |
| BSP end-to-end testing | `SERVICE-NO-MFRREAM-BSPE2E-V2` |

The NEM network for all Nordic testing is `NEM-TEST`.

Contact mfrr@svk.se for Svenska kraftnat test service codes, reservit@fingrid.fi for Fingrid, and electricitymarket@energinet.dk for Energinet.

## Supported ReserveBid schema versions

Statnett's BSP test environment currently accepts these namespace URIs:

- `urn:iec62325.351:tc57wg16:451-7:reservebiddocument:7:4` (IEC v7.4)
- `urn:iec62325.351:tc57wg16:451-7:reservebiddocument:7:2` (IEC v7.2)
- `urn:iec62325:ediel:nbm:reservebiddocument:7:2` (NBM v7.2)

Inclusive bids require v7.4 or NBM v7.2 (not IEC v7.2).

Element names differ between versions. See CLAUDE.md for the mapping.

## MADES transport details

MADES (Market Data Exchange Standard) is the SOAP protocol used between ECP endpoints. Understanding it helps when debugging transport issues, even though this library does not implement MADES directly.

### SOAP operations

| Operation | SOAP Action | Direction | Purpose |
|---|---|---|---|
| SendMessage | `http://mades.entsoe.eu/SendMessage` | Outbound | Submit bid XML to TSO endpoint |
| CheckMessageStatus | `http://mades.entsoe.eu/CheckMessageStatus` | Outbound | Poll delivery state after send |
| ReceiveMessage | `http://mades.entsoe.eu/ReceiveMessage` | Inbound | Poll next message from TSO |
| ConfirmReceiveMessage | `http://mades.entsoe.eu/ConfirmReceiveMessage` | Inbound | Acknowledge receipt, removes from queue |
| ConnectivityTest | `http://mades.entsoe.eu/ConnectivityTest` | Either | Verify endpoint connectivity |

### Authentication

MADES does not use username/password at the SOAP level. Identity is established via pre-registered endpoint codes at the network/infrastructure level. When sending, the client specifies its `receiverCode` (the TSO's MADES endpoint identifier, e.g. `50V-Statnett-ATI` for Statnett). The sender identity is implicit from the registered ECP endpoint.

### Message encoding

MADES uses MTOM (Message Transmission Optimization Mechanism) encoding over SOAP. The XML payload is the CIM document. Messages are encoded as ISO-8859-1 (not UTF-8) on the wire, particularly for inbound messages from Nordic TSOs, to preserve Norwegian/Swedish/Danish characters.

### Connection lifecycle

MADES connections are not persistent. The typical pattern is: establish client per polling cycle, send/receive, then close. There is no session or keep-alive.

## Bid submission flow (end-to-end)

### 1. Build bids

Use this library's builder API to construct bids and wrap them in a `BidDocument`:

```python
from nexa_mfrr_eam import Bid, BidDocument, TSO

bid = Bid.up(volume_mw=50, price_eur=85.50).divisible(min_volume_mw=10) \
    .for_mtu("2026-03-21T10:00Z").resource("NOKG90901", coding_scheme="NNO") \
    .build()

doc = BidDocument(tso=TSO.STATNETT) \
    .sender(party_id="9999909919920", coding_scheme="A10") \
    .add_bid(bid).build()
```

### 2. Validate

```python
errors = doc.validate()
if errors:
    raise ValueError(f"Bid validation failed: {errors}")
```

Validation checks common rules (price limits, volume limits, MTU alignment) and TSO-specific rules (min bid volume, supported attributes, max bids per message).

### 3. Serialize to XML

```python
xml_bytes = doc.to_xml()
```

This produces a complete `ReserveBid_MarketDocument` XML document ready for transport.

### 4. Send via ECP

How you send depends on your ECP integration channel:

```python
# FSSF: write to ECP outbox
from pathlib import Path
Path("/ecp/outbox/bid_20260321T1000.xml").write_bytes(xml_bytes)

# AMQP: publish to local broker
channel.basic_publish(exchange="", routing_key="ecp.outbox", body=xml_bytes)
```

The ECP endpoint routes the message to the TSO's `mfrr-bid-coll` service via the EDX service catalogue.

### 5. Receive acknowledgement

The TSO validates the bid document and returns an `Acknowledgement_MarketDocument` via ECP. Poll your ECP inbox or receive via your integration channel.

```python
# Read ACK XML from ECP inbox
ack_xml = Path("/ecp/inbox/latest_ack.xml").read_bytes()

# Parse with this library (planned)
from nexa_mfrr_eam import AcknowledgementDocument
ack = AcknowledgementDocument.from_xml(ack_xml)

if ack.is_accepted:
    print("Bids accepted")
else:
    for reason in ack.reasons:
        print(f"Rejected: {reason.code} - {reason.text}")
```

### 6. Handle rejection

If the acknowledgement is negative (A02 - fully rejected), all bids in the document are rejected. The ACK contains reason codes and text indicating why. Common reasons include validation errors (price out of range, bid size violations, invalid linking). Fix the issues and resubmit with a new document mRID.

## Delta submission pattern

You do not need to resend your entire bid portfolio each time. The standard approach is:

- Only send bids that have changed since the last successful submission
- To update a bid: send a new document containing the bid with the **same bid time series mRID** but updated price/volume
- To cancel a bid: send a new document with the bid's mRID and `quantity.quantity` set to 0
- Unchanged bids do not need to be included in the update document

Each new document gets a fresh document mRID (UUID). The revision number is always 1.

## Gate closure considerations

Bids must be received by the TSO before the BSP Gate Closure Time (BEGCT):

- Pre-MARI: QH-45 (45 minutes before the quarter-hour start)
- Post-MARI: QH-25

Allow time for ECP transport. A bid submitted at QH-46 that takes 2 minutes to traverse the ECP network will arrive after gate closure. Build in a safety margin.

TSO-specific cut-off times for stale messages (separate from gate closure):
- Statnett: documents older than 15 minutes are silently dropped (no NACK)
- Svenska kraftnat: documents older than 6 minutes are silently dropped
- This is based on the `createdDateTime` in the document header, so ensure your system clock is accurate

## Test environment behaviour (Statnett)

The Statnett BSP SYNTAX/SIT test environment has the following characteristics:

- Gate closure is set to QH-45 (pre-MARI timing)
- Bids can be submitted up to 2 days in advance
- Day-ahead price validation is turned off
- Maximum bid price is validated at 10,000 EUR/MWh (pre-MARI limits)
- Simple bids, complex bids (exclusive, multipart, inclusive), linked bids (technical, conditional), and non-standard bids (mFRR-D Z74) are all supported
- The test environment uses a simple activation simulator (out of scope for this library, but useful to know: submitted bids will be activated automatically for testing purposes)

## What you need from your TSO

Before you can submit bids:

1. **BSP registration** - formal agreement with your connecting TSO
2. **ECP V-codes** - endpoint addresses for test and production
3. **Registration keystore** - certificate for ECP endpoint authentication
4. **Your BSP party ID** - EIC code (scheme A01) or GS1 GLN (scheme A10)
5. **Resource object codes** - identifiers for your generation/consumption assets
6. **EDX service catalogue configuration** - your TSO adds your endpoint to the service catalogue
7. **Message path configuration files** - download from ediel.org for your TSO
