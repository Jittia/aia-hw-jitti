# Calculation check (Deep-Dive) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** For every Screener company, the Deep-Dive shows each measure's formula, inputs and result, and builds a one-company Google Sheet (or .xlsx download) that recomputes every measure from SEC values with filing, tag and printed page.

**Architecture:** Python exports one audit record per company (`output/data/audit_data.js`), built from the same fact store, as-of date and live market values as the Screener, with every 12-month figure split into its filed parts. A separate resumable job (`src/mm_pages.py`) finds each part's printed page in the Inline XBRL filing and caches it. The page computes the measures from the record (pure JS, tested in Node), turns the record into a workbook model, renders it with ExcelJS, and sends the .xlsx to the reader's Google Drive connector (`create_file`, converted to a Google Sheet) or offers it as a download.

**Tech Stack:** Python 3 / pandas (existing), unittest; plain JS in `output/moat_momentum.html`, Node for tests; ExcelJS 4.4.0 (cdnjs, loaded on first click); artifact capabilities `mcp`, `user`, `db`, `downloads`.

**Spec:** `docs/specs/2026-11-04-calculation-check-design.md`

## Global Constraints

- No calculation in the tool changes. Every refactor keeps `ttm_panel` output identical (existing tests stay green).
- Every number shown has a source: filing (form, period, filed, accession, EDGAR link), XBRL tag, printed page or "not located"; price = Yahoo Finance close and date. Never a guessed page.
- Sources only from `spec.md` Trust sources: SEC EDGAR for company data, Yahoo Finance for prices.
- Workbook: blue = sourced value, black = formula; every derived number is a formula; labels starting with "+", "−" or "=" are text; US$ unrounded.
- Sheet title: `TICKER · Moat Momentum calculation check (data as of DATE)`.
- Connector manifest: `{server: "Google Drive", tools: ["create_file"]}`; one call per click, never on load, no automatic retry of the write.
- `audit_data.js` ≤ 8 MB, loaded with `defer` like `brief_data.js`.
- Repo is public: no keys, tokens or personal data in any file. Commits only when Jitti says save (AGENTS.md): each task ends with the full test run instead of a commit.
- Page copy in English; no investment-advice wording.
- Tests: `.venv/bin/python -m unittest discover -s tests` (151 today) must stay green after every task.

## Review Focus

1. A company whose latest point is a 10-K year (no year-to-date parts): items show one fiscal-year line and still reconcile. Test in Task 2.
2. Missing or unusable inputs (no point 12 quarters back, average invested capital ≤ 0, NOPAT ≤ 0, capital grew < 10%): the page and the sheet say "n/a" exactly where the dashboard does. Test in Task 5.
3. ADS tickers and splits after the share-count date (BeOne ONC 13 per ADS, AMCR reverse split): the shares line shows the ratio and split factor, and EV matches the dashboard. Test in Task 3.
4. Debt built from several tags (LongTermDebt missing → noncurrent + current; DebtCurrent rule; finance leases inside LongTermDebtAndCapitalLeaseObligations) and impairment chosen as the max of alternatives: the "used" parts sum exactly to the panel value. Test in Task 2.
5. A reader without the Google Drive connector, who declines approval, or whose call fails ambiguously: the table still renders, Download is offered, the message names the fix, and nothing retries the write. Test in Task 7.

---

### Task 1: Keep the filed parts of every 12-month figure

**Files:**
- Modify: `src/mm_fundamentals.py:139-176` (`ttm_rows`)
- Test: `tests/test_audit.py` (new)

**Interfaces:**
- Produces: `ttm_parts(k: pd.DataFrame) -> pd.DataFrame` in `mm_fundamentals.py`, one row per (cik, tag, end) for 10-Q flow facts with columns `cik, tag, end, ttm, a_val, a_accn, a_start, a_end, val, accn, start, p_val, p_accn, p_start, p_end` (`ttm` = `a_val + val − p_val`, or `val` for `POINT_TAGS`). `ttm_rows` calls it; its output is unchanged.

- [ ] **Step 1: Write the failing tests**

```python
class TtmParts(unittest.TestCase):
    def test_parts_add_up_and_keep_filings(self):  # DUOL revenue, 12 months to 30 Jun 2026
        k = known_as_of(pd.read_pickle(FIX / "duol_facts.pkl"), "2026-11-03")
        r = ttm_parts(k).query("tag == 'RevenueFromContractWithCustomerExcludingAssessedTax' and end == '2026-06-30'").iloc[0]
        self.assertEqual((r.a_val, r.val, r.p_val, r.ttm), (1037589000, 590421000, 483008000, 1145002000))
        self.assertEqual((r.a_accn, r.accn, r.p_accn), ("0001628280-26-012494", "0001628280-26-053603", "0001562088-25-000168"))

    def test_ttm_rows_unchanged(self):
        k = known_as_of(pd.read_pickle(FIX / "duol_facts.pkl"), "2026-11-03")
        pd.testing.assert_frame_equal(ttm_rows(k), pd.read_pickle(FIX / "duol_ttm_rows_before.pkl"))
```

Fixtures: `tests/fixtures/duol_facts.pkl` (DUOL rows of `facts.pkl`, ~100 KB) and `duol_ttm_rows_before.pkl` (saved from the current `ttm_rows` before the refactor).

- [ ] **Step 2: Run** `.venv/bin/python -m unittest tests.test_audit -v` — Expected: FAIL, `ttm_parts` not defined.
- [ ] **Step 3: Implement `ttm_parts`** by moving the two `merge_asof` steps out of `ttm_rows`, carrying `accn`/`start`/`end` of the annual and prior parts through the merges (`a_accn`, `p_accn`, …).
- [ ] **Step 4: Run** the new tests and the whole suite — Expected: all pass.

### Task 2: Audit record per company (`src/mm_audit.py`)

**Files:**
- Create: `src/mm_audit.py`
- Test: `tests/test_audit.py`

**Interfaces:**
- Consumes: `ttm_parts` (Task 1); `TAG_PRIORITY`, `RAW`, `known_as_of` from `mm_fundamentals`; `ttm_panel` rows; `lag_q` from `mm_quarterly`.
- Produces:
  - `points(panel_c: pd.DataFrame) -> dict` → `{"now": row, "q4": row|None, "q12": row|None}` using `lag_q` matching (±20 days), exactly the rows `group_series` uses.
  - `item_parts(k_c, parts_c, metric: str, end, is_ttm: bool) -> dict` → `{"tag": str|None, "parts": [{"kind": "FY"|"YTD"|"PRIOR"|"POINT"|"BAL", "val": float, "accn": str, "start": str|None, "end": str}], "value": float|None}`; the tag is the first in `TAG_PRIORITY[metric]` present for that end, as `_derive` picks it.
  - `debt_parts(w_row: pd.Series) -> list[dict]` and `oneoff_parts(w_row) -> list[dict]`: every candidate tag with `val`, `sign` (+1/−1) and `used: bool`, mirroring `_derive` (LongTermDebt else noncurrent + current/DebtCurrent; leases unless inside LongTermDebtAndCapitalLeaseObligations; impairment = the max alternative; gains subtracted).
  - `company_record(cik, k_c, parts_c, panel_c, live_row, price, price_date) -> dict` with keys `cik, ticker, end, pts{now,q4,q12: {end, ttm}}, items{revenue, gross_profit|cogs, op_income, oneoffs, da, cfo, interest, equity, cash, st_invest, debt, htm}, mkt{price, date, shares, shares_src, ads_ratio, split_factor, mcap, ev}, filings{accn: {form, period, filed}}`.

- [ ] **Step 1: Write the failing tests**

```python
def test_duol_record_matches_hand_built_sheet(self):
    rec = company_record(1562088, ...)  # fixtures from Task 1 plus live row {price: 128.0, shares: 50080000}
    rev = rec["items"]["revenue"]["now"]
    self.assertEqual([p["val"] for p in rev["parts"]], [1037589000, 590421000, 483008000])
    self.assertEqual(rec["items"]["equity"]["q12"]["parts"][0]["val"], 596405000)
    self.assertEqual(rec["items"]["htm"]["now"]["parts"][0]["val"], 132979000)  # shown, not used (spec §7)
    self.assertEqual(rec["mkt"]["shares_src"], "diluted")

def test_10k_point_has_one_fy_part(self):  # Review Focus 1
    # a company whose latest row is a 10-K year (pick from panel: is_ttm False at latest end)
    self.assertEqual([p["kind"] for p in item["parts"]], ["FY"])

def test_used_debt_and_oneoff_parts_sum_to_panel_for_all_companies(self):  # Review Focus 4
    # over the full panel at 2026-11-03: sum(sign*val for used parts) == panel debt / one_offs (abs diff < 1)
```

The all-company test reads `data/cache/mm/facts.pkl` and is skipped when it is missing (as other cache-backed tests are).

- [ ] **Step 2: Run** — Expected: FAIL, module missing.
- [ ] **Step 3: Implement** the four functions. `htm` reads `DebtSecuritiesHeldToMaturityAmortizedCostAfterAllowanceForCreditLossCurrent` (shown only, never used in a measure).
- [ ] **Step 4: Run** the tests and the suite — Expected: pass.

### Task 3: Recompute and reconcile; export `audit_data.js`

**Files:**
- Modify: `src/mm_audit.py`, `src/mm_run.py:286-290` (after `screener_block`), `.gitignore` (add `data/cache/mm/pages/`)
- Test: `tests/test_audit.py`

**Interfaces:**
- Consumes: Task 2; `scr` from `screener_block`; live `mmap` rows (`price` from `daily`, `cover_shares`, `shares`, `mcap`, `ev`, ticker with "." → "-").
- Produces:
  - `recompute(rec: dict, tax: float, cash_pct: float) -> dict` → `{"g1": [x, y], "g2": [x, y], "g3": [x, y], "g4": [x, y], "ic", "nd", "cd"}` using the formulas in spec §2/§3 (same "n/a"/None rules as `group_series` and `risk_measures`).
  - `build(tpanel, facts, mmap, daily, scr, as_of, settings, pages: dict) -> dict` → `{"meta": {as_of, price_date, sec_retrieved, tax, cash_pct, n, reconciled}, "co": {cik: rec | rec + {"recon": False, "diff": {...}}}}`.
  - `mm_run.main` writes `output/data/audit_data.js` as `window.MM_AUDIT = …;` and prints `audit: N companies, M reconcile, size X MB`.

- [ ] **Step 1: Write the failing tests**

```python
def test_recompute_duol(self):
    m = recompute(duol_rec, 0.21, 0.02)
    self.assertAlmostEqual(m["g1"][0], 0.3730, 4); self.assertAlmostEqual(m["g1"][1], 0.9184, 4)
    self.assertAlmostEqual(m["g2"][0], 1.8796, 4); self.assertAlmostEqual(m["g2"][1], 0.5072, 4)
    self.assertAlmostEqual(m["g3"][1], 0.0067, 4); self.assertAlmostEqual(m["g4"][1], 0.0300, 4)
    self.assertAlmostEqual(m["nd"], -6.83, 2); self.assertIsNone(m["ic"]); self.assertIsNone(m["cd"])

def test_ads_and_split_shares(self):  # Review Focus 3: ONC shares divided by 13; AMCR split after count date undone
def test_export_size_under_8mb(self):  # after a run: output/data/audit_data.js < 8_000_000 bytes
```

- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** `recompute` and `build`; reconcile each company against `scr["co"][cik]` (4-dp values within 0.0001, `nd` within 0.01); unmatched companies are kept with `recon: False` and the differing measures.
- [ ] **Step 4: Run** `.venv/bin/python src/mm_run.py` — Expected: the audit line prints; reconciled ≥ 99% of companies (investigate any systematic mismatch before going on; record the count in the ledger). Then the suite passes.

### Task 4: Page numbers from Inline XBRL (`src/mm_pages.py`)

**Files:**
- Create: `src/mm_pages.py`
- Test: `tests/test_pages.py`, fixtures `tests/fixtures/ixbrl_mini.htm`

**Interfaces:**
- Produces:
  - `split_pages(html: str) -> list[tuple[str, str]]` — split at `page-break-after/before: always` and `break-before/after: page`; label = the page's last short line matching `^(?:[A-Z]-)?\d{1,3}$` (e.g. "84", "F-3"), else "".
  - `contexts(html: str) -> dict[str, tuple[str|None, str]]` — `xbrli:context` id → (start or None, end/instant); contexts with a segment (dimensions) are left out.
  - `locate(pages, ctx, tag: str, value: float, start: str|None, end: str) -> str|None` — first page holding `ix:nonFraction name="us-gaap:<tag>"` whose context has that period and whose value (text × 10^scale, `sign="-"` negative) equals `value` within 0.5 × 10^scale.
  - `run(needed: dict[str, list[tuple]], cache: Path) -> None` — per accession: fetch the main document (index → row of type 10-K/10-Q, as in the DUOL check), write `cache/<accn>.json` = `{"tag|start|end": label|null}`; skip accessions already cached; SEC throttle from `SecClient`.
  - CLI: `.venv/bin/python src/mm_pages.py` reads `output/data/audit_data.js`, collects every (accn, tag, start, end, val), runs, prints located share.
  - `mm_audit.build` reads the cache into each part's `page` ("" when not cached, `null` when not located).

- [ ] **Step 1: Write the failing tests** on `ixbrl_mini.htm` (three pages labelled "6", "7", "F-3"; a revenue cell with `scale="3"`, a negative operating loss with `sign="-"`, the same tag with a dimensional context on page 6, the plain context on page 7):

```python
def test_locate_statement_page(self): self.assertEqual(locate(P, C, "Revenues", 590421000, "2026-01-01", "2026-06-30"), "7")
def test_negative_value(self): self.assertEqual(locate(P, C, "OperatingIncomeLoss", -13384000, "2023-01-01", "2023-06-30"), "7")
def test_dimensional_context_ignored(self): ...  # the segment-member cell on page 6 is not returned
def test_f_page_label(self): ...  # "F-3"
def test_not_found_is_none(self): self.assertIsNone(locate(P, C, "Revenues", 1, "2026-01-01", "2026-06-30"))
```

Plus a network test (skipped unless `MM_NET=1`): the DUOL pages found on 2026-11-04 — F2 revenue "84", F1 cash "6", F1 diluted shares "22", F3 cash flow "9".

- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** with the standard library `html.parser`-free regex approach used in `mm_brief` (documents are large; avoid building a DOM).
- [ ] **Step 4: Run** tests (and `MM_NET=1` once) — Expected: pass.
- [ ] **Step 5: Start the full job in the background** (`run_in_background`), then rerun `src/mm_run.py` when it finishes. Expected: located ≥ 95%; record the share and the most common miss in the ledger.

### Task 5: Measures and calculation table in the Deep-Dive

**Files:**
- Modify: `output/moat_momentum.html` (new `<script src="data/audit_data.js" defer onload="onDataLoaded()" onerror="…">` next to `brief_data.js`; new functions; `viewDeep` adds the section before the back links)
- Test: `tests/test_screener_js.py` (add the new functions to the extracted list)

**Interfaces:**
- Consumes: `MM_AUDIT.co[cik]` (Task 3), the Screener's current lines (`SCR.meta.lines` as modified by the line controls) and risk thresholds.
- Produces (top-level `function`s so the test harness can extract them):
  - `auditMeasures(a, tax, cashPct) -> {blocks: {rev:[now,q4,q12], coi, nopat, cash, xcash, debt, ic, gm:[now,q4], ebitda, nd, mcap, ev}, m: {g1x, g1y, g2x, g2y, g3y, g4y, ic, nd, cd}}` — same rules as `recompute` (None where Python gives None).
  - `ddCalcRows(a, lines, thr) -> [{k, label, formula, used: [[label, value, period]], res, line, side}]` for the 9 rows in spec §2.
  - The section HTML "Calculation check": table, "Building blocks" list, the held-to-maturity note when `a.items.htm` has a value, the reconcile note when `a.recon === false`, and the two buttons (wired in Task 7). "Loading…" until `MM_AUDIT` arrives.

- [ ] **Step 1: Write the failing tests**

```python
def test_measures_match_screener_for_sample(self):  # 50 random CIKs from audit_data.js: |js - SCR.co value| <= 1e-4
def test_na_rules(self):  # Review Focus 2: no q12 point -> g1x/g2y null; avg IC <= 0 -> g1y null; NOPAT <= 0 -> g2x null;
                          # capital grew < 10% -> g2y null; side "No point" for null
def test_duol_rows(self): # row g1x: formula text "(Revenue now ÷ revenue 12 quarters back)^(1/3) − 1", res 0.3730, side "Above"
```

- [ ] **Step 2: Run** `.venv/bin/python -m unittest tests.test_screener_js -v` — Expected: FAIL.
- [ ] **Step 3: Implement** the functions and the section, styled with the existing card/table classes.
- [ ] **Step 4: Run** the suite — Expected: pass.

### Task 6: Workbook model and .xlsx

**Files:**
- Modify: `output/moat_momentum.html`
- Test: `tests/test_screener_js.py`

**Interfaces:**
- Consumes: Task 5 `auditMeasures`, `ddCalcRows`; record fields from Task 3.
- Produces:
  - `auditWorkbook(a, meta, lines, thr, dash) -> {title, sheets: [{name, rows: Cell[][], widths, formats}]}` with `Cell = {v: number|string} | {f: string} | null`; sheets "Calculation check", "SEC inputs", "Sources" laid out as the DUOL example (spec §3), including the page column and, when present, the held-to-maturity what-if.
  - `async xlsxBytes(model) -> Uint8Array` — loads ExcelJS 4.4.0 from `https://cdnjs.cloudflare.com/ajax/libs/exceljs/4.4.0/exceljs.min.js` on first use (script injection, cached promise), applies fonts, blue/black colours, number formats, header fills.

- [ ] **Step 1: Write the failing tests** (Node, model only):

```python
def test_results_are_formulas(self):  # every cell in Calculation check column "Result" is {f}
def test_formula_refs_exist(self):    # every A1 reference in every {f} points at a non-null cell (same or named sheet)
def test_signed_labels_are_text(self):# labels "+ This year to date…", "= Revenue, 12 months" are {v: string}
def test_duol_inputs_and_pages(self): # SEC inputs revenue row: 1037589000 / 590421000 / 483008000, pages "84 · 7 · 6"-style text from the record
def test_10k_point_single_line(self): # Review Focus 1 in the sheet: one FY line, total formula = that cell
```

- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** `auditWorkbook` and `xlsxBytes`.
- [ ] **Step 4: Run** the suite — Expected: pass. Then in the browser preview, Download DUOL's .xlsx (Task 7 wiring can be stubbed by calling `xlsxBytes` from the console) and open it: no formula errors, results equal the hand-built sheet.

### Task 7: Create in Google Drive, download, remember the link

**Files:**
- Modify: `output/moat_momentum.html`
- Test: `tests/test_screener_js.py`

**Interfaces:**
- Consumes: Task 6.
- Produces:
  - `driveErrorText(code) -> {msg, retry: boolean}` — `server_not_connected`/`selection_required` → "Add Google Drive in claude.ai Settings → Connectors, then try again."; `needs_reauth` → "Reconnect Google Drive in claude.ai Settings → Connectors."; `approval_required`/`not_in_manifest` → "Creating the sheet needs your approval; claude.ai asks when the dashboard is open there."; `not_granted`/`capability_disabled`/`capability_removed` → "Google Drive is not available in this view. Use Download as Excel."; `server_unavailable`/`upstream_error`/`tool_error`/unknown → "The sheet may have been created; check your Google Drive before trying again." `retry` is always false (no automatic write retry).
  - `async createAuditSheet(cik)` — one `callTool("Google Drive", "create_file", {title, base64Content, contentMimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"})` per click; on success store `{url, built: meta.as_of}` at `data/users/<user.id()>/auditSheets/<cik>` via `db`, falling back to localStorage; render Open / Rebuild.
  - `async downloadAuditXlsx(cik)` — `downloads.save({filename: "TICKER_calculation_check_DATE.xlsx", data})`; button hidden when `use("downloads")` is null.
  - Publish with capabilities `{db: {}, downloads: true, user: {}, mcp: {servers: [{server: "Google Drive", tools: ["create_file"]}]}}`.

- [ ] **Step 1: Write the failing tests**

```python
def test_error_texts(self):  # Review Focus 5: each code above maps to its text; retry false for all
def test_stale_link_offers_rebuild(self):  # stored built < meta.as_of -> state "rebuild"; equal -> "open"; none -> "create"
```

- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement**; the buttons disable while a call is in flight (no double click).
- [ ] **Step 4: Run** the suite — Expected: pass.

### Task 8: Publish and check end to end

**Files:**
- Modify: `README.md` (one paragraph: Calculation check and how the page numbers are found), `docs/specs/2026-11-04-calculation-check-design.md` status line

- [ ] **Step 1:** Publish the artifact (`output/moat_momentum.html` with `data/*.js` incl. `audit_data.js`) to https://claude.ai/artifact/UNG5354pYDDBbT3NXjJy7g with the Task 7 capabilities.
- [ ] **Step 2:** In the browser: DUOL Deep-Dive table shows 37.30%, 91.84%, 187.96%, 50.72%, 0.67%, 3.00%, (6.83x), Not tested ×2; a 10-K-year company and ONC render without errors; console clean.
- [ ] **Step 3:** Ask Jitti to click **Create calculation sheet** on DUOL (first use needs his approval in claude.ai), then compare the new sheet with the hand-built one (`get_values` on both): every "Same as dashboard?" is Yes, pages present.
- [ ] **Step 4:** Full suite green; report reconcile count, located-page share, `audit_data.js` size.
