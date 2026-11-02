---
title: 10-Bagger Catalyst Watchlist Scanner — Phase 1 (US)
owner: Jitti
status: draft
updated: 2026-11-02
---

# Spec

## 1. Goal · What decision this supports

Pick a shortlist of 10–20 companies for my key watchlist that have a realistic path to **10x in 5 years** because of a *new* catalyst (new TAM, new S-curve, turnaround, new market), found from evidence in the numbers rather than from general news that most investors already follow.

Long-term scope: USA, Hong Kong, Thailand, Singapore, Japan, Taiwan. **Phase 1 = USA only** (best data coverage; other markets follow as separate phases).

## 2. Material questions

1. **Is there a measurable inflection now?** Revenue growth accelerating, gross/operating margin turning up, operating income or FCF turning from negative to positive.
2. **Is the inflection caused by something new** (segment, product, market, turnaround) rather than a normal cycle?
3. **Is 10x arithmetically plausible?** 10x market cap implies a required revenue CAGR at a reasonable sales multiple. A $50B company needs a $500B outcome, so size is a soft penalty, not a hard cap.
4. **Is it under-followed?** If everyone already owns the story, the edge is gone.

Evidence rule: a catalyst counts only when **the numbers already show it** (Q1). Management statements and transcripts can confirm (Q2) but never trigger. Accepted trade-off: we enter after 1–2 quarters of visible inflection, not before.

## 3. Trust sources

| Source | Used for questions | Notes |
|---|---|---|
| SEC EDGAR — XBRL `companyfacts` API (data.sec.gov) | 1, 3 | Numeric backbone. Free, public, citable URL per number, filing dates allow point-in-time backtests, includes later-delisted companies |
| SEC EDGAR — 10-K / 10-Q / 8-K filings | 2 | Layer 2 catalyst review, quoted briefly with link |
| Company IR (earnings call transcripts, investor decks) | 2 | Confirmation only |
| StockAnalysis screener CSV export | 3, 4 | **Local only** (`data/private/`), paid data, never committed |
| GuruFocus screener CSV export | 4 | **Local only** (`data/private/`), insider / guru activity, never committed |
| Yahoo Finance via `yfinance` | backtest | Price history to identify 2019→2024 10-baggers |

Rule: every number has a source URL and retrieval date. If not found, leave blank and say so. No guessing.

## 4. Output

Two layers:
- **Layer 1 (quant):** score all US stocks on Q1 + Q3 (+ Q4 where data allows) → top ~100.
- **Layer 2 (AI reads filings):** classify the catalyst type for the top ~100 with short quotes + filing links → shortlist 10–20.

Files: `output/dashboard.html` (ranked table, signal scores, catalyst type, click-through to source) · `output/shortlist.csv` · backtest report.

## 5. Success criteria

- [x] Backtest as of 2019-12-31: report recall (share of 2019→2024 10-baggers that land in the top ~100) and precision among survivors, with survivorship bias stated openly. → `output/backtest_report.md` (final config: recall 20%, precision 5%, lift 3.4x; holdout 2018 window 13% / 3% / 2.3x)
- [x] Point-in-time check: the 2019 run uses no fact filed after 2019-12-31. → `tests/test_edgar_asof.py`
- [x] For 3 sample tickers, every signal value matches the cited EDGAR filing. → `src/verify_filings.py`: DERM, TRT, AAPL, 19/19 inputs (revenue, cost of revenue, gross profit, operating income, cash flow, capex, diluted shares) found in the filing text; kept as `tests/test_filing_values.py`. Earlier: 2019 revenue for AAPL, NVDA, LWAY.
- [x] Current run produces a shortlist of 10–20 names, each with catalyst type + linked evidence. → `output/shortlist.csv`: 20 names in two tiers (A = 1 confirmed, B = 19 watch); every quote verified verbatim against the SEC filing.
- [x] No paid data, transcript text or token in the public repo. → Checked every round before commit; tracked CSVs are SEC-derived only, `data/` and `.env` are gitignored. GuruFocus was not needed in Phase 1.
