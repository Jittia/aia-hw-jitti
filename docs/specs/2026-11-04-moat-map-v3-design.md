# Moat Momentum v3.0 · Moat Map and Expectation Gap — design spec

Status: design approved by Jitti in chat, 2026-11-04. Written spec for review; no v3.0 code yet.
Reading copy: `output/moat_map_v3_spec.html`. Based on the framework review `output/signal_framework_review.pdf` (stages 1 and 3; stages 2, 4 and 5 out of scope).

## 1. Goal

- **Stage 1 · Financial momentum:** is the business getting better? One visual signal, the **Moat Map** (clean ROIC above the hurdle against revenue growth, with each company's trail), instead of more settings.
- **Stage 3 · Expectation gap:** is the improvement already priced in? Compare the growth the share price implies with the growth the company is delivering.
- **Product rule:** v1.1 stays the main ranking and v2.0 stays an experimental list. v3.0 adds a view, columns and lists. It replaces nothing unless a later test supports it.

## 2. Positions on the Moat Map

At each date, for each company, using only filings made on or before that date (existing point-in-time store) and 12-month figures (TTM: the latest 10-Q or 10-K; `mm_quarterly.ttm_panel`).

| Item | Definition |
|---|---|
| x · revenue growth | 3-year revenue growth a year = (revenue TTM now ÷ revenue TTM 12 quarters earlier)^(1/3) − 1; missing if the earlier revenue is missing or ≤ 0 |
| y · return above hurdle | clean ROIC (TTM, `roic_ttm`) − 9% |
| Industry median x | median x of universe companies in the same industry group (v1.x SIC grouping) at that date |
| **Top-right ("Compounder")** | x ≥ 10% **and** y ≥ 0 **and** x > industry median x |
| Other quadrants (chart labels only) | "Profitable, slow" (y ≥ 0, x < 10%); "Growing, below hurdle" (y < 0, x ≥ 10%); "Neither" (y < 0, x < 10%) |
| Distance to the corner d | max(0, 10% − x) + max(0, −y), in percentage points (0 inside the corner) |
| Trail | x and y at the same quarter 1, 2, 3, 4 and 5 years earlier (period ends matched within ±20 days) |

The chart line is drawn at x = 10% and y = 0 for every view. The industry-median condition applies to the signal only, and the Deep-Dive marks the industry median with a second, dashed line.

## 3. Movement rules (fixed before any run)

"A year earlier" = the company's point 4 quarters earlier. A rule needs both points; companies without the earlier point are not in it.

| Rule | Definition |
|---|---|
| **R1 Entered** | top-right now and not top-right a year earlier |
| **R2 Moving toward** | not top-right now; x and y both higher than a year earlier; d fell by at least 5 points over the year; d now ≤ 10 points |
| **R3 Improving and not priced in** | (R1 or R2) and Expectation Gap > 0; companies with no gap are excluded |

**Rule list** = every universe company meeting the rule at that date.
**Top 25** = the 25 from the rule list that pass the existing v1.1 risk gate (no Remove rule hit), ranked by distance moved (d a year earlier − d now), highest first; ties broken by y, highest first.

## 4. Valuation and Expectation Gap

| Item | Definition |
|---|---|
| Market value | price × shares outstanding from the latest filing cover page (dei), else diluted shares; hidden if below 0.2% or above 200× of revenue TTM (existing `mm_valuation` sanity check) |
| Price | **Back-test:** Yahoo Finance adjusted close at the last month-end **before** the date. **Live:** Yahoo Finance close of the previous trading day, retrieved on the run date |
| EV | market value + debt (including finance leases) − cash and short-term investments, from the latest filing's balance sheet (same definitions as invested capital) |
| EV/Sales | EV ÷ revenue TTM |
| EV/clean EBIT | EV ÷ clean operating income TTM; none if ≤ 0 |
| Clean P/E | market value ÷ clean net income TTM; none if ≤ 0 |
| FCF yield | FCF TTM ÷ market value |

**Reverse DCF (implied growth g):**
- R₀ = revenue TTM; m = clean operating margin TTM × (1 − 21%); ROIC = clean ROIC TTM.
- For years t = 1…10: FCF_t = R₀(1+g)^t × m × (1 − g ÷ ROIC).
- Terminal: FCF₁₁ = R₁₀ × 1.03 × m × (1 − 0.03 ÷ ROIC); terminal value = FCF₁₁ ÷ (9% − 3%).
- Value(g) = Σ FCF_t ÷ 1.09^t + terminal value ÷ 1.09^10.
- **Implied g** = the first g, scanning upward from −20% to +60% in steps of 0.1 point, at which Value(g) − EV changes sign, refined by linear interpolation between the two steps.
- **None ("n/a")** when clean operating income ≤ 0, ROIC ≤ 0, EV ≤ 0, or there is no sign change in the range.
- **Expectation Gap** = x − implied g. Positive means the company has grown faster than the price assumes.

Fixed assumptions, shown on the page: horizon 10 years, discount rate 9%, terminal growth 3%, tax 21%.

## 5. Leading items (shown, not tested)

| Item | SEC tags (first present) | Shown as |
|---|---|---|
| Backlog (remaining performance obligations) | RevenueRemainingPerformanceObligation | growth over 4 quarters vs revenue growth |
| Deferred revenue | ContractWithCustomerLiability (+ …Current), DeferredRevenue, DeferredRevenueCurrent | growth over 4 quarters vs revenue growth |
| R&D intensity | ResearchAndDevelopmentExpense (existing tag list) | R&D TTM ÷ revenue TTM |
| Capex intensity | PaymentsToAcquirePropertyPlantAndEquipment / …ProductiveAssets (existing) | capex TTM ÷ revenue TTM |

Coverage of today's universe (read on 2026-11-04 from the bulk file retrieved 2026-11-03): backlog 37% (none before 2018), deferred revenue 82% (31% back to 2014), R&D 54%, capex 97%. The page shows each item's live coverage. A missing item is shown as "not reported", never as zero. These items do not enter R1–R3 or the test.

## 6. Test (rules above fixed; nothing tuned)

- **Dates:** quarterly, 2021-03-15 to 2023-08-15 (11 dates). These are the dates with a full 3-year outcome. There is no training period, because the rules have no fitted parameters.
- **Universe:** universe B as in v1.1/v2.0 back-tests (no exchange filter in the past).
- **Winner:** the existing moat-compounder label (`mm_outcomes.label`, as fixed on 2026-11-04). Missing data means "no outcome".
- **Pass (each of R1, R2, R3, on the whole rule list):**
  - its compounder rate ≥ 2.0× the rate of the rest of the universe, pooled over the 11 dates; **and**
  - higher than the rest in each screen year 2021, 2022 and 2023.
- **Reported, not deciding:**
  - top-25 lists;
  - v1.1 (top 10% by Moat Score, and top 25 after the risk gate) and v2.0 (top 10% and top 25 by Compounder Signal) on the same 11 dates and measure;
  - 12-month share return from the month-end after each date against the S&P 500 total return, for dates 2021-03-15 to 2025-08-15, top 25 equal weight, with the three missing-price cases (survivors, neutral, worst);
  - share of each rule list still top-right 4 quarters later (dates to 2025-08-15);
  - results without COVID rebounds (revenue TTM more than 20% below its best of the previous 8 quarters).
- **If a rule fails:** published as failed in the Proof tab; nothing is re-tuned on these years. The Moat Map view still ships as a description.
- **Output:** `output/data/v3_test.json`; track record `track_record/<as_of>_v3.0.json` with today's top 25 of R1, R2 and R3.

## 7. Product

- **Screener:** new tab "Moat Map (v3.0)" next to Early Moat, Proven Leaders, Strict Risk and Compounder.
  - **Scatter** of the universe, or one industry chosen in a dropdown. Lines at x = 10% and y = 0 and labelled quadrants. Axes capped at the 2nd and 98th percentiles, with outliers pinned to the edge and marked.
  - **Dot colour** = Expectation Gap: green above 0, red below 0, deeper colour as the gap grows, capped at ±20 points; grey when there is no gap. **Dot size** = market value (square root, 3–12 px).
  - **Interaction:** hover shows the name, x, y, gap and quadrant. Click shows the 5-year trail and opens a link to the Deep-Dive.
  - **Filter chips:** All · R1 · R2 · R3 · "Improving and gap positive" (= R3).
  - **Table below the chart:** quadrant, movement (R1/R2), x, y, distance moved, EV/Sales, EV/clean EBIT, P/E, FCF yield, implied growth, gap, market value. Sortable, with the existing industry and market-value filters.
  - **Box above the chart:** what the view shows, and the v3.0 test result once it exists (pass/fail first).
- **Deep-Dive:** a Moat Map card with the company's 5-year trail against its industry's current dots, the valuation block (EV, multiples, implied growth, gap, assumptions), and the leading items with "not reported" where missing.
- **Terminology:** plain-language entries for Moat Map, the four quadrants, R1–R3, EV and the multiples, reverse DCF, implied growth and Expectation Gap.
- **Proof:** a v3.0 section: pass or fail per rule first, then the comparison with v1.1 and v2.0, the reported results and every miss.
- **Methodology:** v3.0 change-log row and the fixed assumptions.
- **spec.md:** §3 notes that Yahoo prices are now also used for the Expectation Gap (a valuation view), never inside the Moat Score.
- **Sheet:** `output/sheet/moatmap.csv` and a "Moat Map (v3.0)" tab importing it.
- **Sources:** every number carries its source and date: SEC EDGAR (bulk retrieved date) and Yahoo Finance (close date, retrieved date).
- **Checks:** the page is checked in the browser in light, dark and phone width (375 px, no horizontal page scroll) before it is called done.

## 8. Components

| Unit | Does | Depends on |
|---|---|---|
| `mm_moatmap.py` (new) | x, y, quadrant, industry median, distance, trail, R1/R2 for one date | `mm_quarterly.ttm_panel`, `mm_signals`/`mm_score` (universe, industry group, gate) |
| `mm_revdcf.py` (new) | implied growth and gap for given inputs | none (pure function) |
| `mm_valuation.py` (extended) | EV and multiples; point-in-time market value at a date | prices cache, cover shares, `ttm_panel` |
| `mm_extract.py` (extended) | deferred revenue and backlog facts → `data/cache/mm/leading.pkl` | bulk companyfacts |
| `mm_v3_test.py` (new) | the test in section 6 → `v3_test.json` | the units above, `mm_outcomes`, discovery rows (v1.1/v2.0 comparison), prices |
| `mm_run.py`, `mm_track.py`, `mm_sheet_payload.py`, `mm_proof.py`, web page (updated) | live v3.0 data, freeze, Sheet, Proof, views | all of the above |

Testing: unit tests for x/y/quadrant (including the industry-median condition), distance, R1/R2/R3 edge cases (missing earlier point, exact thresholds), the reverse DCF (a hand-checked case, the n/a cases, the scan picking the first root), EV and multiples with missing items, and the point-in-time price (month-end before the date).

## 9. Limits

- 2021–2023 is one period; dates a quarter apart share most companies, so results are judged per year.
- The 3-year growth at 2021 dates still compares with pre-COVID years, and 12-month figures in 2021 include the rebound; the rebound check is reported.
- The reverse DCF is simple on purpose: one margin, one ROIC, fixed rates. It describes what the price implies under those assumptions, not a fair value.
- Yahoo prices miss many companies that no longer trade; returns are bounded with the three cases.
- Leading items are not tested; backlog has no history before 2018.
