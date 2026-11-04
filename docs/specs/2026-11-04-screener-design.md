# Moat Momentum · Screener (four 2×2 groups) — design spec

Status: design agreed with Jitti in chat, 2026-11-04. Written spec for review; no code yet.
Reading copy: `output/screener_spec.html`.

## 1. Purpose

A screening tool in the **Action** group: narrow the universe to a short list worth a Deep-Dive.
1. Remove companies with weak debt or interest-paying capacity (risk pre-screen).
2. Look at the remaining companies through four 2×2 groups, each answering one question about the moat.
3. Compare the groups and keep the companies that show up in several.

**It is not a tested signal.** None of the four groups has been back-tested in our data. The page says so, and links to the Proof tab for what has been tested. Scenarios (Evaluation) keeps the tested methods unchanged. The site opens on the Screener once it ships.

## 2. Data

- **Basis:** live run only (no back-test).
- **Figures:** 12-month figures (TTM) from each company's latest 10-Q or 10-K (`mm_quarterly.ttm_panel`), and the points at the previous 4 quarter-ends (matched within ±20 days).
- **Prices:** Yahoo Finance close of the previous trading day for "now" (existing `prices_daily`). For past quarter-ends: the Yahoo month-end close of that quarter's last month, with later splits undone (`split_factor_after`), × cover-page shares filed by then (`cover_at`).
- **Universe:** today's universe (Scenarios universe B: US-listed, revenue ≥ $100M, ≥ 5 years, not finance).
- **Missing values:** a company with a missing value is left out of that chart and that group's lists only. The page shows how many were left out.

## 3. Section 1 · Master filter (applies to every section below)

- **Market value:** chips, several may be chosen.
  - Mega ≥ $200B · Large $10–200B · Mid $2–10B · Small $300M–2B · Micro < $300M · Not available
  - None chosen = all.
- **Industry:** a searchable list of SIC industries with company counts. Several may be ticked. "Clear" resets to all.
- **Count:** a line shows how many companies remain.

## 4. Section 2 · Risk pre-screen

| Check | Formula (12 months) | Default | Reference (linked in Terminology) |
|---|---|---|---|
| Interest cover | clean operating income ÷ interest expense | ≥ 3.0× | Damodaran, interest coverage ratio → synthetic rating table (NYU Stern, updated yearly) |
| Net debt ÷ EBITDA | (debt − cash) ÷ (clean operating income + depreciation & amortisation) | ≤ 3.0× | S&P Global Ratings, *Corporate Methodology: Ratios and Adjustments* (core leverage ratio table) |
| Operating cash flow ÷ debt | cash from operations ÷ total debt | ≥ 20% | Same S&P table (FFO/debt; operating cash flow used as the FFO proxy) |

**How companies are treated:**
- **Net cash** (cash ≥ debt) passes the two debt checks.
- **Net debt with EBITDA ≤ 0** fails the net-debt check.
- **No debt** passes the cash-flow-to-debt check.
- **Debt but no interest tagged:** "not tested" for interest cover. Kept by default, with a setting to remove these instead.

**Controls:**
- each value is editable (number box);
- a switch, **Filter** / **Not filter** (default Filter);
- **Reset to defaults**.

**Counts:** removed by each check, not tested, and remaining. The groups below use the remaining companies when Filter is on.

## 5. Section 3 · Four 2×2 groups (one under another)

Each group shows:
- **Header:** the two measures and its question.
- **Remark** (lighter text): the reference.
- **Chart** (scatter, the existing Moat Map drawing):
  - lines labelled, quadrant names shown;
  - outliers pinned at the edge and marked, axes capped at the 2nd and 98th percentiles;
  - dot size = market value; no colour coding (one neutral colour, top-right dots in the accent colour).
- **Clicking a dot:**
  - shows its name and values next to the dot;
  - the **side box** (right of the chart; below it on a phone) shows the company's current values and quadrant, plus a 5-point trend table: now and 1–4 quarters back, both measures, all 12-month figures;
  - the box links to the Deep-Dive.
- **Three lists under the chart (25 each):**
  1. **Now in the top-right.** Ranked by the average of the two measures' percentile ranks (0–100 among companies shown).
  2. **Improving fastest toward the top-right on the Y axis.** Already right of the X line, below the Y line, Y rose over the last 4 quarters (> 0). Ranked by the rise in Y.
  3. **Improving fastest toward the top-right on the X axis.** Already above the Y line, left of the X line, X rose over the last 4 quarters (> 0). Ranked by the rise in X.

  Each list row: company, X, Y, change over 4 quarters, market value; click → Deep-Dive.

| Group | Question | X axis (line) | Y axis (line) | Reference |
|---|---|---|---|---|
| **1 · Value creation: ROIC vs growth** | Is growth creating value right now? | 3-year revenue growth a year (10%) | clean ROIC − 9% (0) | Koller, Goedhart & Wessels, *Valuation* (McKinsey & Company), value matrix |
| **2 · Compounding runway: reinvestment vs return on new capital** | Can it keep compounding? | Reinvestment rate = (invested capital now − 4 quarters earlier) ÷ NOPAT (50%) | Return on new capital = (NOPAT now − 12 quarters earlier) ÷ (invested capital now − 12 quarters earlier), only when capital grew ≥ 10% (9%) | Mauboussin & Callahan, "Measuring the Moat" (Credit Suisse, 2013; updated 2016) |
| **3 · Pricing power: gross-margin change vs growth** | Is pricing power rising while it grows? | 3-year revenue growth a year (10%) | Gross margin now − 4 quarters earlier, in points (0) | Novy-Marx (2013), "The other side of value", *Journal of Financial Economics* |
| **4 · Good and cheap: Magic Formula** | Is it a good business at a cheap price? | Return on capital = clean ROIC (median of all companies with both values) | Earnings yield = clean operating income ÷ EV (median of all companies with both values) | Greenblatt (2005), *The Little Book That Beats the Market* |

**Notes:**
- **Group 2:** NOPAT ≤ 0 → no reinvestment rate. Capital growth below 10% → no return on new capital (about 40% of companies have one); the count is shown.
- **Group 4:** the medians are fixed for the day (computed on the whole universe), so the lines do not move while filtering. Greenblatt's return on capital uses net working capital + net fixed assets; ours is the clean ROIC used everywhere else, stated in the remark. EV ≤ 0 → no earnings yield.

## 6. Section 4 · Overlap

- **Selector:** ① Now in the top-right · ② Improving fastest on Y · ③ Improving fastest on X.
- **Table:** every company in the chosen list of any group:
  - company;
  - number of groups (1–4);
  - which groups (badges);
  - average percentile rank;
  - market value;
  - link to the Deep-Dive.
- **Sorting:** by number of groups, then average rank. Column headers can re-sort.

## 7. Terminology

New entries, each with a plain-language explanation, formula, default threshold and a **link to the source**:
- the three risk checks (Damodaran; S&P core ratios);
- Groups 2, 3 and 4 (Mauboussin & Callahan; Novy-Marx; Greenblatt).

Group 1 already has its Moat Map entry; it gains a link to the McKinsey *Valuation* book page. Every link is opened and checked during the build. A source that has no stable public page is cited without a link and says so.

## 8. Product rules

- **Labels and sources:** plain-language labels. Every number carries its source and date: SEC EDGAR bulk retrieved date; Yahoo close date.
- **Browser checks:** light, dark and 375 px phone width (no horizontal page scroll); no console errors.
- **Out of scope:** Scenarios, Proof and Track record do not change. No Sheet tab, no freeze, no back-test (not requested).

## 9. Components

| Unit | Does |
|---|---|
| `mm_screener.py` (new) | For each company: risk measures; the 4 groups' X/Y now and at the previous 4 quarter-ends; changes over 4 quarters; Group 4 medians; percentile ranks. Writes a `scr` block into `site_data.js` |
| `mm_run.py` (updated) | Calls it in the live run |
| `output/moat_momentum.html` (updated) | Screener view: master filter, risk pre-screen, 4 group sections (scatter + side box + 3 lists), overlap section; Terminology entries; site opens on Screener |

**Testing:**
- unit tests for each group's X/Y formulas, the 4-quarter changes, the three list rules (including the "already right of / above the line" conditions), the risk checks with net cash / no interest / negative EBITDA, and the past-quarter earnings yield (split undone, shares as filed then);
- browser checks of filtering, the risk switch, dot click, side box and overlap ranking.
