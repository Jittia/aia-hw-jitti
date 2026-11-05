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
- Choose thresholds and event types on the tuning window only; never re-tune after looking at the holdout.
- Every quarter/event row must carry known_date = SEC filing date; point-in-time = filter known_date ≤ date.
- Reader agents often say they did not check their quotes; always re-verify with code before a label counts.
- Yahoo records some spin-offs as small "splits" (e.g. MOD 1.086); compare market cap with the screener before adjusting.
- Rank a company against its full peer group: a wider SIC group includes the companies placed in narrower groups; never rank the leftover few on their own.
- Compute a "change ÷ change" ratio (incremental ROIC, incremental margin) only when the denominator moved by a meaningful amount (≥ 10%); otherwise leave it blank.
- Keep "infinite" risk values (e.g. net debt with EBITDA ≤ 0) as a breach in every output; never let them turn into "not tested" when exported.
- When the web page re-implements a Python calculation, check that both give the same score for every company before calling it done.
- Serve the web page through a local server (.claude/launch.json "moat-site") to preview it; the browser pane opens a file without its data/*.js files.
- Search filing values in the visible text (hidden XBRL removed), most precise format first; a short number counts only with its line label nearby.
- Never subtract a "gain" from operating income without checking it sits inside operating income; business-sale gains usually do not.
- When a back-test screen uses data newer than the fiscal year its outcome starts from (e.g. a 10-Q TTM point), measure outcomes from the next year too; otherwise the screen has seen part of the outcome.
- Missing data inside an outcome window means "no outcome", never a failed company.
- For market value, use the cover-page share count (dei) with a sanity check (market value 0.2%–200× revenue); XBRL diluted shares are sometimes filed in thousands or millions.
- A "run the test once" guard must also stop re-training and settings changes from erasing or redoing the test.
- Fix the success test and its definitions before looking at test-period results; any later check is reported as a second result, not a new pass rule.
- A document generator must read each result from a fixed, named file (e.g. archive_v1.0) for the version it describes, never "the current results", or a re-run silently mixes versions.
- Google Slides `updateSlidesPosition` counts the insertion index in the order before the move; read the slide order back after moving a slide.
- When a control has no effect in the current view, disable it and say why on screen; a control that silently does nothing looks like a bug.
- Before any new code multiplies a price by a share count, find the existing rule on splits and apply it; Yahoo history is split- and dividend-adjusted, SEC share counts are as filed.
- A "yesterday's close" must exclude bars dated on the run date (they can be intraday).
- Short-term investments = the filed total (ShortTermInvestments, MarketableSecuritiesCurrent), else available-for-sale + held-to-maturity lines; when a company's cash looks low against its 10-K, look for another securities tag before blaming the data.
- Clean net income must remove one-time *tax* items too: a filed tax rate outside 0–50% (valuation-allowance release, tax-law charge) is replaced by 21%; pre-tax one-offs alone are not enough.
- When re-running mm_run to test a methodology fix on a later day, keep the earlier daily closes (`MM_REUSE_DAILY=1` on the saved `prices_daily.pkl`); a fresh download mixes a price update into the before/after comparison.
- To wait for a background process, watch its PID (`kill -0 <pid>`); `pgrep -f <name>` inside a watcher matches the watcher's own command line and never ends.
- Never scale a "too small to be meaningful" guard on invested capital by revenue: distributors (MCK, CAH, COR) run on capital of 1–2% of revenue and are real businesses, not data errors.
- Operating leases are filed as current + non-current lines by more than half the companies (839 of 1,557); read the split tags, not only `OperatingLeaseLiability`.
- Show a ratio whose denominator can approach zero (clean ROIC) through one capped formatter, and keep exact values in data, sorting and the Calculation check; never cap the stored number.
- On one screen, every number derived from price (market value, P/E, EV, gap) must come from the same price and date.
- Cross-check the OperatingIncomeLoss tag against revenue − CostsAndExpenses; some filers tag a segment total.
- Fingerprint settings and scoring code before a validation run, and report every variant tried, including results against the hypothesis.
- Test a "momentum" signal against companies with the same starting level, not only against the industry median; otherwise picking already-strong companies looks like skill.
- Before any market test, measure how many past picks no longer trade; with free prices, report the result under neutral, worst-case and survivors-only fills.
- Treat a month above +300% as a Yahoo stitching error only for companies with a bankruptcy 8-K (item 1.03); real jumps (e.g. GME Jan 2021) stay.
- Compare a screen with a simpler version of itself (e.g. level only) built from the same data and the same price method, not only with an index.
- Choose demo cases by a rule written down before looking, and include a miss.
- Build pitch documents from code that reads the validation outputs; never retype numbers by hand into a deck or document.
- Leave prices, volumes and the funding ask as marked placeholders for the founder; never invent them.
- Before sending a generated Slides batch, compact it (round colours, drop default styles); per-cell table styling can be several times the size of the content.
- In any ranked table, label which rank a number is (position in this list vs overall rank); a filtered list with gaps reads as a bug.
- In a risk filter, a missing figure is "not tested", never a failure; show how many are not tested and let the user decide whether to drop them.
- When pairing a split-adjusted price with a share count, undo only the splits dated after the day the shares were counted, not after the price month.
- Page logic that decides membership (filters, lists) gets unit tests too: extract the pure JS functions and run them in Node, not only by hand in the browser.
- Sort a new table by market value and by each multiple once before shipping; the extremes show share-count errors (e.g. ADRs) that the revenue sanity range misses.
- Text extracted from filings: test it on the real cached corpus, not only on hand-made examples; count suspicious outputs (headings, "Item", lowercase starts, boilerplate) before shipping.
- A ratio read from today's filing (ADS, split) applies to past counts only when they are the same size; check the share-count history before applying it backward.
- A user action that can be refused (save, remove) must never look done: roll back on refusal, and give one-click deletes an Undo.
- After removing or renaming styles, check every class the page uses still has CSS ("grid2" had none, so two boxes stacked); review layout at a wide desktop width too, not only the narrow preview pane.
- Google Slides: an inserted image keeps a tiny base size and is shown through its scale; to resize it, set the scale to the target size ÷ that base size (read it first), never a small ratio such as 0.9. Check every slide as an image (Slides thumbnails work when no PDF renderer is installed).
- When showing how a number was calculated, recompute it from the raw SEC parts and test every company against the stored value; never just display the stored value.
- A page number shown for a value comes from its Inline XBRL tag; if it cannot be found, write "not located", never a guess.
- The public copy (GitHub Pages) has no claude.ai runtime: every feature that uses `claude.use(...)` needs a plain-browser fallback or must say it only works in claude.ai; test it on the local server, not the file preview.
- A file exists for others only after commit + push: before telling Jitti a file is ready to share, check `git status` and open its public link (GitHub and GitHub Pages) without logging in.
- Investor.gov glossary addresses can return status 200 with an empty page: check the page contains the definition before citing it.

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

### 2026-11-02 · Filings dated before their own period end

- **เจออะไร:** 7 of ~106,000 history rows had a filing date before the quarter they report (e.g. VTOL tagging a September quarter in a June filing).
- **สาเหตุ:** Mis-tagged period dates in the XBRL.
- **แก้อย่างไร:** Rows where known_date ≤ quarter end are dropped (`history.py`, `events.py`); a test checks known_date > end for every row.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** —

### 2026-11-02 · The best in-sample threshold was the worst out of sample

- **เจออะไร:** In the threshold grid, industry excess ≥30% gave the best tuning lift (2.6x) but only 1.26x in the holdout. The thresholds set before the study gave 1.68x (Confirmed).
- **สาเหตุ:** Overfitting: with a few hundred entries, the best of 40 combinations is partly luck.
- **แก้อย่างไร:** Kept the a-priori thresholds; the report shows the full grid so the sensitivity is visible.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Picking the grid maximum.

### 2026-11-02 · Raw "something changed" has no edge on its own

- **เจออะไร:** Radar (any numeric change) had a 0.99x holdout lift, and 8-K officer changes and material agreements ~1.0x in both windows. With 8-K items included, Radar was worse than random (0.86x / 0.91x).
- **สาเหตุ:** Most changes are noise or cycles. The edge appears only after the filters: beating the industry, organic, limited dilution, room to 5x.
- **แก้อย่างไร:** Radar triggers limited to numeric events with tuning lift ≥ 1.2; 8-K and insider events shown as context only.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Using every event type as a trigger.

### 2026-11-03 · Moat Momentum: peer groups of 1 gave scores of 100

- **เจออะไร:** In the first scoring run, several companies (Korn Ferry, UPS, Ziff Davis) scored exactly 100, and 124 companies sat in peer groups with fewer than 8 members.
- **สาเหตุ:** Companies were placed in the narrowest SIC level with ≥ 8 members. Those members were then also removed from the wider group, which left "leftover" groups of 1–7. A group of 1 ranks itself at the 100th percentile.
- **แก้อย่างไร:** `rank_in_groups()` ranks each company against everyone whose SIC starts with its group code, including companies placed in narrower groups. A test covers it (`tests/test_moat.py`).
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Plain `groupby(group).rank()`.

### 2026-11-03 · Incremental ROIC capped at 200% for many names

- **เจออะไร:** "Incremental ROIC 200%" was the top reason for 8 of 25 shortlist names.
- **สาเหตุ:** When invested capital barely changed over 3 years, Δ NOPAT ÷ Δ capital explodes and hits the cap.
- **แก้อย่างไร:** Computed only when capital grew ≥ 10%. The remaining cases are real (profit grew a lot on modestly more capital) and are worded "over 200%".
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Only requiring Δ capital > 0.

### 2026-11-03 · Web page and engine disagreed for 84 companies

- **เจออะไร:** The browser's Moat Score differed from Python by exactly 5 points (one risk flag) for 84 companies.
- **สาเหตุ:** Net debt ÷ EBITDA is infinite when EBITDA ≤ 0. Python counted it as a breach, but JSON export turned infinity into null, so the page treated it as "not tested".
- **แก้อย่างไร:** Exported as 999 with the label "EBITDA ≤ 0". After the fix, all 1,870 scores match.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** —

### 2026-11-03 · SEC bulk files are faster than per-company requests

- **เจออะไร:** The old cache (`data/cache/`) was not on this machine, so everything had to be downloaded again.
- **สาเหตุ:** The cache is git-ignored (correct, it is large), so a fresh clone has none.
- **แก้อย่างไร:** Downloaded SEC's two bulk files once (1.4 GB + 1.6 GB, ~6 minutes) and extracted all companies in ~2 minutes with 8 processes. No per-company requests, no rate limits. `edgar.py` falls back to the bulk zip, so the old tests still run.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** —

### 2026-11-03 · XBRL operating income was a segment total (TechnipFMC)

- **เจออะไร:** In the 10-K spot-check, TechnipFMC's OperatingIncomeLoss was $1,157.3M (FY2024), but its income statement has no operating-income line and revenue − total costs is $956.8M.
- **สาเหตุ:** Some filers tag the segment-profit total as OperatingIncomeLoss. 48 of 1,870 universe companies differ from revenue − CostsAndExpenses by more than 10% of operating income.
- **แก้อย่างไร:** Kept the reported value, lowered data confidence one level, added a Risk observation. A regression test covers FTI. My first threshold (3% of revenue) missed FTI itself (2.2%), and the test caught it; the gap is now measured as a share of operating income.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Gap as a share of revenue.

### 2026-11-03 · Business-sale gains were removed from operating income

- **เจออะไร:** FTI's $71.3M gain on disposal of Measurement Solutions is printed below total costs, but the clean-up subtracted it from operating income.
- **สาเหตุ:** The gain tags (GainLossOnSaleOfBusiness, DisposalGroup…) were treated like asset-sale gains. XBRL facts do not say which line an item sits on.
- **แก้อย่างไร:** Only gains on assets and equipment are removed; business-sale gains are shown as "not removed". Shortlist unchanged.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** —

### 2026-11-03 · Validation: "strengthening" did not predict further strengthening

- **เจออะไร:** Over 2013–2023 only 26.9% of shortlist picks improved their industry rank over 3 years (base 48.6%) and 38.0% fell by more than 10 points (base 21.8%). The result was the same in all 17 variants.
- **สาเหตุ:** Mean reversion. The screen rewards recent improvement and picks companies near the top of it; improvements tend to fade. The picks were still above their industry 3 years later (+8.3 rank points), but no better than companies that started at the same rank (−3.4).
- **แก้อย่างไร:** Reported as found (Proof tab). Any v1.1 must be designed in advance and tested on years not used to build it.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Changing weights, blend, risk gate or the confirmation rule (all 17 variants show the same pattern).

### 2026-11-03 · Yahoo joins pre- and post-bankruptcy shares

- **เจออะไร:** The equal-weight universe returned more than the S&P 500 and RSP, which looked wrong. Monthly returns showed CHRD +30,991% (Nov 2020) and AMPY +15,525% (Oct 2016).
- **สาเหตุ:** After a Chapter 11 reorganisation, Yahoo's adjusted series joins the old equity (worth cents) to the new shares under the same ticker.
- **แก้อย่างไร:** For companies with a bankruptcy 8-K (item 1.03) in their SEC submissions, months above +300% count as missing and are filled per scenario. 4 months were affected; the conclusion did not change. The universe is still flattered by survivorship, which the report says.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** A flat cap at +300% for every stock would also remove real moves such as GME (+1,625% in Jan 2021).

### 2026-11-03 · The market test showed no excess return

- **เจออะไร:** The shortlist returned 14.3% a year (2013–2026), the same as the S&P 500, with 18.6% volatility against 14.3%.
- **สาเหตุ:** Consistent with step 5: picks are good companies whose improvement tends to fade, and annual turnover is 81%.
- **แก้อย่างไร:** Reported in the Proof tab and spec §7b. The product is positioned as a research screen for high-quality improving businesses, not a return predictor.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** —

### 2026-11-03 · A number in my chat summary did not match the data

- **เจออะไร:** I told Jitti, and wrote in round 11, that the shortlist beat the S&P 500 in "5 of 13 years". The pitch generator counted 7 of 13, and the yearly table confirms 7 (2013, 2014, 2016, 2017, 2020, 2022, 2025).
- **สาเหตุ:** The number in the summary was counted by eye from a printed table instead of read from the data. The Proof page, which computes it, was right.
- **แก้อย่างไร:** Corrected round 11 with a note. Pitch numbers are now generated from the outputs, not typed.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Counting from a printed table.

### 2026-11-03 · TTM scores looked better only because of look-ahead

- **เจออะไร:** Scoring on 10-Q TTM figures raised the shortlist hit rate from 27% to 36% in the back-test.
- **สาเหตุ:** The outcome was measured from the fiscal year t, but the TTM point (e.g. March of year t+1) already contained part of the outcome period.
- **แก้อย่างไร:** Measured both methods from year t+1. TTM was then worse: 34.8% vs 39.0%, and the market return was lower (12.2% vs 15.6%). Not adopted; results kept in `output/data/ttm_study.json`.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Comparing methods on an outcome window that overlaps the newest data one of them uses.

### 2026-11-04 · The v2.0 Compounder Signal failed its one-time test

- **เจออะไร:** 8 signals chosen on 2013–2019 reached 2.3× the base rate in training, but only 1.19× on 2020–2023 (2× was needed).
- **สาเหตุ:** Most of the training edge was fitting the past. Winners are about 1–2% of companies, so a few lucky years move the numbers.
- **แก้อย่างไร:** Published as failed. Shown as an experimental second list; v1.1 stays the main ranking. Both lists are frozen so that live results from 2026 can test them.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Gross-margin change and acceleration from quarter to quarter (noise in training). "Winners start mid-table on ROIC" (high ROIC won).

### 2026-11-04 · SEC share counts filed in thousands or millions

- **เจออะไร:** Market value came out at $41.7 trillion for Waters and tiny for McDonald's (diluted shares tagged as 712.3). Guessing a ×1,000 fix also went wrong (Nutanix $20M, Karyopharm $17B).
- **สาเหตุ:** Some filers tag the weighted diluted share count in thousands or millions.
- **แก้อย่างไร:** Use the share count from the filing cover page (dei:EntityCommonStockSharesOutstanding), else diluted shares, and hide values below 0.2% or above 200× of revenue (5 companies shown as "check").
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Rescaling diluted shares by powers of 1,000.

### 2026-11-04 · Code review found a label bias and a weak test guard

- **เจออะไร:** (1) A company with one untagged quarter inside its 3-year window counted as a loser. (2) Re-running training erased the recorded test result, so the test could be run again. (3) On the web page, changing a risk rule put unranked companies at the top of the experimental list.
- **สาเหตุ:** Only the start and end points were checked for missing data; training rewrote `discovery.json` from scratch; the page recomputed a filter that only Python can set.
- **แก้อย่างไร:** Each fixed with a test that failed first. Labels recomputed with the same signals: 1.18× (was 1.19×), same conclusion; the original result stays on record.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** —

### 2026-11-04 · A new deck slide landed one place too early

- **เจออะไร:** The v2.0 slide was meant to follow the market-test slide but appeared before it.
- **สาเหตุ:** `updateSlidesPosition` counts the insertion index in the slide order before the move, so index 7 put it at position 6.
- **แก้อย่างไร:** Read the order back and moved it with index 8. Now always read the order back after moving a slide.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Counting the target position after removing the slide.

### 2026-11-04 · Screener settings looked broken

- **เจออะไร:** I changed weights but the list did not change.
- **สาเหตุ:** I was on the Compounder list, which is fixed and does not use the settings; the page did not say so. The settings could also total more or less than 100% without any warning.
- **แก้อย่างไร:** Settings are greyed out on the Compounder tab with a note. Totals are shown and the list pauses until both reach 100%.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** —

### 2026-11-04 · v3.0 back-test valued companies with split-adjusted prices (rule already existed)

- **เจออะไร:** The independent review found NVIDIA's 2021 market value at $8.5B instead of about $338B (also Amazon, Broadcom, Walmart, Chipotle). Past gaps and R3 were wrong.
- **สาเหตุ:** Yahoo monthly closes are adjusted for later splits; I multiplied them by share counts filed before those splits. A rule in this file already said "undo later splits first"; I did not apply it to new code.
- **แก้อย่างไร:** Split history from Yahoo (472 of 1,912 tickers); price × later split ratios; a `correct` step reran only the price-based results: R3 0.62× → 0.65×, still failed. The original result stays on record.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Relying on the 0.2%–200× sanity check: split errors stay inside that range.

### 2026-11-04 · v3.0 movement rules failed their one-time test

- **เจออะไร:** R1/R2/R3 lists became moat compounders 0.6–0.7× as often as other companies (2021–2023); their top 25 trailed the S&P 500.
- **สาเหตุ:** Entering or approaching the high-ROIC, high-growth corner mostly catches companies near a peak (energy in 2021–22), the same pattern as v1.0 and v2.0.
- **แก้อย่างไร:** Shipped as a description, labelled failed; lists frozen for the live record.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Strong current numbers, alone or with a price gap, as a guide to becoming a compounder.


### 2026-11-04 · Screener risk filter removed companies for missing data

- **เจออะไร:** The independent review found LLY, JNJ, MRK, PFE, IBM and KLAC (114 companies) removed by the risk pre-screen and counted as failures, although their numbers were only missing. Net-cash loss-makers (e.g. WOLF −5.1×) and 149 companies with interest but no debt tagged passed everything.
- **สาเหตุ:** The pass rules treated a missing value as a fail, let net cash skip interest cover, and read "no debt tagged" as "no debt". My browser checks only used made-up rows that had every value.
- **แก้อย่างไร:** Missing → "not tested" (kept by default, can be removed); interest cover tested whenever interest is reported; interest without debt → the two debt checks "not tested". Each fix started with a failing test in `tests/test_screener_js.py`.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Checking the rules by hand in the browser console only.

### 2026-11-04 · Reverse split between quarter-end and share count (AMCR)

- **เจออะไร:** AMCR's past earnings yield was 5× too high for one quarter.
- **สาเหตุ:** A 1-for-5 reverse split (Jan 2026) fell between the quarter-end price and the cover-page share count filed after it; I undid splits after the price month, so the price was pre-split and the shares post-split.
- **แก้อย่างไร:** Undo only splits dated after the share-count date (test `test_past_yield_split_between_quarter_end_and_share_count`). The same gap exists in v3.0 `value_at`; left for later.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Undoing splits relative to the price month (the v3.0 fix), which is correct only when the count is from before the split.

### 2026-11-04 · ADR market value 13× too high (BeOne Medicines), found by sorting

- **เจออะไร:** Sorting the new Screener Summary by P/E put BeOne Medicines first at a $524.7B market value; the real value is about $40B.
- **สาเหตุ (confirmed, round 22):** the price is per ADS; the cover-page count is ordinary shares (13 per ADS). About 98× revenue, inside the 0.2%–200× sanity range.
- **แก้อย่างไร:** `src/mm_adr.py` reads the ratio from the 10-K cover line naming the ticker (245 foreign-incorporated companies checked); applied only to counts close in size to the one in that 10-K. First try divided Zai Lab's 2021 count (taken before its 2022 share change) by 10 and made it 10× too small; fixed with that rule and a test.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Relying on the revenue sanity range alone.

### 2026-11-04 · 10-K "Business" text: table of contents and cross-references got through

- **เจออะไร:** The independent review ran the extractor over all cached 10-Ks: Halliburton and Rollins returned table-of-contents text; Avista and others returned quoted cross-references ("see “Item 1. Business – …”"), mid-sentence starts, or legal boilerplate (about 60 cases).
- **สาเหตุ:** My section-end pattern missed "Item 1(a)" and "Item 1.A.", so the contents line looked long enough; quoted references were taken as headings; the sentence splitter broke at "Item 1." and at invisible zero-width spaces.
- **แก้อย่างไร:** Wider Item 1A pattern; reject segments with several "Item" headings; skip quoted or "see …" references (also "Part 1 – Item 1"); require a capital first letter; more boilerplate phrases; strip zero-width spaces. 9 tests; suspicious outputs 43 → 6 of 1,557.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Testing only on 8 hand-picked companies before the full run.

### 2026-11-04 · Layout looked fine in the narrow pane but not on a wide screen

- **เจออะไร:** In the design review at 1,440 px, the Introduction headline wrapped into five short lines, the company card and the diagram left half the width empty or grew oversized, and "Why look deeper / What to watch" stacked instead of sitting side by side.
- **สาเหตุ:** Earlier checks were done in the ~1,000 px preview pane only. The side-by-side boxes used a class ("grid2") that was never defined in the CSS.
- **แก้อย่างไร:** Audited every tab at 1,440 px, phone width, light and dark; defined the grid; two-column layouts for the cover and company card; capped diagram width.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Checking only the default pane width.

### 2026-11-04 · A screenshot vanished from a Google Slides deck after resizing

- **เจออะไร:** After a resize on slide 4 of the FYI deck, the screenshot shrank to a dot.
- **สาเหตุ:** Slides stores the image with a base size of 36,000 × 25,000 EMU and shows it through a scale of about 113; my request set the scale to 0.91.
- **แก้อย่างไร:** Read the element's base size, then set the scale to the target width ÷ base width (113.28). Checked again with slide thumbnails (there is no PDF renderer on this Mac).
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Treating the scale as a ratio of the size I had asked for.

### 2026-11-05 · Calculation check: five companies did not reconcile, and sheet formulas broke on edge cases

- **เจออะไร:**
  - The first re-derivation of the Screener measures disagreed for 5 companies.
  - The generated sheets showed #ERROR!/#NAME? for some companies: missing inputs, gross profit without cost of revenue, ROIC with one invested capital missing, and others.
  - The audit export was 14.3 MB.
  - Page labels were found for only 81% of values.
- **สาเหตุ:**
  - The tool ignores a balance-sheet copy of a tag when that tag is a flow anywhere in the run, and I had built the records from fewer facts.
  - Spreadsheet formulas were written for the typical company only.
  - Filings print page numbers in many styles ("- 3 -", "Page 7", "F-3"), and some print none.
- **แก้อย่างไร:**
  - Build each record from the full fact store with the same flow-tag rule.
  - Wrote a small formula evaluator in the tests and calculated every company's workbook (all say "Same as dashboard? Yes").
  - Trimmed and split the export into 16 parts.
  - Added footer patterns, plus "#N" or "cover page" when no number is printed, and "not located" when not found.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Checking a few sample companies only; text search for the number in the filing.

### 2026-11-05 · Download as Excel was missing on the public GitHub Pages link

- **เจออะไร:** On https://jittia.github.io/… the Calculation check had no Download as Excel button, while its message told the reader to use it.
- **สาเหตุ:** The download used claude.ai's `downloads` feature, which exists only when the page runs inside claude.ai. The built-in browser's file preview could not show the problem either: it opens a snapshot with no data files.
- **แก้อย่างไร:** Use a plain browser download (Blob + link) when there is no claude.ai runtime. Tested on a local server (`python -m http.server`, moat-site in `.claude/launch.json`), which behaves like GitHub Pages.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Opening the HTML as a file preview to test.

### 2026-11-05 · Others could not open the SEC guide PDF from GitHub

- **เจออะไร:** Jitti said others could not open `output/sec_filings_guide.pdf` from the repo; both GitHub and GitHub Pages links returned 404.
- **สาเหตุ:** The PDF was created but not committed or pushed (Jitti chose "Not now" for the save), so it existed only on this Mac.
- **แก้อย่างไร:** `/save` (round 30) committed and pushed it; the public links were checked after the push.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Nothing. While checking sources for the guide, several Investor.gov glossary addresses returned status 200 with an empty page; only pages that contain the definition are cited.

### 2026-11-05 · DUOL ROIC and P/E differed from GuruFocus: two bugs found

- **เจออะไร:** Jitti compared DUOL's clean ROIC (FY2025 55.6%) with GuruFocus's, which was about a third of ours (their figure is licensed data, so it is not quoted here). Most of the gap is method (invested capital: equity + debt − excess cash vs GuruFocus's total assets − payables; their cash buffer; operating leases in debt; their effective tax rate), but two items were bugs: (1) DUOL files its short-term investments only as held-to-maturity securities ($104M at FY2025), a tag the tool did not read, so cash was too low; (2) clean net income still contained DUOL's $232M one-time tax benefit (valuation-allowance release), so clean P/E was 16 instead of about 41.
- **สาเหตุ:** (1) The short-term investment list took the first of three tags and had no held-to-maturity tag; the 2026-11-04 Calculation check had shown the amount as "not counted" and left the decision for later. (2) The clean-up removed only pre-tax one-offs; tax one-offs went straight into net income.
- **แก้อย่างไร:** Round 31. Cash now adds the filed total, else available-for-sale + held-to-maturity (old and new tags; 412 companies gained cash in some year). Clean net income replaces a filed tax rate outside 0–50% with 21% (11.4% of company-years; the 2017 tax-reform year stands out with 771). Re-run on the same Nov 3 closes: Screener lists M1–M3 unchanged, M4 lost CRK; P/E changed for 175 companies (e.g. LYFT 2.2 → 1,343, DUOL 16 → 41); v1.1 shortlist changed 3 names (in HLT, USLM, DECK; out GFF, YOU, NVDA). The track record (track_record/*.json) is frozen and was not touched. DUOL's 12-month ROIC rose from 92% to 1,588% because average invested capital fell to $7.8M: correct under our formula, but it shows the near-zero-capital problem (10 companies above 200%), left as a separate method decision.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** The first re-run downloaded fresh prices (Nov 4) and showed 1,329 P/E changes and 18 M4 changes, mostly price moves; the Nov 3 closes were rebuilt from Yahoo (DUOL $128.00 matches the earlier run) and the run repeated with `MM_REUSE_DAILY=1`.

### 2026-11-05 · Invested-capital study: no variant passed all three rules set in advance

- **เจออะไร:** `src/mm_ic_study.py` (output/data/ic_study.json) tried 7 definitions of invested capital on the Screener as of 2026-11-03. Variant A (current) reproduced the published lists exactly (269 / 204 / 574). The rules written before the run: (1) at most 2 companies above 200% ROIC, (2) lists ≥ 80% the same and ROIC rank correlation ≥ 0.90, (3) the "not meaningful" guard drops at most 5 companies from M1 or M4.
- **สาเหตุ:** Results: the guard (average IC < 10% of revenue) removed every outlier but dropped 14 companies from M1 and 25 from M4, among them drug distributors (MCK, CAH, COR) whose capital is small next to their very large revenue: fails rule 3. Operating leases (B) kept lists 90–92% the same, and the companies hit hardest were restaurants and retailers as expected, but 9 outliers remained (rule 1). The 5% cash buffer (C) and GuruFocus-style cash (D) left 9 and 4 outliers. The GuruFocus-like definition (E) removed outliers but changed lists the most (M2 only 54% the same) and cut the ROIC of 35 software companies by more than a third, the prepaid-revenue penalty expected. Companies with negative equity were mostly not a problem: 51 sit in M1/M4 and 46 stay with the guard, because their debt keeps invested capital positive.
- **แก้อย่างไร:** Nothing adopted; the study is reported as run and the rules were not changed after seeing the results. Any new guard (e.g. a display cap) is a new test written down first.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** The revenue-scaled guard (see above).

### 2026-11-05 · Adding unrelated tags to facts.pkl changed two companies' 12-month figures (open bug)

- **เจออะไร:** After 5 balance tags were added to facts.pkl for the study (leases, payables), the all-company audit test failed: CIK 730272 gained four 12-month points and CIK 1077688 used a different filing for two points (for 2025-08-03 the original 2025 filing instead of the 2026 restatement). Facts for every existing tag were identical.
- **สาเหตุ:** Not fully traced. The likely cause is a tie in `ttm_parts` (merge_asof "nearest" matching, keyed on tag codes from `pd.factorize`): the order of tags changes which candidate wins when two are equally near.
- **แก้อย่างไร:** For now: facts.pkl restored to the round 31 file (byte-identical), study tags moved to extra_facts.pkl (`mm_extract.py extra`). The tie-break itself still needs a fix and a rule (prefer the latest filing on ties) plus a test that adding a tag never changes other values.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Adding study-only tags straight to TAGS.

### 2026-11-05 · Clean ROIC display cap: passed all five rules

- **เจออะไร:** After round 31 DUOL's clean ROIC showed as 1,588% (28 companies above 100%), a precise-looking number that mostly reflects invested capital near zero.
- **สาเหตุ:** The ratio's denominator (average invested capital) can be tiny; the round-32 study showed a guard that blanks ROIC also removes real businesses (distributors), so only the display changes.
- **แก้อย่างไร:** Round 33 (spec docs/specs/2026-11-05-roic-display-cap.md, rules written first). Above 100% the page shows "> 100%" with the exact value on hover; Deep-Dive mini charts draw it just above 100%; a ROIC change larger than 100 points shows "n.m."; the Calculation check keeps the exact value with a note. Checked: 33 data files byte-identical (no list, rank or score changed), sorting by ROIC uses the true order, all tests pass, no console errors; in the browser DUOL shows "> 100%" everywhere except the audit table.
- **ลองวิธีไหนแล้วไม่เวิร์ก:** Using the page's global formatters inside `buildDeck` broke 5 deck tests: the deck is built as a self-contained file (the tests run it alone in Node), so it got its own copy of the cap. Return on new capital (Group 2 Y, e.g. PLTR 358%) is left uncapped by design.

