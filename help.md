# ติดตรงไหน 3 ข้อ

> ผู้สอนอ่านไฟล์นี้ก่อนวันเสาร์ เพื่อเตรียมคำตอบให้คุณใน Repair Clinic เขียนให้เจาะจงที่สุด
>
> (Drafted by AI from this week's results on 2026-11-02, to be reviewed and edited by Jitti.)

## 1. Half of the 10-baggers cannot be caught by a "numbers first" rule

- **อยากให้เกิดอะไร:** Catch more future 10-baggers early, while still requiring some hard evidence (not management talk).
- **ลองทำอะไรไปแล้ว:** Backtested as of 2019-12-31 and 2018-12-31 (`output/backtest_report.md`). Switched the growth gate off to see the cost. Tested a "revenue at a new high" signal.
- **เกิดอะไรขึ้นจริง:** About half the 10-baggers had **shrinking revenue** on the as-of date (NVDA −19% in 2019, GME, MOD, STRL) or no revenue yet (biotech). Turning the gate off only added one hit, because those companies still rank low. **Question:** which *early, still quantitative* signals would you add, such as backlog, remaining performance obligations, deferred revenue, insider buying (Form 4) or capex ramps? And how would you avoid them flagging every cyclical trough?

## 2. How to run a backtest without survivorship bias, on a free budget

- **อยากให้เกิดอะไร:** Include companies that later went bankrupt, were acquired or delisted, so hit rates and returns are not optimistic.
- **ลองทำอะไรไปแล้ว:** Fundamentals come from SEC EDGAR, which keeps delisted filers. The universe and prices come from today's listings and Yahoo Finance.
- **เกิดอะไรขึ้นจริง:** Yahoo has no prices for most delisted tickers, so the population is "listed today" only, and the bias is disclosed. **Question:** is there a free or cheap source of delisted US prices or final returns (e.g. via GuruFocus, CRSP-like data, or SEC delisting forms) that is good enough for this?

## 3. Too few confirmed catalysts, and small samples for tuning

- **อยากให้เกิดอะไร:** A shortlist of 10–20 names with *confirmed* structural catalysts, and weights I can trust.
- **ลองทำอะไรไปแล้ว:**
  - AI readers reviewed the top 100 using filing text only, with every quote verified by code.
  - Added an acquisition flag (cash paid + goodwill added), which pushed 15 acquisition-driven names out of the top 100.
  - Compared 8 weight variants on two windows.
- **เกิดอะไรขึ้นจริง:** Only **1** confirmed (Tier A: DERM) plus 19 "watch" names, mostly low-confidence turnarounds. Each window has only ~25 ten-baggers, so 1–2 hits between variants is noise, and I had to judge on 5x+ counts and median returns instead. **Question:** how do professionals separate a self-help turnaround from a cyclical rebound in the numbers? And is there a sounder way to compare scoring variants with so few events (e.g. bootstrap, more start dates, or 5x as the target)?
