# PROJECT_MEMORY.md

> ความจำระยะยาวของโปรเจกต์ AI อ่านไฟล์นี้ก่อนเริ่มงานทุกครั้ง ผู้สอนอ่านเพื่อดูว่าคุณเจออะไรมาและเรียนรู้อะไร
> ห้ามวาง error ยาว ๆ ที่อาจมี key หรือข้อมูลส่วนตัว ให้สรุปสั้น ๆ แทน

## กฎที่ได้จากบทเรียน

> กฎ 1 บรรทัด ที่ AI ต้องทำตามจากนี้ไป

- Use SEC EDGAR XBRL data for any number used in a backtest; never use a screener CSV, because it only shows today's values.
- In a point-in-time run, use only facts whose *filing date* is on or before the as-of date (not the period end date).
- GuruFocus / StockAnalysis exports and transcript text live only in `data/private/`; check `git status` before every commit.
- A catalyst counts only when the numbers already show it; transcripts and management statements can confirm but never trigger.
- Every backtest result must state that the 10-bagger list contains survivors only (survivorship bias).
- Decide 10-K vs 20-F/40-F from SEC filing forms, never from the screener's country or currency column.
- Fetch SEC data with parallel workers that share one ≤10 req/s throttle; one request at a time only reaches ~1.5 req/s.
- Before re-running a long download, confirm the old process is gone with `pgrep -fl <script>`; on macOS `pkill -f "python x.py"` can miss it.
- Never compare share counts across filings (not split-adjusted); take current and year-ago diluted shares from the same filing.
- Cash-flow quarters must be derived from year-to-date differences; 10-Qs never report a 3-month cash-flow figure.
- After any change to quarter or TTM logic, re-check TTM revenue against Stock Analysis (baseline: 96.5% within 1%).
- Never multiply a yfinance `Close` by SEC shares; undo later splits first (raw = Close × product of later splits).
- Judge weight variants on 5x+ count, median return and share halved, and require both windows to agree; ~25 ten-baggers per window is too few to rank variants by hits.
- AI reader agents may use only the pack text; the code must check every quote verbatim and every URL against the pack before a label counts.
- Before blaming the AI for "insufficient", check whether the input text was trimmed or extracted from the wrong section.
- Detect acquisitions with both cash paid and goodwill added; cash alone misses stock-financed mergers.
- Any new Layer 1 penalty must improve the backtest in both windows before it is kept.
- Get share counts only through `quarters.shares_as_of()` (fallbacks + age limit); never use the latest `dei` value blindly.
- Open every generated page in the browser (light, dark, narrow) before calling it done; the data can be right while the layout is broken.
- Copy identifiers (CIK, ticker) into tests from the data files, never from memory; a wrong CIK silently points at another company.

## บันทึกปัญหา

> เพิ่มต่อท้าย ห้ามลบของเก่า

### 2026-11-02 · A screener CSV cannot backtest 2019

- **เจออะไร:** The first plan used StockAnalysis/GuruFocus CSV exports for both the current screen and the 2019 backtest.
- **สาเหตุ:** A screener export is a snapshot of today's numbers. It cannot show what a company looked like in 2019, and it mostly leaves out companies that were delisted or went bankrupt.
- **แก้อย่างไร:** Switched the numeric backbone to the SEC EDGAR XBRL `companyfacts` API. It is free and public, gives a URL for every number, has filing dates for point-in-time cuts, and keeps delisted companies. The paid CSVs are now used only for the current universe and extra fields.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Nothing was run yet; this was caught during planning.

### 2026-11-02 · SEC download too slow, then a crash on restart

- **เจออะไร:** The submissions download ran at only ~1.5 requests/second (~35 min for 3,000 companies). After I restarted it with parallel workers, it crashed with `FileNotFoundError` on a `.tmp` cache file.
- **สาเหตุ:** (1) Requests were sent one at a time, and each takes ~0.4 s, so we never got near SEC's 10/s limit. (2) `pkill -f "python universe.py"` did not stop the old run, because on macOS the process shows as `Python universe.py`. Both runs wrote the same `.tmp` file.
- **แก้อย่างไร:** Added a thread-safe throttle in `src/sec_client.py`, so 6 workers share one ≤10 req/s limit (measured 7.6 req/s, 4.4 min). Temp file names now include the process and thread id. Killed the old process by PID after checking with `pgrep -fl`.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** `pkill -f "python universe.py"`.

### 2026-11-02 · Reverse split looked like an 88% buyback

- **เจออะไร:** OESX showed shares outstanding −88% in a year, so it scored as a heavy buyback. DVLT had +872% shares and still ranked #13.
- **สาเหตุ:** The `dei:EntityCommonStockSharesOutstanding` cover-page counts are as reported on each filing date and are not adjusted for splits; OESX had a reverse split. Separately, dilution had only a 5% rank weight, which is far too weak for a near-10x share increase.
- **แก้อย่างไร:** Dilution now uses `WeightedAverageNumberOfDilutedSharesOutstanding` for the current period and the year-ago period, both from the same latest filing (filings restate comparatives for splits). Added a score multiplier of 0.7 when diluted shares rise more than 25%. After the fix: OESX +25% (real), DVLT rank 13 → 1,058, coverage 98%.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Comparing cover-page share counts from two different filings.

### 2026-11-02 · Fiscal-year changes break quarter chains

- **เจออะไร:** 134 companies looked "stale" (no recent TTM), but 52 of them do have recent quarters.
- **สาเหตุ:** They changed their fiscal year end and filed a short transition period (e.g. a 4-month period), so 4 contiguous quarters cannot be formed.
- **แก้อย่างไร:** Labelled them `quarter_gap` instead of `stale`, so they are visible and not silently dropped. Not fixed for the MVP (~2% of companies).
- **ลองวิธีไหนแล้วไม่เวิร์ก:** —

### 2026-11-02 · "Plausibility" measured cheapness, not size

- **เจออะไร:** After raising the plausibility weight to 0.45, 53 of today's top 100 were still above $1B market cap, although the backtest said small companies were ~10x more likely to 10x.
- **สาเหตุ:** Required CAGR = (10 × market cap ÷ exit P/S ÷ revenue)^(1/5) − 1, which depends on price-to-sales, not size. A $38B-revenue refiner trading at a low P/S looks very "plausible".
- **แก้อย่างไร:** Added an explicit `small_size` rank (−market cap) and tested it in both windows. Chose size .15 / plausibility .30 (see prompts.md round 4).
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Relying on plausibility alone to capture size.

### 2026-11-02 · yfinance `Close` is split-adjusted

- **เจออะไร:** AAPL's 2019-12-31 `Close` from yfinance was $73.41, but it actually traded at $293.65.
- **สาเหตุ:** yfinance adjusts `Close` for later splits (AAPL 4:1 in 2020). Multiplying it by SEC share counts from 2019, which are not split-adjusted, would understate market cap 4x.
- **แก้อย่างไร:** Raw price = `Close` × product of all splits after that day (from yfinance `Stock Splits`). Checked against AAPL $293.65 and NVDA $235.30.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** —

### 2026-11-02 · MD&A extraction picked the table of contents

- **เจออะไร:** The first reading packs for Layer 2 contained the 10-Q's table of contents and balance sheet instead of the MD&A (SANM), or a forward-looking-statement paragraph (PBF).
- **สาเหตุ:** The MD&A heading appears 2–3 times (TOC, in-text mentions, the real heading). Choosing the "longest section" while starting the end-search 200 characters late let the TOC entry run to the real Item 3.
- **แก้อย่างไร:** Prefer headings preceded by "Item 2." / "Item 7."; start the end-search right after the heading; fall back to all matches if the titled one is under 2,000 characters; skip boilerplate to "Overview"/"Results of Operations". Checked by reading 5 packs.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** A regex for exhibit 99.1 names (`ex99-1`); real names vary (`a991press...`, `exx991...`). Now chosen by elimination.

### 2026-11-02 · Trimming text hid the revenue explanation

- **เจออะไร:** 29 of 100 companies were classified "insufficient", and about 12 of them said "the pack does not explain the driver".
- **สาเหตุ:** All those MD&As hit the 9,000-character cap; the revenue explanation lives later, under "Results of Operations".
- **แก้อย่างไร:** Added a "Revenue drivers" section (later MD&A paragraphs that mention revenue + a change + a cause, max 5,000 characters). Re-review moved 3 of 10 to watch.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** —

### 2026-11-02 · Cash paid for acquisitions misses stock mergers

- **เจออะไร:** `PaymentsToAcquireBusinesses…` flagged only 8 of the 21 companies the agents found to be acquisition-driven.
- **สาเหตุ:** Stock-financed mergers (e.g. RJET, MAGN, CAL) pay little or no cash, so nothing shows in the cash-flow tag.
- **แก้อย่างไร:** Also flag when goodwill added over ~2 years exceeds 10% of prior-year revenue → 15/21 caught, 2 false flags.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Cash paid alone.

### 2026-11-02 · Missing and stale cover-page share counts

- **เจออะไร:** 10 of 100 dashboard companies had no market cap (incl. DERM, CLOV, EVC, PBF), and TLYS used a share count from 2015.
- **สาเหตุ:** `dei:EntityCommonStockSharesOutstanding` is missing from companyfacts for many filers (often multi-class companies), or was last tagged years ago. The code took the latest value without checking its age. The Day 4 backtest used the same lookup.
- **แก้อย่างไร:** `quarters.shares_as_of()`: cover page → `CommonStockSharesOutstanding` → quarterly diluted weighted shares, nothing older than 400 days. Result: market caps 100/100, all within 25% of the screener. Backtest rerun (holdout 10x hits 4 → 3).
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Cover-page shares only.
