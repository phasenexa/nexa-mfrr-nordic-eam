# Task: Add GS tax price calculator and technical link ordering utilities

## Summary

Add two utility modules to `nexa-mfrr-nordic-eam`:

1. A resource rent tax (Grunnrenteskatt / GS tax) price adjustment calculator for Norwegian mFRR bids
2. A technical link ordering utility that assigns link IDs to a set of bids following the PowerDesk convention

Both should include Jupyter notebook examples in `examples/`.

---

## 1. GS Tax Price Calculator

### Background

Norwegian hydro generators are subject to a resource rent tax (Grunnrenteskatt, commonly called "GS tax"). The Nordic regulator requires that BSPs should not make more money in mFRR than is possible in the day-ahead auction. The tax is defined as a proportion of the day-ahead price, and mFRR bid prices must account for it.

This means bid prices are not static per tier. They vary per MTU because the day-ahead price varies per MTU.

### Formula

```text
bid_price = tier_price + tax_rate * (DA_price - tier_price)
```

Where:

- `tier_price` is the base price the trader has set for this bid tier (EUR/MWh)
- `DA_price` is the day-ahead price for this specific MTU (EUR/MWh)
- `tax_rate` is the resource rent tax rate as a decimal (e.g. 0.59 for 59%)

### Clamping rules

After applying the formula, the resulting bid price must be clamped:

- **Up bids**: bid price must be >= DA price (a trader should never offer upward regulation below the market clearing price)
- **Down bids**: bid price must be <= DA price (a trader should never offer downward regulation above the market clearing price)
- **Statnett price limits**: bid price must be within -9,999 to +9,999 EUR/MWh (pre-MARI) or -14,999 to +14,999 EUR/MWh (post-MARI). Use the MARI mode from config to determine which limits apply. Note: these are slightly inside the official -10,000/+10,000 and -15,000/+15,000 limits to avoid boundary issues.
- **Price granularity**: round to 2 decimal places (0.01 EUR granularity per the implementation guide)

### Where to put it

Create a new module: `src/nexa_mfrr_eam/pricing.py`

### Public API

```python
from nexa_mfrr_eam.pricing import gs_adjusted_price, gs_adjust_bids

# Single price calculation
adjusted = gs_adjusted_price(
    tier_price=185.00,
    da_price=131.73,
    tax_rate=0.59,
    direction=Direction.UP,
)
# Returns: 185.00 + 0.59 * (131.73 - 185.00) = 185.00 + 0.59 * (-53.27) = 185.00 - 31.43 = 153.57
# Clamped: max(153.57, 131.73) = 153.57 (already above DA price, no clamp needed)

# Batch adjustment for a list of built bids
adjusted_bids = gs_adjust_bids(
    bids=my_bids,           # list of BidTimeSeriesModel
    da_prices=da_series,    # dict mapping MTU start (datetime) to DA price (Decimal)
    tax_rate=0.59,
)
# Returns new BidTimeSeriesModel instances with adjusted prices
# Original bids are not mutated
```

The `gs_adjusted_price` function should:

- Accept `tier_price: Decimal | float`, `da_price: Decimal | float`, `tax_rate: Decimal | float`, `direction: Direction`
- Optionally accept `mari_mode: MARIMode | None` (defaults to global config) for price limit clamping
- Return `Decimal` rounded to 2 decimal places
- Raise `ValueError` if `tax_rate` is not between 0 and 1

The `gs_adjust_bids` function should:

- Accept a list of `BidTimeSeriesModel` and a dict of DA prices keyed by MTU start datetime
- Return a new list of `BidTimeSeriesModel` with adjusted prices
- Raise `KeyError` if a bid's MTU is not found in the DA prices dict
- Not mutate the input bids

### Edge cases to handle

- DA price is negative (can happen during high wind/solar, e.g. -50 EUR/MWh). The formula still applies. For up bids, the clamp to >= DA price may result in a negative bid price.
- tier_price equals DA price: formula returns tier_price (no adjustment). This is correct.
- tax_rate is 0: formula returns tier_price unchanged. This is correct (non-Norwegian generators).
- tax_rate is 1: formula returns DA_price. This is an extreme case but mathematically valid.
- The formula can produce a price that violates Statnett limits (e.g. very high DA price with high tax rate). Clamp to the MARI-mode-dependent limits.

### Tests

Add tests in `tests/test_pricing.py`:

- Basic up bid calculation with known values
- Basic down bid calculation with known values
- Clamping: up bid where formula result < DA price
- Clamping: down bid where formula result > DA price
- Clamping: result exceeds Statnett price limits (both pre-MARI and post-MARI)
- Edge case: negative DA price
- Edge case: tax_rate = 0 (passthrough)
- Edge case: tax_rate = 1 (returns DA price)
- Edge case: tier_price == DA_price
- Batch function: multiple bids across different MTUs
- Batch function: missing DA price raises KeyError
- Rounding to 2 decimal places
- ValueError for tax_rate outside 0-1

### Re-export

Add `gs_adjusted_price` and `gs_adjust_bids` to `__init__.py` re-exports.

---

## 2. Technical Link Ordering

### Background

PowerDesk assigns technical links to all bids, not just those that need double-activation protection. The link ordering follows specific rules that encode the multipart price stack hierarchy across time. These rules come from internal PowerDesk documentation (not the official implementation guide).

### Rules

1. **All bids should have a technical link.** Every bid in the portfolio gets a link ID.

2. **Technical link IDs are UUIDs.**

3. **For upward bids from a given set of generators**: the lowest-priced bid always gets the first technical link. Additional links are added in order of increasing price. So if you have 3 up tiers at 145, 185, and 225 EUR/MWh, the 145 tier gets TL1, 185 gets TL2, 225 gets TL3.

4. **For downward bids from a given set of generators**: the highest-priced bid always gets the first technical link. Links are added in order of decreasing price. So if you have 3 down tiers at 40, 20, and 10 EUR/MWh, the 40 tier gets TL1, 20 gets TL2, 10 gets TL3.

5. **Links are ordered by price rank (position in the sorted tier list), not by price value.** If prices change across QHs (e.g. due to GS tax adjustment making prices unique per period), the same link ID follows the same tier position. The 2nd-cheapest up bid in QH1 and the 2nd-cheapest up bid in QH2 share the same link ID, even if their actual prices differ.

6. **Gaps are allowed.** Technical links do not have to be continuous across time. If a bid exists in QH1 and QH3 but not QH2, the same link ID is used for QH1 and QH3.

7. **Technical links can span multiple days.** A link ID used at the end of one delivery day can continue into the next.

8. **Within an MTU, each link ID is used by exactly one bid** (per the implementation guide rule: technical link IDs must be unique within an MTU).

### Where to put it

Create a new module: `src/nexa_mfrr_eam/link_ordering.py`

### Public API

```python
from nexa_mfrr_eam.link_ordering import assign_technical_links

# Input: a list of built bids (BidTimeSeriesModel) that share the same
# resource/bidding zone and need technical links assigned.
# Bids should NOT already have linkedBidsIdentification set.

linked_bids = assign_technical_links(
    bids=my_bids,
    direction=Direction.UP,
)
# Returns new BidTimeSeriesModel instances with linkedBidsIdentification populated.
# Bids at the same price rank across MTUs share the same link UUID.
# Original bids are not mutated.
```

The function should:
- Accept `bids: list[BidTimeSeriesModel]`, `direction: Direction`
- Group bids by MTU (using the bid's period time interval start)
- Within each MTU, sort bids by price (ascending for UP, descending for DOWN)
- Assign a consistent link UUID to each price rank position across all MTUs
- Return new `BidTimeSeriesModel` instances with `linked_bids_identification` set
- Raise `ValueError` if any bid already has a `linked_bids_identification` set (to prevent double-assignment)
- Raise `ValueError` if bids within the same MTU have duplicate prices (ambiguous ordering)

### Algorithm

```
1. Group bids by MTU start time
2. Determine the maximum number of price tiers across all MTUs
3. Generate that many UUIDs (one per rank position)
4. For each MTU:
   a. Sort bids by price (ascending for UP, descending for DOWN)
   b. Assign link_uuid[rank] to each bid at position rank
5. Return new bid instances with the assigned link IDs
```

### Example

Input: 6 bids across 3 MTUs, 2 price tiers each, direction UP

```
QH1: [50 EUR 20MW, 80 EUR 15MW]
QH2: [53 EUR 20MW, 83 EUR 15MW]   (prices differ due to GS adjustment)
QH3: [48 EUR 20MW, 78 EUR 15MW]
```

Output: 2 link UUIDs generated. UUID-A assigned to rank 0 (cheapest), UUID-B to rank 1.

```
QH1: [50 EUR 20MW link=UUID-A, 80 EUR 15MW link=UUID-B]
QH2: [53 EUR 20MW link=UUID-A, 83 EUR 15MW link=UUID-B]
QH3: [48 EUR 20MW link=UUID-A, 78 EUR 15MW link=UUID-B]
```

### Edge cases

- Single bid per MTU: still gets a link ID (rule: all bids should have a technical link)
- Bids only exist in some MTUs (gaps): link IDs are still consistent by rank for the MTUs where bids exist
- Different number of tiers per MTU: the MTU with fewer tiers simply doesn't use the higher-rank link IDs. This is valid.
- Down bids: sorting is reversed (highest price first gets rank 0)

### Tests

Add tests in `tests/test_link_ordering.py`:

- Basic up bid ordering: 2 tiers across 3 MTUs, verify same rank shares same link ID
- Basic down bid ordering: verify reverse sort
- Single tier: every bid gets a link
- Gaps in MTUs: link IDs consistent across non-consecutive MTUs
- Uneven tiers: MTU1 has 3 tiers, MTU2 has 2 tiers
- GS-adjusted prices (different prices per MTU but same rank): verify consistent linking
- ValueError when bids already have links
- ValueError when duplicate prices within same MTU
- Verify link IDs are valid UUIDs

### Re-export

Add `assign_technical_links` to `__init__.py` re-exports.

---

## 3. Jupyter Notebook: GS Tax Price Adjustment

Create `examples/gs_tax_pricing.ipynb`

This notebook should demonstrate:

1. **The problem**: Show a simple scenario with a Norwegian hydro generator that has 3 upward price tiers (e.g. 145, 185, 225 EUR/MWh) and a tax rate of 0.59 (59%). Show the day-ahead prices for a series of MTUs (use realistic NO2 prices, e.g. ranging from 80-160 EUR/MWh across 12 MTUs).

2. **Single price calculation**: Use `gs_adjusted_price` to calculate one adjusted price step by step, showing the formula and the result.

3. **Batch adjustment**: Build a set of simple bids using the `Bid` builder for the 12 MTUs and 3 tiers (36 bids total). Use `gs_adjust_bids` to adjust all prices. Display a before/after comparison table.

4. **Clamping in action**: Show a period where the DA price is high enough that the formula would produce a bid price below the DA price for an up bid, and demonstrate the clamp.

5. **Down bid example**: Show one or two down bid tiers with the same tax rate to demonstrate the reversed clamping logic.

Use markdown cells to explain each step. Keep it concise. Use a simple dict for DA prices (no need to fetch real data).

You may also need to adjust @examples/statnett_bid_preparation.ipynb as it contains price adjustment logic and may benefit from this new code if applicable? Use your best judgement.

---

## 4. Jupyter Notebook: Technical Link Ordering

Create `examples/technical_link_ordering.ipynb`

This notebook should demonstrate:

1. **The problem**: Explain that the implementation guide says technical links prevent double-activation, but in practice all bids should have technical links assigned following a consistent ordering convention. Explain the rules briefly.

2. **Basic example**: Create 3 upward price tiers for a single resource across 4 consecutive MTUs (12 bids). Prices are static (same per MTU). Use `assign_technical_links` and show the resulting link assignments in a table grouped by MTU and sorted by price.

3. **GS-adjusted prices**: Take the same 12 bids but apply GS tax first (so prices differ per MTU). Then apply `assign_technical_links`. Show that the link assignment is the same (by rank) even though the actual prices differ across MTUs.

4. **Down bids**: Create 2 downward price tiers across 3 MTUs. Apply `assign_technical_links` with `Direction.DOWN` and show the reversed ordering.

5. **Gaps**: Show a scenario where a bid tier only exists in QH1 and QH3 (not QH2). Demonstrate that the link ID is consistent across the gap.

6. **Full workflow**: Combine GS tax adjustment and technical link ordering into a single pipeline: build bids -> adjust prices -> assign links -> build document -> serialize to XML. Show the final XML snippet for one MTU to prove the `linkedBidsIdentification` element is populated.

Use markdown cells to explain each step. Reference the technical link rules document as the source of the ordering convention.

---

## General notes

- Follow the existing code style and conventions documented in CLAUDE.md
- All new public functions need Google-style docstrings
- Use `Decimal` for all price calculations (not float) to avoid rounding errors
- New modules should be type-checked with mypy strict
- Run `make ci` before considering the task complete
- Update the implementation status table in README.md to reflect the new modules
- Update CLAUDE.md module layout section to include the new modules
