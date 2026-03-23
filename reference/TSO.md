# mFRR EAM Bid Attributes: TSO Comparison

> Nordic mFRR Energy Activation Market — BSP Implementation Guide v1.2.0 (September 2025)
> Reference: [nordicbalancingmodel.net](https://nordicbalancingmodel.net)

---

## Common Nordic Attributes

All four TSOs (Energinet, Fingrid, Statnett, Svenska kraftnät) support these attributes.

| Attribute | Description |
|---|---|
| Price | Activation price in EUR/MWh. Determines merit order position. |
| Volume / Quantity | Offered MW. Minimum 1 MW, granularity 1 MW. |
| Direction | Up-regulation or down-regulation. |
| Bidding Zone | The bidding zone the bid belongs to (e.g. NO1, SE3, FI, DK1). |
| Bid Period | The 15-minute MTU(s) the bid covers. |
| Divisible / Indivisible | Whether partial activation is permitted. Indivisible bids are all-or-nothing. |
| Minimum Offered Volume | Minimum MW acceptable for activation. Mandatory for divisible bids. |
| Exclusive Group | Group of bids where at most one can be activated (mutually exclusive). |
| Multipart Bid | Group of bids for the same period that must all be activated together. |
| Technical Linking (time) | Links bids across consecutive MTUs. Models assets that cannot stop at quarter-hour boundaries. |
| Conditional Linking (time) | Bid availability depends on whether a prior MTU bid was or was not activated. |
| Activation Type (SA / SA+DA) | Whether the bid is available for Scheduled Activation only, or also for Direct Activation. |
| Locational Information | Sub-bidding-zone location. Used to assess internal congestion risk. |

---

## National Attributes by TSO

These attributes are handled by the TSO in pre-processing before bids reach the shared AOF platform. They are **not forwarded to the AOF**.

| Attribute | Energinet (DK) | Fingrid (FI) | Statnett (NO) | Svenska kraftnät (SE) |
|---|:---:|:---:|:---:|:---:|
| Maximum Duration | Yes | No | Yes | Yes |
| Resting Time | Yes | No | Yes | Yes |
| Inclusive Bids | No | Yes* | Yes | Yes |
| Activation Time (slower than FAT) | Yes | No | No | Yes |
| Faster Activation | No | No | Yes | No |
| Period Shift | No | No | Yes | Yes |
| Production Type (mandatory) | Yes | No | No | No |
| Voluntary Bid Identification | No | Yes* | No | No |

*Added in BSP Implementation Guide v1.2.0 (September 2025)

---

## TSO-Specific Products and Mechanisms

These are products or operational mechanisms that exist outside the standard AOF bid selection process.

| Feature | Energinet (DK) | Fingrid (FI) | Statnett (NO) | Svenska kraftnät (SE) |
|---|---|---|---|---|
| Disturbance / Emergency Reserve | Emergency Volumes fallback when automation fails | Reserve Power Plants — activated locally after all market bids exhausted | Operational Disturbance Reserve (DFR) — manually activated non-standard bids | Störningsreserven — activated locally after all market bids exhausted |
| Guaranteed Volume | No | No | Yes — reserves a ring-fenced volume of DA bids for incident response | No |
| Direct Activation (local model) | Yes — local model implemented for DA (added v1.2.0) | Not yet decided (local or common solution) | Yes | Yes |
| Heartbeat | Not implemented at go-live | Yes | Yes | Yes |
| Fallback Bid Submission | BRP Self Service Portal | — | — | — |

---

## Attribute Detail Notes

### Maximum Duration
How long an asset can be continuously activated before mandatory rest. When the limit is reached, the TSO marks the next linked bid unavailable for the upcoming MTU. Derived from physical or contractual limits (e.g. reservoir capacity, thermal cycling constraints).

**Supported by:** Energinet, Statnett, Svenska kraftnät

---

### Resting Time
Minimum downtime after deactivation before an asset can be reactivated. The TSO blocks subsequent linked bids for the declared resting period. Derived from physical recovery requirements.

**Supported by:** Energinet, Statnett, Svenska kraftnät

---

### Inclusive Bids
A group of bids that must all be activated together, or none at all. Opposite of an exclusive group. The TSO merges the group into a single bid before forwarding to the AOF. Useful for bundles of small assets (e.g. aggregated DERs) that are only viable as a combined offer.

**Supported by:** Fingrid (v1.2.0), Statnett, Svenska kraftnät

---

### Activation Time (slower than FAT)
Declared by BSPs whose assets cannot achieve the standard 12.5-minute Full Activation Time. The TSO removes these bids from AOF eligibility. They may still be activated outside the AOF in specific circumstances:
- **Energinet:** last resort when standard mFRR bids are insufficient
- **Svenska kraftnät:** congestion management (countertrade / redispatch)

**Supported by:** Energinet, Svenska kraftnät

---

### Faster Activation
Assets capable of responding faster than the standard FAT. Treated as normal bids in scheduled activation. In direct activation, these bids receive priority handling when rapid system response is required.

**Supported by:** Statnett only

---

### Period Shift
Flags a bid as eligible for period shift activation. This process handles structural ramp imbalances at 15-minute boundaries. Runs as a separate process after the main scheduled activation. Bids with this attribute remain eligible for normal scheduled and direct activation as well.
- **Statnett:** implements a dedicated "period shift" tool
- **Svenska kraftnät:** requires BRPs to limit production changes to under 200 MW between MTUs

**Supported by:** Statnett, Svenska kraftnät

---

### Production Type
Mandatory in Denmark. The BSP must declare the generation technology type (hydro, thermal, wind, etc.). Used in Energinet's local pre-processing logic.

**Supported by:** Energinet only (mandatory)

---

### Voluntary Bid Identification
Fingrid-specific flag distinguishing voluntary bids from those submitted under a capacity market obligation. Affects how bids are classified and treated during pre-processing.

**Supported by:** Fingrid only (added v1.2.0)

---

## Summary: What Each TSO Adds Beyond the Common Set

| TSO | National extensions |
|---|---|
| **Energinet (DK)** | Maximum Duration, Resting Time, Activation Time (slow), Production Type (mandatory), Emergency Volumes fallback, local DA model |
| **Fingrid (FI)** | Inclusive Bids, Voluntary Bid Identification, Reserve Power Plants (outside AOF), conditional linking for inclusive bids |
| **Statnett (NO)** | Maximum Duration, Resting Time, Faster Activation, Period Shift, Guaranteed Volume, Disturbance Reserve (non-standard bids), conditional linking for period shift |
| **Svenska kraftnät (SE)** | Maximum Duration, Resting Time, Inclusive Bids, Activation Time (slow), Period Shift, Störningsreserven (outside AOF) |

---

*Source: Nordic mFRR EAM BSP Implementation Guide v1.2.0, September 2025. Nordic Balancing Model programme.*
*Go-live: 4 March 2025.*