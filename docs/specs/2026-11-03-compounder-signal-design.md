# Moat Momentum v2.0 · Compounder Signal — design spec

Status: design approved by Jitti in chat, 2026-11-03. This file is the written spec for review; no code has changed for v2.0 yet.
Reading copy: `output/compounder_signal_spec.html`.

## 1. Why v2.0

**Objective (Jitti):** find companies that are about to become the next big growth stocks because their moat is improving, and choose the signal by back-testing, not by hand.

Why v1.x does not meet it (measured 2026-11-03 on the 2013–2023 back-test, `data/cache/mm/validation_rows_v1.0.pkl`):

| Problem | Evidence |
|---|---|
| v1.x measured a different outcome ("peer rank kept rising"), not "became a compounder" | 5 of 275 v1.0 shortlist picks met the compounder definition below (1.8%), against 1.1% for the whole universe |
| Weights and rules were set by hand; the back-test only graded them | Shortlist kept improving less often than the rest (27–39% vs ~50%) |
| The score rewards a high level plus a mature 5-year trend, so it picks companies near their peak | Same result; v1.0 shortlist false alarms 38% vs 22% |
| Fiscal-year data is slow; TTM smooths turning points away | v1.2 TTM test: no gain once look-ahead was removed; market CAGR 12.2% vs 15.6% for fiscal years (section 9) |

## 2. Outcome: what a "moat compounder" is

Measured from the screen date over the next 12 quarters, using 12-month (TTM) figures at the screen date and 12 quarters later, and the three fiscal years in between. Every condition must hold:

1. **Scales:** revenue CAGR ≥ 20% a year.
2. **Beats its industry:** revenue CAGR at least 10 percentage points above the median of its peer group (same SIC grouping as v1.x) over the same period.
3. **Steady:** revenue up in each of the 3 years.
4. **Earns its growth:** clean ROIC above the 9% hurdle in at least 2 of the 3 years, and the final ROIC no more than 2 points below the starting ROIC.
5. **Keeps pricing power:** gross margin no more than 2 points lower at the end (skipped when the company does not report gross profit).
6. **Organic:** goodwill added over the 3 years is less than 25% of starting total assets (same threshold as the v1.x goodwill rule).

Companies with no outcome (acquired, delisted, stopped filing) are counted as "no outcome", not as losers, and reported separately, as in v1.x.

Base rate from a first check of conditions 1–5 on annual data: 247 of 22,109 company-years (1.1%), spread across all years (5–36 a year). Energy, mining and utilities are 5% of winners against 13% of the universe, so the industry-relative rule removes most commodity booms. The price-based alternative (top-quintile 3-year return) was rejected because a large share of its winners were commodity and 2020–21 valuation moves.

## 3. Universe and screen dates

- **Universe B (unchanged from v1.x):** US exchange listing (live runs only), at least 5 fiscal years of history, TTM revenue ≥ $100M, SIC outside 6000–6799. No market-value floor, so no price data is used before the final test.
- **Screen dates:** 15 March, 15 May, 15 August, 15 November. Only facts filed on or before the screen date are used (existing point-in-time store).
- **Training:** 2013-03-15 to 2019-11-15 (28 screens). **Test:** 2020-03-15 to 2023-11-15 (16 screens), opened once. The last test outcome ends in late 2026, which is why 2023 is the final test year.

## 4. Signals (fixed before testing)

All calculated per company at each screen date from point-in-time data, then ranked 0–100 within the industry peer group. "Quarter" means the single latest fiscal quarter; Q4 = full year − 9 months year to date.

| # | Theme | Signal | Expected direction |
|---|---|---|---|
| 1 | Value creation | Clean ROIC (TTM) now minus 4 quarters earlier | higher = better |
| 2 | Value creation | Incremental ROIC over the last 4 quarters: Δ NOPAT ÷ Δ invested capital (only when capital grew ≥ 10%) | higher = better |
| 3 | Pricing power | Gross margin, latest quarter minus same quarter a year earlier | higher = better |
| 4 | Pricing power | Gross-margin acceleration: signal 3 now minus signal 3 two quarters earlier | higher = better |
| 5 | Scale | Clean operating margin, latest quarter minus same quarter a year earlier | higher = better |
| 8 | Peers | Revenue growth (latest quarter vs same quarter last year) minus peer median | higher = better |
| 9 | Peers | Revenue-growth acceleration: growth now minus growth two quarters earlier | higher = better |
| 10 | Peers | Peer-rank change over 4 quarters (v1.x peer rank on ROIC, gross margin, operating margin, asset turnover; TTM) | higher = better |
| 11 | Quality | Free-cash-flow margin (TTM) now minus 4 quarters earlier | higher = better |
| 14 | Starting point | Clean ROIC rank vs industry at the screen date | tested both ways; hypothesis: winners start mid-table |

Signals 6, 7, 12, 13, 15 and 16 from the candidate list were not chosen. Keeping the list short lowers the chance of a lucky "discovery".

## 5. Training rule and combination

On training screens only:

1. For each signal, per calendar year: winner rate in the signal's top 10% vs the universe winner rate that year.
2. **Keep** a signal if its top 10% beats the base rate in at least 5 of the 7 training years and the direction matches section 4. For signal 14, the direction that wins in at least 5 of 7 years is kept, and the hypothesis is reported as confirmed or not.
3. **Combine** the kept signals as the equal-weighted mean of their 0–100 ranks: the **Compounder Signal**. No fitted weights.
4. Report every signal's yearly results, kept or not.

Because screens a quarter apart share most companies, results are judged per year, not on pooled counts.

## 6. Success test (pre-registered)

Run once on the test screens after the signal is fixed.

- **Business (main):** the top 10% by Compounder Signal become winners at least **2× the universe base rate** over 2020–2023.
- **Price (reported, not used to choose):** top 25 by Compounder Signal at each screen, equal weight, held one quarter (rebalanced each screen), against the S&P 500 total return, QUAL, the equal-weight universe and the v1.1 shortlist. Same three missing-price cases as v1.x (survivors only, neutral, worst case) and the same bankruptcy masking.
- **If it fails:** the result is published as is. No re-tuning on 2020–2023. Any revised method needs new years (2024 onward screens, as their outcomes arrive) to be tested.

## 7. Product changes (Methodology v2.0)

- **Screener:** ranked by Compounder Signal; shortlist = top 25 (after the existing risk gate: interest cover remove, other rules flag).
- **Deep-Dive:** Compounder Signal and each signal's rank, the 12-quarter charts, today's five-theme Moat Score as context.
- **Scenarios:** individual signals can be switched on or off; theme sliders apply only to the context score. JavaScript mirrors the Python combination, checked for parity as in v1.x.
- **Proof tab:** training table per signal and year, the single test result, the price test, v1.x and the v1.2 TTM experiment as earlier attempts.
- **Also:** Google Sheet tabs, track record (new freeze at v2.0), Methodology page and change log, then the pitch documents.

## 8. Components

| Unit | Does | Depends on |
|---|---|---|
| `mm_quarterly.py` (new) | Single-quarter and TTM rows per company at any screen date, point-in-time | `facts.pkl`, `mm_fundamentals` (TTM builder, clean-up) |
| `mm_signals.py` (new) | The 10 signals and their industry ranks for one screen date | `mm_quarterly`, `mm_score` (peer groups) |
| `mm_outcomes.py` (new) | Compounder label for a company at a screen date | `facts.pkl` (all filings) |
| `mm_discover.py` (new) | Training table, keep rule, combination, the one test, writes `output/data/discovery.json` | the three above |
| `mm_market.py` (extended) | Quarterly-rebalanced price test for the Compounder shortlist | `discovery.json`, Yahoo prices cache |
| `mm_run.py`, web page, Sheet, track (updated) | Live v2.0 | all of the above |

Testing: unit tests with synthetic facts for single-quarter derivation (including Q4), each signal, the outcome label (each of the 6 conditions), and point-in-time behaviour; one check against real filings for 3 companies.

## 9. Today's uncommitted v1.2 TTM work

- **Keep:** TTM builder (`ttm_rows`, `scoring_table`), quarterly facts from 2011, 12-quarter chart, TTM tests.
- **Revert:** live default to v1.1 (`data.ttm: false`, `methodology_version: "1.1"`) and re-run the live outputs until v2.0 ships.
- **Document:** on the Proof tab, as an experiment not adopted:
  - the first back-test showed shortlist hit 36.1% vs 26.9%, but that was look-ahead (the TTM point saw part of the outcome period);
  - with outcomes starting after all data used: hit 34.8% vs 39.0% for fiscal years, false alarm 34.3% vs 27.8%;
  - market test Jul 2013 – Oct 2026: CAGR 12.2% (TTM) vs 15.6% (fiscal years, v1.1 gate) vs 14.3% S&P 500.
- **Remove:** `track_record/2026-11-03_v1.2.json` (never committed or published); the removal is noted in prompts.md.

## 10. Risks and limits

- Winners are about 1% of company-years, so a top-10% group of ~200 companies holds only a few winners per screen; yearly results will be noisy.
- 10-Q figures are unaudited; some tags are missing in 10-Qs more often than in 10-Ks (for example, interest expense is available for 59% of companies on TTM rows vs 65% on fiscal years).
- A pass on 2020–2023 would be one test period that includes an unusual cycle (pandemic, rate rise); the live track record from 2026 onward is the real test.
- Universe B excludes companies with less than 5 years of history, so some early-stage winners are missed by design.
