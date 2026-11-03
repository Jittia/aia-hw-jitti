# บันทึกขั้นตอน (process log)

> เพิ่ม 1 entry ทุกครั้งก่อน commit ต่อท้ายไฟล์ ห้ามลบของเก่า
> ผู้สอนอ่านไฟล์นี้เพื่อดูวิธีคิดของคุณ ไม่ใช่แค่ผลงานสุดท้าย
> ถ้าใช้ AI ช่วยทำงาน AI จะเขียน entry ให้ตาม AGENTS.md ถ้า commit เอง ให้เขียนเองตามแบบด้านล่าง

---

## รอบ 1 · 2026-11-02

- **ทำอะไร:** Brainstormed the project with AI in Plan mode (asked it to challenge me), then wrote the first full `spec.md`.
- **เครื่องมือ / model:** Claude Code desktop · Opus 5.5 · Plan mode + brainstorming skill
- **Prompt ที่ใช้:**

```text
Let's brainstorm first. I want you to challenge and grill me to build robust plan to meet my objective below.

My objective: To identify shortlist of company to be part of my key watchlist which have potential to reach 10X return in 5 years. Focus on it's new key catalyst such as, new business TAM, new S curve, Turn-around, new market. This must help me find the needle from the haystack instead of depend on general news which many investor already focus on. Scope is from USA, Hongkong, Thailand, Singapore, Japan and Taiwan stock market.

Let's plan together, development could be split in to phases (focused market or industry), I have personal subscription of GuruFocus and Stock analysis website which could be utilize to support this work.
```

- **ผลที่ได้:** The AI pushed back with 6 challenges: (1) 10x in 5 years = ~58% CAGR, rare and mostly small caps; (2) GuruFocus/StockAnalysis are not an edge because everyone has them; (3) 6 markets at once is too broad; (4) the repo is Public so paid data cannot be committed; (5) "catalyst" is qualitative, so a pure number screen cannot see it; (6) without a backtest the tool is just a feeling. After 3 rounds of multiple-choice questions we agreed a Phase 1 plan and wrote `spec.md`. Still missing: no code and no data yet.
- **ตัดสินใจอะไร และเพราะอะไร:**
  - Phase 1 = US. Best data coverage (EDGAR, English transcripts); other markets later. Taiwan monthly revenue noted as a strong Phase 2 idea.
  - No hard market-cap limit, but a **soft penalty**: a $50B company needs a $500B outcome for 10x, so the score shows how implausible that is instead of hiding the company.
  - Two layers: numbers cut ~4,000 stocks to ~100, then AI reads filings to classify the catalyst and cut to 10–20. Numbers alone cannot see a new S-curve; reading 4,000 filings is too slow.
  - **Quant proof first**: a catalyst counts only if the numbers already show it; transcripts only confirm. I prefer evidence over management talk. Accepted cost: entering after 1–2 quarters of inflection.
  - Paid CSVs stay in `data/private/` (gitignored). The repo is Public and AGENTS.md forbids purchased data.
  - Backtest as of 2019-12-31 against 2019→2024 10-baggers, measuring recall and precision on survivors, with the survivorship bias disclosed. A strict test that includes delisted stocks would not fit a 1-week MVP.
  - The AI pointed out that a screener CSV is a *today* snapshot and cannot backtest 2019, so SEC EDGAR XBRL data (free, public URL per number, has filing dates, includes delisted companies) became the numeric backbone.
  - Output = HTML dashboard + CSV (same pattern as my dividend dashboard), shortlist 10–20 names, written in English.
- **ขั้นต่อไป:** Day 2: export the US universe CSV from StockAnalysis into `data/private/`, build `universe.py` (ticker → SEC CIK) and `edgar.py` (fetch and cache companyfacts, point-in-time filter).

---

## รอบ 2 · 2026-11-02

- **ทำอะไร:** Day 2. (1) Pulled the US universe from the Stock Analysis Pro screener. (2) Built `src/universe.py` to map every ticker to its SEC CIK and drop companies with no quarterly 10-Q data. (3) Built `src/edgar.py` to download SEC XBRL companyfacts and look up numbers point-in-time. (4) Added a test against real filings.
- **เครื่องมือ / model:** Universe pull: Claude Cowork · SA Specialist (separate project). Code: Claude Code desktop · Opus 5.5.
- **Prompt ที่ใช้:** (to the SA Specialist: the universe prompt drafted in round 1's session; to Claude Code:)

```text
Read AGENTS.md, PROJECT_MEMORY.md, spec.md and prompts.md first.

Context: Day 2. The US universe is saved at
data/private/stockanalysis_us_universe_2026-11-02.csv (3,073 rows, licensed data, never commit, never print rows to chat).
Its README sits next to it — read it for filters, columns and caveats.

Task A — universe.py: load the CSV; download SEC company_tickers.json (+ company_tickers_exchange.json) with a User-Agent from a local .env; map ticker -> 10-digit CIK (handle BRK.B vs BRK-B, GOOG/GOOGL); use the submissions API to record the latest annual form (10-K vs 20-F/40-F) and whether any 10-Q was filed in the last 2 years; output data/private/universe_with_cik_2026-11-02.csv with cik, sec_form_annual, has_10q_recent, include_flag, exclude_reason; exclude no CIK, 20-F/40-F, no 10-Q in 2 years; keep and flag the 4 royalty trusts; keep both share classes but mark one primary; print counts only.

Task B — edgar.py: fetch companyfacts per included CIK (max 10 req/s, retry with backoff, resumable cache in data/cache/companyfacts/); facts_as_of(cik, concept, as_of_date) returns only facts FILED <= as_of, de-duplicated by period keeping the earliest filing; cover revenue aliases, GrossProfit, OperatingIncomeLoss, operating cash flow, capex, dei shares outstanding; short test for AAPL, NVDA and one small cap as of 2019-12-31 with filing URL, confirming no later fact is used.

Rules: follow PROJECT_MEMORY.md; git status before any commit; data/private and data/cache must not appear; do not commit until I say so.

Task C — log round 2 in prompts.md and lessons in PROJECT_MEMORY.md.
```

- **ผลที่ได้:**
  - **Universe pull (Stock Analysis Pro screener):** exchanges NYSE / NASDAQ / NYSE American, `Is SPAC` = No, market cap ≥ $50M. Industries exclude banks, insurance (incl. brokers), REITs, mortgage finance, asset management, capital markets and shell companies. The site has no average dollar-volume filter, so we computed avg volume × price and dropped rows below $500K (340 removed): 3,413 → 3,073 rows. ADR / 20-F filers could not be filtered on the site, and Stock Analysis has no CIK column; both are handled from SEC data. File stays in `data/private/` (licensed).
  - **Task A, `universe.py`:**
    - All 3,073 tickers matched a CIK (0 unmatched; the 9 class-share tickers such as `BF.B` needed `.`→`-`).
    - Excluded 554: 407 file 20-F, 112 file 40-F, 35 have no 10-Q in 2 years. Of the 35, 16 are foreign companies filing 6-K reports and most of the rest are IPOs from the past year.
    - Included: **2,519 tickers = 2,499 companies**. 20 companies have two share classes (the more liquid one is marked primary). The 4 royalty trusts are kept and flagged.
    - Source: [company_tickers.json](https://www.sec.gov/files/company_tickers.json), [submissions API](https://data.sec.gov/submissions/), retrieved 2026-11-02.
  - **Task B, `edgar.py`:**
    - companyfacts downloaded for 2,496 of 2,499 companies (3 return 404 = no XBRL data); 430 MB gzip cache in `data/cache/` (gitignored).
    - Annual revenue is found for 1,672 companies as of 2019-12-31 and 2,312 as of today. The other 187 today use revenue concepts not yet in the alias list.
  - **Test** (`tests/test_edgar_asof.py`, 3/3 pass). Revenue visible on 2019-12-31:

    | Ticker | Revenue | Period end | Filing |
    |---|---|---|---|
    | AAPL | $260,174M | 2019-09-28 | [10-K filed 2019-10-31](https://www.sec.gov/Archives/edgar/data/320193/000032019319000119/0000320193-19-000119-index.htm) |
    | NVDA | $11,716M | 2019-01-27 | [10-K filed 2019-02-21](https://www.sec.gov/Archives/edgar/data/1045810/000104581019000023/0001045810-19-000023-index.htm) |
    | LWAY (Lifeway Foods, small cap) | $103.35M | 2018-12-31 | [10-K filed 2019-04-15](https://www.sec.gov/Archives/edgar/data/814586/000168316819001051/0001683168-19-001051-index.htm) |

    The LWAY value was checked against the 10-K text ("Net Sales $ 103,350" in thousands). The test also confirms no fact filed after 2019-12-31 is returned, and that the same lookup "as of today" sees more periods, which proves the filter really removes later filings.
- **ตัดสินใจอะไร และเพราะอะไร:**
  - Kept credit services, financial data & exchanges, financial conglomerates (57) and non-REIT real estate (28). They can still be catalyst stories (fintech, exchanges, developers), unlike banks and insurers, whose revenue and margin mean something different.
  - Excluded 20-F / 40-F filers and companies with no recent 10-Q: they have no quarterly data, and our signals need quarters. Recent IPOs are dropped for the same reason; revisit them once they file 10-Qs, because new listings can be early 10x candidates.
  - Point-in-time = keep the **earliest** filing per period. Later restatements must not leak into a 2019 run.
  - Revenue merges 4 concept names in priority order, because companies switched from `SalesRevenueNet` to `RevenueFromContract...` with ASC 606 in 2018.
  - Shares outstanding sums the cover-page values per filing, because multi-class companies report one value per class.
  - Cache stored as gzip (430 MB instead of several GB). The SEC User-Agent is read from a local `.env` (gitignored); `.env.example` is committed as a template.
- **ขั้นต่อไป:** Day 3: build quarterly series from the facts (derive Q4 = annual − 9-month YTD), then compute Layer 1 signals: revenue acceleration, margin inflection, turnaround, and a dilution penalty. Add the 10x plausibility penalty and a score. First, widen the revenue aliases so the 187 companies without revenue are covered.

---

## รอบ 3 · 2026-11-02

- **ทำอะไร:** Day 3, Layer 1 quant scoring. Widened the revenue concept list, built quarterly + TTM series from SEC facts (`src/quarters.py`), computed per-company signals (`src/signals.py`), and added the 10x plausibility penalty and weighted score (`src/score.py`, settings in `config.yaml`). Validated against Stock Analysis and added tests.
- **เครื่องมือ / model:** Claude Code desktop · Opus 5.5
- **Prompt ที่ใช้:**

```text
Start Day 3
```

- **ผลที่ได้:**
  - **Quarters:** a discrete quarter = a 3-month fact, or the difference of two year-to-date facts with the same fiscal start (12M − 9M = Q4). Needed because 10-Q cash-flow statements are year-to-date only and Q4 never appears directly. Test: Apple Q4 FY2019 = $64,040M, and TTM at 2019-09-28 = the reported annual $260,174M (`tests/test_quarters.py`; 6/6 tests pass).
  - **Validation vs Stock Analysis:** our TTM revenue is within 1% of the site's figure for **96.5%** of 2,097 USD reporters (97.3% within 5%; 29 off by more than 20%). This is an independent check that the quarter derivation works.
  - **Coverage of 2,499 companies:**

    | Status | Count | Meaning |
    |---|---|---|
    | ok | 2,100 | scored |
    | no_revenue_ttm | 230 | mostly pre-revenue biotech and recent IPOs without 4 quarters yet |
    | stale | 82 | no quarter in the last ~200 days |
    | quarter_gap | 52 | quarters exist, but a fiscal-year change leaves a gap |
    | no_revenue_history | 35 | no revenue a year earlier to compare with |

    1,680 passed the gate (growing, or just turned profitable / FCF-positive).
  - **Signals:** TTM revenue growth, acceleration, gross and operating margin change, turnaround, dilution, and two new red-flag signals (revenue vs prior peak, lumpy quarter). The score = weighted percentile ranks × penalties (mega-cap, dilution > 25%, one quarter > 50% of TTM).
  - **Still open:** 58 of the top 100 are below their earlier revenue peak, i.e. cyclical rebounds (refiners PBF, CVI, DK; SEDG) rather than new S-curves. Weights are not tuned yet; that is Day 4.
- **ตัดสินใจอะไร และเพราะอะไร:**
  - Dilution uses diluted weighted shares for now vs a year earlier **from the same filing**. Raw share counts across filings are not split-adjusted, so a reverse split looked like an 88% buyback (OESX). Filings restate comparatives for splits, so taking both numbers from one filing is split-safe. After the fix, OESX shows its real +25% and DVLT (+968% shares) fell from rank 13 to 1,058.
  - Quarter chains keep concept consistency first and the earliest filing second. Mixing a subset revenue concept with a total would corrupt the year-to-date differences. Point-in-time is still respected, because every fact used was filed before the as-of date.
  - Exit P/S by sector (Tech 6x … Energy 1.5x) and all penalty thresholds are marked ASSUMPTION in `config.yaml`. There is no source for them, so the backtest has to tune them.
  - `rev_new_high` weight is set to 0 for now. Whether rebounds or new highs produced more 10-baggers is an empirical question for Day 4.
  - Analyst count (under-followed, question 4) is kept as a display column only. There is no 2019 value for it, so it cannot be backtested.
  - Scores file stays in `data/private/` because it includes licensed market-cap columns.
- **ขั้นต่อไป:** Day 4: backtest as of 2019-12-31. Build the 2019→2024 10-bagger list with `yfinance`, get 2019 market cap (price × shares), run Layer 1 on 2019 data, measure recall and precision on survivors, and tune the weights. Includes deciding rebounds vs new highs.

---

## รอบ 4 · 2026-11-02

- **ทำอะไร:** Day 4, backtest. Pulled prices from Yahoo (`src/prices.py`), ran the Layer 1 score point-in-time as of 2019-12-31 (tune window) and 2018-12-31 (holdout window), compared 8 weight variants against the stocks that went ≥10x in the next 5 years (`src/backtest.py`), chose new weights, and wrote the public report `output/backtest_report.md`.
- **เครื่องมือ / model:** Claude Code desktop · Opus 5.5
- **Prompt ที่ใช้:**

```text
Start Day 4
```

(plus my answer to the AI's size-tilt question: "Size .15 / plaus .30 (Recommended)")

- **ผลที่ได้:**
  - **Data:** 2,499 tickers priced; 1,841 had a price on 2019-12-31. Market cap then = actual traded price (split-adjustment undone with Yahoo's split history) × SEC shares on that date. Spot checks: AAPL $293.65 and NVDA $235.30 match the real 2019-12-31 closes; NVDA 2019→2024 = 22.9x, LWAY = 12.5x.
  - **Population:** about 1,800 priced survivors per window, with only **25 (tune) and 23 (holdout) ten-baggers**, a base rate of ~1.5%.
  - **Chosen weights:** **4 ten-baggers in the top 100 in both windows** (recall 16% / 17%, precision 4%, **lift 2.7x / 2.9x** vs random), 10 and 13 names ≥5x. The Day 3 weights scored 4 / 2.
  - **Size is the strongest signal.** Under $300M market cap: 4.6–4.8% became 10-baggers, vs 0.3–0.5% for $1–10B.
  - **About half the 10-baggers could not be caught on the as-of date.** Revenue was still shrinking (NVDA −19% in 2019, GME, MSTR, INOD) or there was no revenue yet (biotech: AXSM, SMMT). Switching the gate off changed results by at most one hit.
  - **Public report:** `output/backtest_report.md` lists every 10-bagger, where it ranked, and why it was missed. It contains only SEC- and Yahoo-derived values, with sources.
- **ตัดสินใจอะไร และเพราะอะไร:**
  - With only ~25 ten-baggers, a 1–2 hit difference is noise, so variants were judged mainly on 5x+ count, median return and share halved (100 names each). Both windows had to agree.
  - **Removed nothing, added a `small_size` rank.** The backtest showed plausibility (required CAGR at an exit P/S) mostly rewards *cheap* stocks, not *small* ones, while size was the strongest signal.
  - **Size tilt = .15, plausibility .30. I chose this** from 3 options the AI showed me. It gives +1 ten-bagger in both windows vs no tilt, while the share of halved stocks rises only modestly (14% / 8%). The more aggressive `size_heavy` (lift up to 3.4x) also picked more blow-ups. I prefer a balanced hit rate over maximum hits.
  - Kept the "quant proof first" gate: turning it off barely helps, and it matches how I want to invest.
  - `rev_new_high` stays at 0 and turnarounds stay in. The test helped one window and hurt the other, so the rebound question is undecided.
  - **Honesty note:** weights were chosen by looking at both windows, so no untouched test period is left. The next real check is forward tracking of the live shortlist.
- **ขั้นต่อไป:** Day 5, Layer 2: take today's top 100 and have the AI read each company's latest 10-K / 10-Q / 8-K on EDGAR, classify the catalyst (new TAM / new S-curve / turnaround / new market / cyclical-none) with a short quote and filing link, and cut to a 10–20 name shortlist.

---

## รอบ 5 · 2026-11-02

- **ทำอะไร:** Day 5, Layer 2. Built a reading pack per top-100 company from SEC filings (`src/layer2_prep.py`): the MD&A of the latest 10-Q/10-K, the paragraphs explaining revenue changes, the latest earnings release (8-K exhibit 99.1) and the Layer 1 numbers. Wrote one instruction file for the AI readers (`src/layer2_instructions.md`). Ran 5 parallel reader agents (Claude Sonnet) to classify each catalyst. Verified every result mechanically (`src/layer2_merge.py`). Then, on my choice, added an acquisition flag to Layer 1, re-reviewed the new entrants, and published a two-tier watchlist.
- **เครื่องมือ / model:** Claude Code desktop · Opus 5.5 (main), 7 reader agents on Sonnet 5.5
- **Prompt ที่ใช้:**

```text
Start Day 5
```

(plus my answer to the AI's question after the first pass: "Fix Layer 1, then 2 tiers (Recommended)")

- **ผลที่ได้:**
  - **First pass (top 100):** 1 shortlist (DERM), 15 watch, 84 reject. The reasons were mostly sound: 26 cyclical rebounds (refiners, semiconductor equipment), 16 acquisitions (e.g. SANM via ZT Systems), 9 one-offs (e.g. PBF insurance proceeds).
  - **Verification:** all quotes matched the filing text word for word and all URLs are the pack's own SEC sources (100/100).
  - **Bug found:** 29 were "insufficient", and about 12 of them because my 9,000-character MD&A trim cut off the part that explains revenue. Added a "revenue drivers" section and re-reviewed 10 → 3 moved to watch (TRT, CALX, TLYS).
  - **Acquisition flag in Layer 1:** cash paid for acquisitions (cash-flow XBRL) caught only 8/21 inorganic companies, because stock-financed mergers pay no cash. Adding goodwill growth caught 15/21 with 2 false flags (both already rejects).
    - In the backtest, the 0.6 penalty raised 5x+ names from 10 → 13 (2019) and 13 → 15 (2018); 10-baggers 4 → 5 (2019).
    - It pushed 17 companies out of today's top 100, and 15 of those were ones the agents had labelled acquisition-driven. No shortlist or watch name was lost.
  - **17 new entrants reviewed:** 2 watch (INGM, SPHR), 15 reject.
  - **Final watchlist (`output/shortlist.csv`, 20 names):**
    - Tier A: DERM (new product Emrosi).
    - Tier B, medium confidence: TRT (AI-chip test, Malaysia), TLYS, CLOV, APPS, STAA (China), STLN, KVHI (LEO satellite airtime), CTRN, ARW.
    - Tier B, low confidence: SEDG, TLS, EVC, ANIK, CALX, TPC, MTRX, SONO, KODK, INGM.
    - SPHR missed the 20-name cap.
  - **Still weak:** only 1 name passed as a confirmed shortlist. Most Tier B names are turnarounds with low confidence. 2 packs have no MD&A (ANIK, PODC) and 24 have no earnings release.
- **ตัดสินใจอะไร และเพราะอะไร:**
  - Readers may use **only** the pack text, and every quote must match the filing word for word. This keeps each label traceable to an SEC document (AGENTS.md rule: every fact needs a source). The code checks it rather than trusting the agent.
  - Sonnet for the 7 reader agents (~1.3M tokens total): classification from short text does not need the larger model. Spot checks of SANM, PBF, KLIC, RILY and DERM matched the filings.
  - **Fix Layer 1 first, then two tiers. I chose this** over "two tiers now" and "widen Layer 2 to top 300". Reason: 45% of the top 100 were cyclical or acquisition-driven, so it is cheaper to stop them at Layer 1 than to pay agents to reject them.
  - A watchlist is the goal, so Tier B (watch) is a valid part of it. Tier A means "act on research now"; Tier B means "monitor next quarter".
  - The acquisition thresholds (10% cash, 10% goodwill) were calibrated on the agents' labels and then checked in both backtest windows before being kept.
- **ขั้นต่อไป:** Day 6: build `output/dashboard.html`: a ranked table with tiers, catalyst, quote and filing link, Layer 1 numbers, and the backtest summary. Market cap from Yahoo price × SEC shares (not the licensed screener).

---

## รอบ 6 · 2026-11-02

- **ทำอะไร:** Day 6, the dashboard. Wrote `src/build_dashboard.py` and `src/dashboard_template.html`, which produce `output/dashboard.html`: one self-contained page (no external scripts) with the screening funnel, the 20-name watchlist (click a row for the filing quote, SEC link and red flags), a chart of what the AI found in the top 100, and the backtest summary. Light/dark theme, works at phone width. Also fixed a share-count bug that affected the backtest, and filled in `output/README.md`.
- **เครื่องมือ / model:** Claude Code desktop · Opus 5.5 · built-in browser to check the page
- **Prompt ที่ใช้:**

```text
Start Day 6
```

- **ผลที่ได้:**
  - **Page:** the dashboard opens with no console errors and no sideways page scroll, and was checked in both light and dark themes. Fixed two layout problems found by looking at it: the evidence text ran past the edge of the screen, and two chart labels overlapped.
  - **Market cap = Yahoo close × SEC share count** (not the licensed screener, because the repo is public). Cross-check against the screener: 93/100 within 10%, 100/100 within 25%.
  - **Bug found while building it:** 10 of 100 companies had no market cap (incl. DERM, the only Tier A), and TLYS was using a 2015 share count.
    - Cause: many companies have no `dei` cover-page share fact in companyfacts, or only a years-old one.
    - Fix: one shared `shares_as_of()` that tries cover page → balance sheet → diluted weighted shares and rejects anything older than ~13 months.
    - The backtest used the same lookup, so it was rerun. 2019 window: 5 ten-baggers (unchanged), lift 3.45x. 2018 window: 4 → **3** ten-baggers, lift 2.34x. 5x+ names 13 / 15. The current weights still have the most 5x+ names in both windows, so they stay.
- **ตัดสินใจอะไร และเพราะอะไร:**
  - One HTML file with the data embedded. It opens offline and anyone can download it from GitHub without a server.
  - Only SEC- and Yahoo-derived values are written into the page, because the repo is Public and AGENTS.md forbids licensed data.
  - Charts kept to what answers a question: why most top-100 names were rejected (bar chart; structural types in full colour), and the size effect (two windows, legend + combined label). Everything else is a table. Colours are the dataviz skill's reference palette slots 1–2. I could not run its validator because Node is not installed; that pair is documented as passing in both themes.
  - Reported the backtest change honestly (holdout 4 → 3 hits) instead of re-tuning weights to win it back. Tuning again on the same two windows would overfit.
- **ขั้นต่อไป:** Day 7: final review against `spec.md` success criteria. The one open item is hand-checking margins, cash flow and shares for 3 tickers against their filings. Then a short summary of results and limits, and `/save`. Optional: publish the dashboard as a shareable page.

---

## รอบ 7 · 2026-11-02

- **ทำอะไร:** Day 7, final review. Hand-checked signal inputs for 3 tickers against their filings (`src/verify_filings.py`, regression test `tests/test_filing_values.py`). Went through every `spec.md` success criterion. Filled in the README header and results summary, added a dashboard screenshot, ticked the pre-submission checklist, and had the AI draft `help.md` for me to edit.
- **เครื่องมือ / model:** Claude Code desktop · Opus 5.5 · built-in browser for the screenshot
- **Prompt ที่ใช้:**

```text
Start Day 7
```

(plus my answers: group number "G03"; help.md "Draft it for me to edit")

- **ผลที่ได้:**
  - **Hand-check:** DERM (small cap), TRT (fiscal year ends June; Q4 derived) and AAPL (mega cap) → **19/19** inputs found verbatim in the filing they came from: revenue, cost of revenue, gross profit, operating income, operating cash flow (YTD), capex and diluted shares. Caveat: very small numbers (e.g. 456) could in theory match by coincidence elsewhere in a filing. DERM reports no gross-profit or capex line, so gross profit is revenue − cost of revenue and capex counts as 0.
  - **Test caught my own mistake:** writing the regression test, I typed a wrong CIK for DERM and the test failed. Corrected from the universe file. All 7 tests pass.
  - **spec.md:** all 5 success criteria ticked, each with where the proof is. Criterion 1 updated to the final backtest numbers (2019: recall 20%, lift 3.4x; 2018: 13%, 2.3x).
  - **Public check:** the repo opens without login (HTTP 200). Tracked data files are only the two SEC-derived CSVs. Licensed column names appear only in code/logs that read the private file, never as data.
  - **README:** header filled (Jitti · G03), one-screen results summary with limits, dashboard screenshot (`output/dashboard.jpg`), because GitHub shows HTML as source.
- **ตัดสินใจอะไร และเพราะอะไร:**
  - Checked filing values by searching the actual 10-Q/10-K text, not by re-reading XBRL. That checks the XBRL pipeline against what the company printed, which is the stronger test.
  - Removed the one-time "how to use this template" section from the README, as the template itself says to.
  - `help.md` was drafted by the AI from the real open problems of this week (half of 10-baggers not catchable by the numbers-first rule, survivorship bias, too few confirmed catalysts / small samples). It is marked as a draft and the checklist item stays unticked until I review it.
  - The spec status stays `draft` and Phase 2 is not started; whether to continue (Taiwan monthly revenue was the idea) is my decision after the instructor's feedback.
- **ขั้นต่อไป:** Edit `help.md` in my own words, submit the repo link via the class Google Form, and wait for instructor comments in Issues (5–6 Nov) and the Repair Clinic (7 Nov). Possible Phase 2: Taiwan (monthly revenue as an early signal) or forward-tracking this watchlist each quarter.

---

## รอบ 8 · 2026-11-02 · Phase 1.5 rework: catalyst-of-change radar

- **ทำอะไร:** Phase 1 did not meet my objective, so I asked the AI to reflect on what we learned, propose a rework, and plan it with me in Plan mode. Then it built the radar:
  - `spec.md` v2 and a `radar` section in `config.yaml`.
  - `src/history.py`: every company's full quarterly history, computed once, each row dated by its SEC filing.
  - `src/events.py`: numeric change events.
  - `src/insiders.py`: insider cluster buys from SEC Form 4 data sets.
  - `src/filing_events.py`: 8-K items.
  - `src/stages.py`: Radar → Emerging → Confirmed.
  - `src/prices_monthly.py` and `src/event_study.py`: test 2012→2021.
  - `src/radar_watchlist.py`: the live list, with AI review of the Confirmed names (3 reader agents).
  - New `output/dashboard.html`, `output/watchlist.csv`, `output/event_study_report.md`, and `tests/test_events.py`.
- **เครื่องมือ / model:** Claude Code desktop · Opus 5.5 (Plan mode, then build), 3 reader agents on Sonnet 5.5, built-in browser
- **Prompt ที่ใช้:**

```text
I want to understand the learning after you run through all this work. Compare with my original objective, what you found, what shall be adjust to make this tool works better, anything we build as our source database for future use ?
```

```text
Back to original objective to find the catalyst of change which could turn company around and grow much faster (if we need to reduce from 10X to lower number to make it reasonable but stretch. that could be revised. From this learning, suggest to me how could we rework to make usable tool for this screening objective. Any additional data we need eg. transcript ?
```

```text
Yes, plan Phase 1.5
```

(plus my plan answers: "What we built so far do not meet my expectation. So I want to rework on it prior to send to Repair Clinic." · target "5x in 5y + 10x flag" · transcripts in Phase 1.6)

- **ผลที่ได้:**
  - **Data:**
    - History for 2,268 companies (105,842 company-quarters, quarters ending 2008-06 → 2026-10). Its TTM revenue equals Phase 1's for all 2,135 comparable companies.
    - Events: 19,371 numeric, 4,637 insider cluster buys (from 100,578 open-market purchases), 48,660 8-K items.
    - Monthly prices 2012→2026 and a share-count history for market cap on any past date.
  - **Event study (5-year forward returns, lift vs all companies in the same months):**

    | Group | Tune 2012–17 | Holdout 2018–21 |
    |---|---|---|
    | Confirmed | 2.07x | **1.68x** (8.7% reached ≥5x vs 5.1%) |
    | Emerging | 1.82x | 1.43x |
    | Radar | 1.30x | 0.99x |
    | Gross-margin step-up | 1.39x | 1.48x |
    | Turned profitable | 1.33x | 1.67x |
    | Revenue acceleration | 1.45x | 1.05x |
    | Contracted revenue | 1.79x | 1.09x |
    | Insider cluster | 1.01x | 1.37x |
    | 8-K items | ~1.0x | ~1.0x |

    The baseline (all company-quarters) is 1.03x / 1.04x, which confirms the method is fair.
  - **Live as of 2026-11-02:**
    - 1,084 Radar → 107 Emerging → 59 Confirmed → AI read 45 new Confirmed names (161/162 quotes verified across all reviews).
    - **26 Tier A**: 11 new S-curve, 7 new TAM, 5 new market, 3 turnaround.
    - 38 Tier B; 33 Confirmed names vetoed by the AI as cycle, acquisition or one-off.
    - 12 Tier A names carry a 10x-stretch flag. Median Tier A market cap $4.0B (8 under $1B).
- **ตัดสินใจอะไร และเพราะอะไร:**
  - **Target 5x in 5 years, with a 10x flag (my choice).** 10x is ~1.4% of stocks, too few to test; 5x is ~5%, so the tests mean something.
  - **Rework on `main` before the deadline (my choice).** Phase 1 did not meet my expectation, and I want the instructor to review the reworked tool.
  - **Two-key evidence rule.** Any event can put a company on Radar; only numbers can promote it. This keeps my "proof first" principle while watching every quarter, so changes are caught as they appear.
  - **Each history computed once, dated by filing.** This makes a 10-year test possible: one pass instead of one run per date.
  - **Triggers chosen on the tuning window only.** 8-K items and insider buys were dropped as Radar triggers because their tune lift was ~1.0. Insider buys looked good in the holdout (1.37x), but using the holdout to choose would be cheating.
  - **Kept the thresholds set before the study.** The grid's best tuning result (≥30% industry excess, 2.6x) fell to 1.26x in the holdout, a clear case of overfitting. The a-priori values hold better (Confirmed 1.68x).
  - **AI reads only Confirmed names.** That cuts cost, and Confirmed is the stage with the edge. Tier B stays "numbers only".
  - **Transcripts deferred to Phase 1.6 (my choice).** Prove the free SEC signals first.
- **ขั้นต่อไป:**
  - Edit `help.md` and submit the link before Wed 4 Nov 21:00.
  - Phase 1.6: GuruFocus transcripts (local only) as an early text signal for Radar.
  - Track this quarter's lists forward.
  - Test whether the AI veto adds value.

---

## รอบ 9 · 2026-11-03 · Moat Momentum: review, spec, brand, first build

- **ทำอะไร:** Started a new tool, **Moat Momentum**, in this repo, replacing the catalyst-of-change radar. Steps of the brief (stops ★ approved by me each time):
  1. ★ Reviewed the old project: what to reuse, and why it gave false alarms.
  2. Archived the old work (`archive/phase1.5-catalyst-radar/` + git tag `phase1.5-catalyst-radar`). ★ Wrote the new `spec.md`.
  3. ★ Brand guide `output/brand_guide.html` (logo, palette with contrast checks, type, badges, chart style, do/don't).
  4. ★ Built step 3:
     - `src/mm_extract.py`: SEC bulk files → point-in-time fact store.
     - `src/mm_fundamentals.py`: clean company-year table.
     - `src/mm_score.py`: universe, risk gate, five themes, Moat Score, confirmation.
     - `src/mm_run.py`: live run, observations, Deep-Dive data.
     - `output/moat_momentum.html`: Screener, Deep-Dive, How it works, Learn, Scenarios, Methodology.
     - Google Sheet (14 tabs, data via `output/sheet/*.csv`).
     - `tests/test_moat.py`.
- **เครื่องมือ / model:** Claude Code desktop · Opus 5.5 · built-in browser to check every page (light, dark, phone width) · Google Drive/Sheets connectors
- **Prompt ที่ใช้:**

```text
# PROJECT BRIEF — "Moat Momentum" (US, SEC EDGAR) — v4, investor-grade
(full brief pasted; key lines: "FIRST TASK: review the old project and report (a) what can be reused,
(b) why it produced false alarms. Do this before building." and "stop for my approval at each ★")
```

```text
I still want to use this Repo to be my homework submission.  To replace the previous work.  what should i do
```

```text
1. yes
2. To submit this full project on Wed.  I do my best to put time to work on.
```

(plus my approvals: spec "อนุมัติทั้งหมด", brand guide "อนุมัติ เริ่มสร้างเลย")

- **ผลที่ได้:**
  - **Why the old tool gave false alarms (numbers from rounds 1–8):**
    1. It flagged one-quarter changes, so cycles looked like catalysts (26 cyclical rebounds in the old top 100; Radar lift 0.99x).
    2. No capital view (no ROIC), so bought growth looked organic (16 of top 100).
    3. No one-off clean-up (9 of top 100).
    4. Almost no risk gate: Confirmed names halved more often than average (18.4% vs 14.9%).
    5. 45% of the score was size and cheapness.
    6. Peers compared on revenue growth only.
    7. Target (5x/10x price) too rare to tune on; 56% of Confirmed names were vetoed when read.
  - **Data:** SEC bulk `companyfacts.zip` (20,540 companies) + `submissions.zip`, read once → 5,176 non-financial candidates, 5.75M fact rows. The store keeps the first filed value and every later restatement, so past runs use only what was public then.
  - **Live run 2026-11-03:**

    | Stage | Companies |
    |---|---|
    | Universe (US-listed, revenue ≥ $100M, ≥ 5 years) | 1,870 |
    | Pass the risk gate | 1,043 |
    | Moat Strengthening (≥ 3 of 5 themes improving) | 343 |
    | Shortlist | 25 |

    The shortlist includes Vertiv, Howmet, Roper, Deckers, NYT, Sprouts, Carpenter, Ralph Lauren, Huron.
  - **Checks:**
    - 19 tests pass. They include Apple FY2025 revenue $416,161M and operating income $133,050M matching its 10-K, and a restatement that is invisible before its filing date.
    - The web page recomputes all 1,870 scores in the browser and matches the Python engine exactly.
  - **Still open:**
    - Step 4 spot-check vs 10-Ks, step 5 validation, track record, Proof/Demo tabs and the pitch pack.
    - Level uses the latest fiscal year, not TTM.
    - The Sheet's data tabs fill only after this push.
- **ตัดสินใจอะไร และเพราะอะไร:**
  - **Rebuild in this repo, keep the old work in `archive/` + a git tag (my choice).** I want this to be my homework submission. The instructor reads the process, so the old attempt and why it failed stay visible.
  - **Aim to submit the full project on Wed (my choice).** If time runs out, the priority is a tested, validated screener; market validation and the pitch pack would go in as scoped drafts.
  - **Approved the AI's 8 proposals in spec §7:**
    - One 21% tax rate (avoids a fake 2018 ROIC jump).
    - Altman Z'' with book equity (EDGAR has no prices).
    - Missing data = "not tested", never Remove.
    - Operating leases out of capital (only tagged from 2019).
    - 9% hurdle for every sector.
    - Engine → Sheet → web page.
    - Public repo.
    - Untagged one-offs lower confidence.
  - **Brand colours:** three brief colours (teal, green, grey) failed the contrast check for small text on the card colour. They got slightly deeper text versions; the brief colours stay for fills and lines.
  - **Sheet gets data by `IMPORTDATA` from CSVs in this repo.** Sending 1,870 rows cell by cell through the connector is slow. Importing makes the Sheet refresh after every push and keeps it the same as the web page.
  - **Not tuned yet, on purpose:** the risk gate removes 44% (interest cover 562, Altman Z'' 511, which also hits buyback companies with negative equity). Some shortlist names may be post-COVID rebounds (LVS, HXL). Step 5 validation and robustness tests decide; defaults are locked before the final test.
- **ขั้นต่อไป:** Step 4 ★: spot-check cleaned figures for 3 years against the actual 10-Ks of 10 companies in different sectors. Then step 5 ★: fundamental validation 2013–2023 (hit rate, false-alarm rate, lead time) and robustness.

---

## รอบ 10 · 2026-11-03 · Moat Momentum steps 4–5: 10-K spot-check and fundamental validation

- **ทำอะไร:**
  - **Step 4 ★: spot-check vs 10-Ks.**
    - `src/mm_spotcheck.py`, `src/mm_spotcheck_report.py` → `output/spotcheck.html`, `output/data/spotcheck.csv`.
    - Fixed two clean-up rules the check exposed. Added regression tests.
    - Moved the filing-text helper to `src/filing_text.py`; archived `layer2_prep.py` and `verify_filings.py` (they depended on archived code).
  - **Step 5 ★: fundamental validation 2013–2023 and robustness.**
    - `src/mm_validate.py` and `src/mm_proof.py`.
    - Outputs: `output/data/validation.json`, the Proof tab in the web page, `output/proof.html`, and the Validation Results tab in the Sheet (`output/sheet/validation.csv`).
  - Checked that the Sheet imports work after I clicked "Allow access".
- **เครื่องมือ / model:** Claude Code desktop · Opus 5.5 · built-in browser · Google Sheets connector
- **Prompt ที่ใช้:**

```text
กดแล้ว ไปขั้น 4
```

```text
Approve, start step 5
```

- **ผลที่ได้:**
  - **Sheet:**
    - All data tabs fill from GitHub (1,870 rows on Universe).
    - The Settings-driven Moat Score formula gives the same value as the engine (LVS 86.5).
  - **Spot-check (step 4):**
    - 10 companies from 10 different industries: PROP, SEZL, HXL, MU, HNRG, FTI, COCO, FSS, SMTI, GSAT. Chosen by a rule set before looking: the highest-ranked company in each of the 10 largest SIC divisions.
    - 3 fiscal years each.
    - **331 of 333 non-zero inputs** were found in the visible 10-K text; 2 are short numbers with no label nearby.
    - **60 of 60** hand recalculations of clean OI and NOPAT match the engine.
  - **Two problems found and fixed:**
    1. TechnipFMC's operating-income tag ($1,157.3M) is a segment total. Its statement shows revenue − total costs = $956.8M. 48 universe companies have a gap above 10% of operating income; their data confidence now drops one level, with a Risk observation.
    2. Gains on selling a whole business ($71.3M at FTI) are printed below operating income. They are no longer subtracted, but are shown in the bridge.

    The shortlist stayed the same 25 names.
  - **Validation (step 5):**
    - Settings and scoring code were fingerprinted before the run: `settings.yaml` b2e1fdf4…, `mm_fundamentals.py` 48cf5ecc…, `mm_score.py` 2975b2bc….
    - Each year re-run as of 30 June using only filings made by then, including later-delisted companies.
    - 275 shortlist picks (212 companies) over 11 years; 17 variants.

    | 3 years later | Shortlist | Moat Strengthening | Rest |
    |---|---|---|---|
    | Peer rank kept improving (hit) | 26.9% | 39.9% | 48.6% |
    | Peer rank fell > 10 points (false alarm) | 38.0% | 27.6% | 21.8% |
    | Reached industry top 20% on ROIC | 29.2% | 32.1% | 24.0% |

  - **What the numbers say:**
    - On the brief's test, flagged companies were better later: shortlist peer rank +8.3 points vs the industry median after 3 years, ROIC +5.4 pp.
    - But against companies that started at the same rank, shortlist rank ended 3.4 points lower; ROIC was only +2.2 pp higher.
    - The same pattern holds in every variant (weights ±10, Proven Leaders, Strict Risk, no gate, Altman as flag, 2 or 4 themes), every sub-period (hit 33% / 26% / 14%) and with energy or tech excluded.
    - **Conclusion:** v1.0 finds strong, improving companies, but "strengthening" does not predict further strengthening (mean reversion). The pitch claim "visible 1–3 years before recognition" is not supported yet.
- **ตัดสินใจอะไร และเพราะอะไร:**
  - **Approved step 4 and step 5 (my choice)**, following the ★ stops in my brief.
  - **Spot-check found → keep the reported operating-income value, but lower confidence.** Replacing it with revenue − total costs could be wrong for companies whose "total costs" include interest, and only 48 companies are affected. Lowering confidence keeps it visible without guessing.
  - **Stop removing business-sale gains.** In the filing they sit below operating income, so subtracting them understated clean profit.
  - **Lock first, then report everything.** The defaults were fingerprinted before the final run and every variant is shown. This is the brief's rule against over-fitting, and the result is reported even though it goes against the brief's main insight.
  - **Added "same starting rank" comparison next to the brief's test.** The brief's level test alone would show a pass that comes only from picking already-strong companies. This was added after seeing the first results, and the report says so.
- **ขั้นต่อไป:** I decide: (a) design v1.1 with 2–3 changes declared in advance, tuned only on 2013–2017 and confirmed on 2018–2023; or (b) accept v1.0, reposition it as a "quality and improving" screen, and go to step 6 (price-data options for market validation).
