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
