---
title: Moat Momentum — Phase 1 (US, SEC EDGAR)
owner: Jitti
status: draft for approval (step 2 ★)
methodology: v1.0-draft (locked before the final validation run)
updated: 2026-11-03
---

# Spec · Moat Momentum

> **Strengthening moats, found in the filings.**
> Source brief: "PROJECT BRIEF — Moat Momentum v4" (2026-11-03). This spec is the short, buildable version of it.
> Replaces the catalyst-of-change radar (kept in `archive/` and git tag `phase1.5-catalyst-radar`).
> Why it was replaced, with numbers: `prompts.md` round 9.

## 1. Goal · What decision this supports

Find US-listed companies whose **competitive moat is strengthening**, proven with audited numbers from SEC filings,
before they are recognised leaders. Output: a short, high-confidence shortlist (**20–30 names**), each with a
Deep-Dive page, ready for a Phase 2 qualitative review (transcripts, leadership, business model).
Business performance first, risk second, qualitative later. **No valuation** in the score.

Product framing: a research tool sold by subscription and as data/signal licensing. Not advice, not a fund.

## 2. Material questions

1. **Is the company creating more value per dollar of capital, and is that improving?** (clean ROIC − hurdle, trend, incremental ROIC)
2. **Is it gaining pricing power?** (gross margin level / trend / stability, gross profit ÷ assets)
3. **Is scale starting to work for it?** (incremental operating margin, SG&A ÷ revenue falling, asset turnover)
4. **Is it pulling away from its industry peers?** (growth vs SIC-peer median, change in peer rank)
5. **Is the profit real and can it be reinvested?** (FCF ÷ clean net income, accruals, reinvestment × incremental ROIC)
6. **Is any of this a false alarm?** Risk gate first: leverage, interest cover, distress (Altman), manipulation (Beneish), dilution, SBC, acquisition-driven growth.
7. **Does the signal work?** Point-in-time re-runs 2013–2023: did flagged companies keep improving more than unflagged peers, and how often did they deteriorate (false-alarm rate)?

## 3. Trust sources

| Source | Used for | Notes |
|---|---|---|
| SEC EDGAR `companyfacts` (bulk `companyfacts.zip` + API) | Q1–7 | Every value with form, period, filing date and accession number; original and restated values both kept |
| SEC EDGAR `submissions` (bulk `submissions.zip` + API) | universe, SIC, filing links | SIC code = industry; 10-K / 10-Q / 8-K links for Deep-Dive and Phase 2 |
| SEC `company_tickers_exchange.json` | universe | Ticker ↔ CIK ↔ exchange |
| Academic / practitioner papers (cited, not data) | method | Mauboussin "Measuring the Moat"; McKinsey "Valuation"; Novy-Marx (2013); Sloan (1996); Piotroski (2000); Mohanram (2005); Altman; Beneish (1999) |
| Price data for market validation (6B) | Q7 market test only | **Not chosen yet** — options proposed at step 6, you decide. Never in the moat score |

Rules: every number has a source URL (filing) and retrieval date; missing = blank and flagged, never guessed.
No licensed data (Stock Analysis, GuruFocus) in this tool — the old universe file is no longer used.
SEC fair access: User-Agent on every request, ≤10 requests/s, back-off on 429/503, cache everything.

## 4. Output

| Output | Where | Notes |
|---|---|---|
| Google Sheet "Moat Momentum" | Google Drive | Settings, Universe, Clean Data (summary), Risk Gate, Theme Scores, Observations, Ranking, Phase 2 Hand-off, Scenarios, Glossary, Validation, Track Record |
| Web page (one self-contained HTML) | `output/moat_momentum.html` | Tabs: Screener, How it works, Learn, Scenarios, Proof, Track Record, Methodology, Demo. Light/dark, mobile |
| Deep-Dive pages (one HTML each, exportable) | `output/deepdive/<TICKER>.html` | Sections A–I of the brief |
| Proof report | Proof tab + `output/proof.html` | Fundamental validation, robustness, honest misses |
| Track record | `track_record/` (git) | Frozen shortlist + settings + SHA-256 fingerprint per official run |
| Brand guide | `output/brand_guide.html` | Built first, approved before styling the rest |
| Pitch pack | Google Docs / Slides | Whitepaper, deck, one-pager — numbers only from validation outputs |

Disclaimer on every output: research tool, not investment advice; past results do not guarantee future results.

## 5. Success criteria (= brief §13)

- [ ] Full US universe screened with 5–10 years of history, data-confidence tags, instant adjustable re-rank, shortlist with Deep-Dive pages.
- [ ] Fundamental validation 2013–2023 with hit rate and false-alarm rate; robustness checks; market validation done or clearly scoped.
- [ ] Live track record running with frozen, fingerprinted shortlists.
- [ ] All tabs complete; automated tests pass; spot-check of 10 companies × 3 years vs 10-Ks passes.
- [ ] Whitepaper, deck and one-pager drafted with numbers from validation.
- [ ] One brand across web page, Sheet, Slides, Docs and exports.

## 6. Method summary (defaults; every one adjustable and versioned)

- **Universe:** US-listed (ticker on an SEC exchange list), files 10-K/10-Q, latest 10-K within 18 months, revenue ≥ $100M,
  ≥ 5 fiscal years, SIC not 6000–6799. Foreign filers (20-F/40-F) out for Phase 1.
- **History:** up to 10 fiscal years (10-K) + last 12 quarters (10-Q) → TTM. Non-December year ends handled.
  Point-in-time store keeps first-filed and restated values; analysis uses latest, validation uses only what was filed by each date.
- **Clean-up:** one-offs removed where the filing tags them (impairments, restructuring, asset-sale gains/losses, litigation);
  tax normalised; unmapped tags flagged; confidence High/Medium/Low per company.
- **Risk gate → 5 themes → Moat Score → confirmation (≥ 3 of 5 themes improving)**, all as in brief §5,
  percentiles within SIC industry (4-digit → 3 → 2 until ≥ 8 peers). Blend 70% improving / 30% level.
  Weights: Value creation 25, Pricing 20, Scale 15, Peers 20, Quality & runway 20.

## 7. Points I need you to confirm (unclear or my proposal)

1. **Tax rate: one constant 21% for all years** (not 35% before 2018). A real rate change in 2018 would create a fake
   ROIC jump in every company's trend. Adjustable in Settings.
2. **Altman Z: the book-equity version (Z'') for all companies.** The original Z needs market value, and EDGAR has no prices.
   Z'' is the published variant for non-manufacturers and private firms.
3. **Missing data in risk checks = "not tested", never Remove.** E.g. Beneish needs 8 items over 2 years; if ≥ 3 are missing,
   the check is skipped and data confidence drops. No debt → interest-cover check passes.
4. **Operating leases left out of invested capital for the trend** (they appear in XBRL only from 2019, which would break
   10-year trends); shown as a second ROIC "with leases" in the Deep-Dive. Finance leases count as debt.
5. **Hurdle rate 9% for every sector in v1.0;** per-sector values can be set in Settings later.
6. **Sheet vs web page:** the Python engine computes everything and writes it to the Sheet; the web page is one HTML file
   carrying the same run's data, so re-ranking is instant and works offline. Saved scenarios live in the Sheet and are
   copied into the page at each run. (A page reading the Sheet live would need the Sheet to be public.)
7. **Public repo:** this repo is public (course homework). Code, method and results will be visible to anyone.
   Whitepaper and deck live in your Google Drive, not in the repo.
8. **One-offs that are not tagged** in XBRL (only described in the text) cannot be removed automatically in Phase 1;
   they lower data confidence instead.

## 8. Plan to Wednesday 2026-11-04 21:00 (stops ★ need your approval)

| Order | Step | Status |
|---|---|---|
| 1 ★ | Review old project: reuse + false-alarm diagnosis | done 2026-11-03 |
| 2 ★ | This spec | **waiting for you** |
| 2b ★ | Brand guide | next |
| 3 ★ | Data history + cleaning → risk gate → scoring → Sheet → screener → Deep-Dive → Learn / How / Scenarios | |
| 4 ★ | Spot-check 10 companies × 3 years vs 10-Ks | |
| 5 ★ | Fundamental validation 2013–2023 + robustness | |
| 6 ★ | Price-data options for market validation | |
| 7 | Start live track record | |
| 8 | Proof, Track Record, Methodology, Demo tabs | |
| 9 ★ | Pitch pack | |

If time runs short, the priority is 1 → 5 and 7 (a working, tested, validated screener with honest results);
market validation (6) and the pitch pack (9) are then submitted as scoped drafts and finished after Wednesday.
