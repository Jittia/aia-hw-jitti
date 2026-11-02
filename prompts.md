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
