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
