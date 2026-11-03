---
title: Catalyst-of-Change Radar — Phase 1.5 (US)
owner: Jitti
status: draft
updated: 2026-11-02
---

# Spec (v2, Phase 1.5)

> v1 (Phase 1, rounds 1–7) was a one-date ranking aimed at 10x. It worked only modestly and found 1 confirmed catalyst,
> so it was reworked. What v1 taught us, in numbers, is in `prompts.md` rounds 1–7 and the "Why v2" note at the end.

## 1. Goal · What decision this supports

Keep a watchlist of companies where a **catalyst of change** (new TAM, new S-curve, turnaround, new market) has just
become visible in their own filings, early enough that **≥5x in 5 years** (≈38%/yr) is still ahead. Names whose story
could stretch to **10x** get a flag. The tool runs every quarter and moves each company through stages:
**Radar → Emerging → Confirmed** (or **Broken**). Scope: USA first; Taiwan next (Phase 2).

## 2. Material questions

1. **Has something changed, and when did it become public?** A change event in the numbers (revenue acceleration,
   margin step-up, profit/FCF turning positive, contracted revenue jumping) or in filings (insider cluster buying,
   officer change, material agreement), dated by its SEC filing date.
2. **Is it the company or the cycle?** Growth must beat the industry median, be organic (not bought through
   acquisitions) and not be a one-off.
3. **Does it persist?** Two consecutive quarters of the numbers holding = Confirmed.
4. **Is 5x (or 10x) arithmetically plausible?** Size and the revenue growth required at a reasonable sales multiple.
5. **Did this kind of event lead to ≥5x more often than the base rate in the past?** (event study, 2012→2021)

**Evidence rule (two-key):** any event can put a company on Radar; only numbers can promote it to Emerging or
Confirmed. Management statements and transcripts can raise an alarm or confirm, never promote on their own.

## 3. Trust sources

| Source | Used for questions | Notes |
|---|---|---|
| SEC EDGAR XBRL `companyfacts` (data.sec.gov) | 1, 2, 3, 4 | Numeric backbone; earliest filing per period = what was known then |
| SEC EDGAR submissions index + 10-K/10-Q/8-K documents | 1, 2 | 8-K item codes; MD&A and earnings releases for the AI review (verbatim quotes) |
| SEC Insider Transactions Data Sets (Form 3/4/5, sec.gov) | 1 | Open-market purchases (code P) by insiders, quarterly bulk files 2012→ |
| Yahoo Finance via `yfinance` | 4, 5 | Month-end prices 2012→, market cap = price × SEC shares |
| Stock Analysis screener CSV | 2 | **Local only.** Universe and industry classification (for the industry median) |
| GuruFocus transcripts | 1 (Phase 1.6) | **Local only**, not used in 1.5 |

Rule: every number has a source URL and retrieval date. If not found, leave blank and say so. No guessing.

## 4. Output

- `output/dashboard.html`: stage view (Confirmed / Emerging / Radar), "new this quarter", per-company event timeline
  with SEC links, the event-study results.
- `output/watchlist.csv`: Confirmed + Emerging names with stage, events, catalyst type, verbatim evidence, links, `stretch_10x`.
- `output/event_study_report.md`: forward 5-year results per event type and per stage vs base rate.

## 5. Success criteria

- [x] Event study over events known 2012-12 → 2021-10: thresholds chosen on 2012–2017 events, reported on 2018–2021
      (holdout) separately; per event type and stage: count, hit rate ≥5x / ≥10x / ≥3x, median, share halved, lift vs base.
      → `output/event_study_report.md`
- [ ] Emerging and Confirmed show a **holdout lift ≥ 1.5x** for ≥5x outcomes. **Partly met:** Confirmed 1.68x
      (8.7% reached ≥5x vs 5.1% base), Emerging 1.43x. Radar alone 0.99x (no edge; it is a logbook).
- [x] Point-in-time: no quarter, event or stage uses anything filed after its date. → `tests/test_events.py`
      (NVDA quarter known only from its 10-Q date; known_date > quarter end for every row; events are onsets)
- [ ] Live watchlist: every Confirmed/Emerging name has ≥1 dated event with an SEC link and a code-verified quote.
      **Partly met:** all names have dated events with SEC links; the 26 Tier A names have code-verified quotes
      (161/162 AI quotes verified); most of the 38 Tier B names are not AI-read yet (by design: AI reads at Confirmed).
- [x] No paid data, transcript text or token in the public repo. → `output/watchlist.csv` and the dashboard hold only
      SEC- and Yahoo-derived values; screener industry labels stay local.

## Why v2 (from Phase 1)

- 10x in 5y is ~1.4% of stocks (~25 events per test window), which is too few to tune on. 5x is ~5–6%, and 13–15% in v1's top 100.
- About half of the 10-baggers looked bad on a single as-of date. Watching every quarter catches changes as they surface.
- 32 of v1's top 100 were industry cycles and 16 were growth bought through acquisitions. The industry-median filter
  and the acquisition flag address that.
