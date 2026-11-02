---
title: Layer 1 backtest — 10-baggers 2018/2019 → 2023/2024
type: note
created: 2026-11-02
updated: 2026-11-02
tags: [backtest, US, layer1]
sources: [SEC EDGAR XBRL companyfacts API, Yahoo Finance via yfinance]
status: draft
---

# Layer 1 backtest

**Question:** if the Layer 1 score had been run on a past date using only filings public at that time, would its top 100 have contained the stocks that went on to return ≥10x in the next 5 years?

## Method

| Window | As of | Return measured to |
|---|---|---|
| tune | 2019-12-31 | 2024-12-31 |
| holdout | 2018-12-31 | 2023-12-31 |

- Fundamentals: SEC EDGAR XBRL companyfacts, only facts **filed on or before** the as-of date (https://data.sec.gov/api/xbrl/companyfacts/, retrieved 2026-11-02).
- Prices: Yahoo Finance via `yfinance` (https://finance.yahoo.com, retrieved 2026-11-02). Return = adjusted close (splits + dividends). Market cap on the as-of date = actual traded price × SEC cover-page shares.
- Universe: 2,499 US companies that file 10-Qs and are listed today; population = those with a price on both dates.
- Metrics: **hits** = 10-baggers in the top 100; **recall** = hits ÷ all 10-baggers in the population; **precision** = hits ÷ 100; **lift** = precision ÷ base rate (1.0 = no better than random); **5x+** = top-100 names returning ≥5x; **halved** = share of the top 100 that lost ≥50%.

> **Survivorship bias:** companies that went bankrupt, were acquired or delisted before 2026-11-02 are missing. Absolute hit rates and returns are therefore optimistic. The test is still fair for comparing variants, because they all see the same population.

> **Small sample:** only ~25 ten-baggers per window. A difference of 1–2 hits between variants is noise, so the 5x+, median and halved columns (100 names each) matter more than the hit count.

## Findings (2026-11-02)

1. **The score beats random, modestly.** With the current config the top 100 holds 5 (tune) / 4 (holdout) ten-baggers against ~1.5 expected by chance (lift 3.4x / 2.9x). Most 10-baggers are still missed.
2b. **The acquisition penalty (Day 5) helped in both windows** (more 5x+ names): growth bought through acquisitions is not the organic catalyst we are looking for.
2. **Size is the strongest single signal.** Companies under $300M became 10-baggers ~10x more often than $1–10B companies, in both windows (table below). Removing the plausibility/size terms gave the worst results.
3. **About half of all 10-baggers could not be caught on the as-of date.** Their revenue was still shrinking (e.g. NVDA 2019) or they had no revenue yet (biotech). This is the accepted cost of the "quant proof first" rule. Switching the gate off barely changes results, because those companies rank low anyway.
4. **Rebound vs new high is undecided.** Weighting "revenue at a new high" helped one window and hurt the other, so turnarounds stay in and `rev_new_high` stays at 0.
5. **Weights were chosen by looking at both windows, so there is no untouched test period left.** The next honest check is forward tracking of the live shortlist.

**Chosen:** size .15 / plausibility .30 (balanced; picked by Jitti over the higher-hit, higher-blow-up `size_heavy`). Full weights in `config.yaml`.

## Results by weight variant

| Variant | Window | Hits | 10-baggers | Recall | Precision | Base rate | Lift | 5x+ | Median top 100 | Median all | Halved |
|---|---|---|---|---|---|---|---|---|---|---|---|
| config.yaml (current) | tune | 5 | 25 | 20.0% | 5.0% | 1.5% | 3.41 | 13 | 1.77x | 1.39x | 13.0% |
| config.yaml (current) | holdout | 4 | 23 | 17.4% | 4.0% | 1.4% | 2.93 | 15 | 1.78x | 1.62x | 6.0% |
| day3_baseline | tune | 4 | 25 | 16.0% | 4.0% | 1.5% | 2.73 | 11 | 1.57x | 1.39x | 17.0% |
| day3_baseline | holdout | 2 | 23 | 8.7% | 2.0% | 1.4% | 1.47 | 7 | 1.64x | 1.62x | 8.0% |
| new_high | tune | 4 | 25 | 16.0% | 4.0% | 1.5% | 2.73 | 11 | 1.51x | 1.39x | 16.0% |
| new_high | holdout | 4 | 23 | 17.4% | 4.0% | 1.4% | 2.93 | 10 | 1.88x | 1.62x | 9.0% |
| growth_heavy | tune | 4 | 25 | 16.0% | 4.0% | 1.5% | 2.73 | 13 | 1.57x | 1.39x | 13.0% |
| growth_heavy | holdout | 2 | 23 | 8.7% | 2.0% | 1.4% | 1.47 | 9 | 1.87x | 1.62x | 7.0% |
| no_plausibility | tune | 3 | 25 | 12.0% | 3.0% | 1.5% | 2.05 | 9 | 1.37x | 1.39x | 19.0% |
| no_plausibility | holdout | 2 | 23 | 8.7% | 2.0% | 1.4% | 1.47 | 4 | 1.48x | 1.62x | 11.0% |
| growth_only | tune | 4 | 25 | 16.0% | 4.0% | 1.5% | 2.73 | 10 | 1.36x | 1.39x | 20.0% |
| growth_only | holdout | 5 | 23 | 21.7% | 5.0% | 1.4% | 3.67 | 10 | 1.65x | 1.62x | 18.0% |
| plausibility_heavy | tune | 3 | 25 | 12.0% | 3.0% | 1.5% | 2.05 | 12 | 1.77x | 1.39x | 12.0% |
| plausibility_heavy | holdout | 4 | 23 | 17.4% | 4.0% | 1.4% | 2.93 | 14 | 2.20x | 1.62x | 3.0% |
| size_heavy | tune | 5 | 25 | 20.0% | 5.0% | 1.5% | 3.41 | 13 | 1.70x | 1.39x | 16.0% |
| size_heavy | holdout | 3 | 23 | 13.0% | 3.0% | 1.4% | 2.20 | 13 | 1.85x | 1.62x | 6.0% |

Variant weights are listed in `src/backtest.py` (`VARIANTS`); the current choice is in `config.yaml`.

## Does the growth gate (quant proof first) cost 10-baggers?

Same current weights, gate switched off (declining-revenue companies also ranked):

| Window | Hits | 5x+ | Median top 100 | Halved | Lift |
|---|---|---|---|---|---|
| tune | 6 | 15 | 1.74x | 13.0% | 4.09 |
| holdout | 4 | 16 | 1.85x | 6.0% | 2.93 |

## 10-baggers by market cap on the as-of date

| Window | Market cap | 10-baggers | Companies | Rate |
|---|---|---|---|---|
| tune | < $300M | 10 | 218 | 4.6% |
| tune | $300M–1B | 6 | 243 | 2.5% |
| tune | $1–10B | 3 | 610 | 0.5% |
| tune | > $10B | 2 | 359 | 0.6% |
| holdout | < $300M | 10 | 210 | 4.8% |
| holdout | $300M–1B | 4 | 239 | 1.7% |
| holdout | $1–10B | 2 | 573 | 0.3% |
| holdout | > $10B | 2 | 295 | 0.7% |

## Every 10-bagger and where the current score ranked it

### tune (2019-12-31 → 2024-12-31)

| Ticker | 5y return | Rank | Market cap then | TTM rev growth then | Note |
|---|---|---|---|---|---|
| PMTS | 33.2x | 3 | $10M | 10.0% | ranked |
| ESOA | 17.0x | 10 | $11M | 28.8% | ranked |
| LMB | 22.6x | 17 | $29M | 7.5% | ranked |
| TGLS | 10.2x | 63 | $376M | 19.6% | ranked |
| LWAY | 12.5x | 91 | $31M | -12.2% | ranked |
| FTAI | 11.3x | 231 | $1,659M | 92.4% | ranked |
| AR | 12.3x | 249 | $867M | 9.4% | ranked |
| CELH | 16.4x | 377 | $333M | 39.6% | ranked |
| TSLA | 14.5x | 556 | $75,402M | 39.4% | ranked |
| CHRD | 54.4x | 689 | $1,047M | 11.8% | ranked |
| INOD | 34.7x | — | $29M | -3.3% | failed gate: revenue shrinking |
| NVDA | 22.9x | — | $144,004M | -19.4% | failed gate: revenue shrinking |
| GME | 20.6x | — | $401M | -15.9% | failed gate: revenue shrinking |
| MSTR | 20.3x | — | — | -3.8% | failed gate: revenue shrinking |
| BBW | 16.5x | — | $49M | -6.8% | failed gate: revenue shrinking |
| BYRN | 15.2x | — | $20M | 50.0% | failed gate: TTM revenue < $5M |
| MOD | 15.1x | — | $425M | -3.1% | failed gate: revenue shrinking |
| SMCI | 12.7x | — | $1,203M | -7.9% | failed gate: revenue shrinking |
| STRL | 12.0x | — | $390M | -0.1% | failed gate: revenue shrinking |
| RCAT | 11.7x | — | $19M | -54.6% | failed gate: revenue shrinking |
| CLDX | 11.3x | — | $36M | -60.4% | failed gate: revenue shrinking |
| CLS | 11.2x | — | — | — | not scorable: no_revenue_ttm |
| SMMT | 11.2x | — | $257M | — | not scorable: no_revenue_ttm |
| CAPR | 10.8x | — | $5M | -4.5% | failed gate: revenue shrinking |
| VRT | 10.3x | — | — | — | not scorable: no_revenue_history |

### holdout (2018-12-31 → 2023-12-31)

| Ticker | 5y return | Rank | Market cap then | TTM rev growth then | Note |
|---|---|---|---|---|---|
| LFMD | 11.8x | 8 | $6M | 66.6% | ranked |
| AEHR | 18.8x | 20 | $31M | 33.0% | ranked |
| QXO | 10.5x | 66 | $10M | 13.7% | ranked |
| LMB | 12.4x | 98 | $28M | 7.9% | ranked |
| BLDR | 15.3x | 112 | $1,252M | 13.0% | ranked |
| ENPH | 27.9x | 218 | $503M | 2.2% | ranked |
| HDSN | 15.2x | 538 | $38M | 33.9% | ranked |
| SMTI | 13.7x | 554 | $7M | 17.9% | ranked |
| NVDA | 15.0x | 633 | $81,435M | 38.4% | ranked |
| CELH | 47.1x | 810 | $177M | 41.4% | ranked |
| TSLA | 11.2x | 874 | $57,153M | 62.9% | ranked |
| ELF | 16.7x | 880 | $418M | 2.2% | ranked |
| CHRD | 42.7x | 972 | $1,761M | 76.4% | ranked |
| ATLX | 41.7x | — | $165M | 29.6% | failed gate: TTM revenue < $5M |
| LEU | 32.2x | — | $15M | -5.0% | failed gate: revenue shrinking |
| AXSM | 28.2x | — | $84M | — | not scorable: no_revenue_ttm |
| SMCI | 20.6x | — | $672M | — | not scorable: stale |
| EU | 14.6x | — | — | — | not scorable: no_revenue_ttm |
| LPG | 13.4x | — | $322M | -4.4% | failed gate: revenue shrinking |
| CLDX | 13.2x | — | $34M | — | not scorable: quarter_gap |
| CYTK | 13.2x | — | $346M | -52.5% | failed gate: revenue shrinking |
| ATLC | 10.6x | — | $56M | — | not scorable: no_revenue_ttm |
| ELA | 10.6x | — | $12M | -5.4% | failed gate: revenue shrinking |

