# Moat Momentum · Calculation check (Deep-Dive) — design spec

Status: approved 2026-11-04; built and published 2026-11-05 (dashboard version 21). Page numbers: 98.5% of 86,592 values placed.
Example the design copies: the DUOL sheet built by hand on 2026-11-04
(https://docs.google.com/spreadsheets/d/1SWEqjdnbSLG7QcqNHfI8UtU3V3XsV-KY1gHbEbxg52A/edit).

## 1. Purpose

Jitti doubts some Screener numbers. For any company in the Deep-Dive, the reader must be able to:
1. see each measure's formula, the numbers it used and the result, in the dashboard;
2. open a Google Sheet for that one company that recomputes every measure with live formulas from values as filed
   with the SEC, each with its filing, XBRL tag and printed page number.

Success: for every Screener company, the sheet's results equal what the dashboard shows (rounding only), and a
reader can find every input on the named page of the named filing.

Choices already made in chat:
- One sheet per company (Option B layout), built when the reader clicks, not built ahead.
- Scope: the four Moat Screener groups and the three risk checks.
- Page numbers for every SEC value.

## 2. What the reader sees (Deep-Dive, new last section "Calculation check")

**Table, one row per measure** (latest 12-month point):

| Measure | Formula | Numbers used | Result | Line | Side |
|---|---|---|---|---|---|
| G1/G3 X · Revenue growth a year (3 yrs) | (Revenue now ÷ revenue 12 quarters back)^(1/3) − 1 | $1,145.0M, $442.4M | 37.3% | 10% | Above |
| … G1 Y / G4 X clean ROIC, G2 X reinvestment, G2 Y return on new capital, G3 Y gross-margin change, G4 Y earnings yield, interest cover, net debt ÷ EBITDA, operating cash flow ÷ debt | | | | | |

- "Numbers used" shows the dollar inputs, in $M, with the period they cover.
- The lines are the ones currently set on the Screener (they are adjustable there).
- "n/a" and "Not tested" use the same rules and wording as the Screener.
- A short "Building blocks" list under the table: revenue, clean operating income, NOPAT, invested capital, cash,
  debt, EBITDA and enterprise value, each with its one-line formula.
- A note when an input is known to be incomplete (today: held-to-maturity securities not counted as cash, §6).

**Buttons** under the table:
- **Create calculation sheet** — builds the sheet in the reader's own Google Drive (§4). Then the button becomes
  **Open calculation sheet** (link) plus a small **Rebuild** link.
- **Download as Excel** — the same workbook as an .xlsx file, for readers without the Google Drive connector.

## 3. The workbook (three tabs, same as the DUOL example)

1. **Calculation check:** settings (tax rate 21%, operating cash 2% of revenue, the Screener lines, risk thresholds),
   building blocks for now / 4 quarters back / 12 quarters back, each measure with result, "Dashboard shows",
   "Same as dashboard?" (Yes/No, green/red), line, side, formula in words.
2. **SEC inputs:** for every 12-month item: last fiscal year (10-K) + this year to date (10-Q) − same months a year
   earlier, then the total; balance-sheet items at period end; share price and shares. Columns: item, XBRL tag, the
   three points, filing IDs, page in filing. When a point is a 10-K year, the item is one line (the fiscal year).
3. **Sources:** one row per filing (ID, form, period, filed, accession, link to the EDGAR filing index), the Yahoo
   Finance price page, the SEC company-facts JSON, and the dashboard data file.

Rules carried over from the DUOL build: blue = value from a source, black = formula; labels that start with
"+", "−" or "=" are stored as text; every number derived in the sheet is a formula; money in US$, no rounding.

## 4. How the sheet is made

- The page builds the workbook as an .xlsx in the browser (ExcelJS 4.4.0 from cdnjs) from the company's audit record
  (§5), with formulas and formatting.
- **Create calculation sheet:** one call to the reader's Google Drive connector, `create_file`, with the .xlsx as
  `base64Content` and Google conversion on, titled "TICKER · Moat Momentum calculation check (data as of DATE)".
  Google turns it into a Google Sheet and recalculates the formulas. The returned link is shown.
- The link is remembered per reader and company (`db`, under the reader's own private path), together with the data
  date. When the dashboard data is newer, the button offers **Rebuild** first.
- **Download as Excel:** the same .xlsx through the `downloads` capability.
- New capabilities: `mcp` with `{server: "Google Drive", tools: ["create_file"]}`, and `user` (for the reader's id).
  `db` and `downloads` exist already.
- Errors are handled per the connector rules: not connected → "Add Google Drive in claude.ai Settings →
  Connectors"; needs approval → keep the button, say claude.ai asks the first time; reconnect needed → say so;
  an unclear failure after the call → "The sheet may have been created; check your Google Drive", and no automatic
  retry. The table in the dashboard always works, with or without the connector.

## 5. Data: the audit record (new `src/mm_audit.py` → `output/data/audit_data.js`)

For every Screener company (1,870 today), from the same point-in-time fact store and as-of date as the Screener run:
- the three points (now, 4 and 12 quarters back): period end, 10-Q 12-month point or 10-K year;
- for each 12-month item (revenue, gross profit or revenue − cost of revenue, operating income, each one-off tag,
  D&A, operating cash flow, interest): the XBRL tag used and each part (fiscal year, year to date, a year earlier)
  with value, accession and page;
- balance-sheet items (equity, cash tag, each short-term investment and debt tag the tool reads) with the same detail;
- price (Yahoo close and date), shares (cover page or diluted average, with source, ADS ratio and later splits);
- the filings list (form, period, filed date, accession).
Loaded after the page opens, like the company briefs (`defer`), so it does not slow the first view. Size budget:
≤ 8 MB (short keys, values in whole dollars); if it is larger, split the file by CIK range and load the part needed.

**Reconciliation test (the honesty check):** for every company, the measures recomputed from the audit record, in
Python and in the page's JavaScript, equal the Screener's stored values within rounding. The run prints how many
companies match; any company that does not match shows "Does not reconcile, see note" instead of hiding it.

## 6. Page numbers (new `src/mm_pages.py`, background job)

- For each filing used, download the main 10-K / 10-Q document once (SEC, ≤ 10 requests a second), keep only the
  results (`data/cache/mm/pages/<accession>.json`, not the document). About 15,000 documents, a few hours the first
  time; later runs only fetch new filings. Resumable.
- Method: the filings are Inline XBRL, so each number on the page carries its tag name. Split the document at its page
  breaks, read each page's printed number (e.g. "84" or "F-3"), and find the page holding the tagged number with the
  right tag, value and period. The DUOL pages found by text search on 2026-11-04 are the test cases.
- A value that cannot be placed gets "not located" (never a guess) and the filing link still works. The run reports
  the share located; target ≥ 95% of values.

## 7. Known gap shown, not fixed here

Held-to-maturity securities (e.g. Duolingo $133.0M) are not in the tool's cash list. The Deep-Dive note and the sheet
show the amount and a what-if (cash, invested capital, ROIC, earnings yield with it counted). Changing the cash
definition changes every company's results, so it is a separate decision.

**Update 2026-11-05 (round 31):** decided and fixed. Held-to-maturity and available-for-sale lines now count as
cash when no filed total exists, so the note and the what-if block were removed; the short-term investment row lists
the tags actually added.

## 8. Testing

- Python: audit parts add up to the panel's 12-month values for all companies; page finder on small HTML fixtures
  (thousands and millions scale, "F-" pages, a value that appears in the notes before the statement, a missing value).
- JavaScript (Node, as today): the measure calculator matches the Screener values for sample companies; the workbook
  builder's output model has formulas (not typed results) and text labels for "+"/"="; error-code → message mapping.
- In the browser: build DUOL's sheet through the connector and compare with the hand-built example.

## 9. Not in scope

Changing any calculation; the one-tab Option A (it stays in the methodology sheet as built); page numbers for
filings older than the 12-quarter-back point; sharing sheets with other people (each reader builds their own).
