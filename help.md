# ติดตรงไหน 3 ข้อ

> ผู้สอนอ่านไฟล์นี้ก่อนวันเสาร์ เพื่อเตรียมคำตอบให้คุณใน Repair Clinic เขียนให้เจาะจงที่สุด
>
> (Drafted by AI from the real results of 2026-11-03, to be reviewed and edited by Jitti.)

## 1. "Strengthening" does not predict further strengthening (mean reversion)

- **อยากให้เกิดอะไร:** A signal that catches a moat while it is forming, so picks keep improving after they are flagged.
- **ลองทำอะไรไปแล้ว:**
  - Methodology v1.0 ranks 13 indicators within SIC industries on level, 5-year slope and consistency (30/50/20), with a risk gate first.
  - Settings were locked before a point-in-time back-test (2013–2023), and 17 variants were tested (weights ±10, level-heavy blend, stricter or no risk gate, 2 or 4 themes).
- **เกิดอะไรขึ้นจริง:**
  - Only 26.9% of shortlist picks kept improving their industry rank over 3 years, against 48.6% for other companies; 38.0% fell by more than 10 points.
  - Against companies that started at the same rank, picks ended 3.4 points lower.
  - It looks like the screen catches companies at the top of their improvement.
  - **Question:** which measures resist mean reversion? For example persistence over 7–10 years, distance from a prior peak, or improvement that is not from a cyclical trough. And how would you design v1.1 so that it is decided before testing on 2018–2023?

## 2. Market validation without survivorship-free prices

- **อยากให้เกิดอะไร:** A fair market test that includes companies that were acquired, delisted or failed.
- **ลองทำอะไรไปแล้ว:**
  - Yahoo prices for companies still trading.
  - SEC filings (8-K item 5.01, SC 14D9, DEFM14A, item 1.03) to classify the missing ones.
  - Three scenarios: neutral, worst case, survivors only.
  - IBKR has delisted stocks but returns one stock per call.
- **เกิดอะไรขึ้นจริง:**
  - 31% of past picks and 40% of the past universe no longer trade.
  - The shortlist returned 12.5–14.7% a year across the scenarios (S&P 500 14.3%), so the conclusion holds.
  - The equal-weight universe still looks flattered by survivorship.
  - **Question:** is a paid survivorship-free source (e.g. Norgate or Sharadar) worth it at this stage? Or is there a free way to get final delisting prices?

## 3. How to pitch an honest negative result

- **อยากให้เกิดอะไร:** A pitch that investors take seriously, without claiming more than the evidence shows.
- **ลองทำอะไรไปแล้ว:** The deck and whitepaper position the product as a transparent, self-testing research tool. Every number comes from the validation outputs; prices and the ask are left as marked assumptions.
- **เกิดอะไรขึ้นจริง:** The core insight ("a strengthening moat shows up 1–3 years before it is recognised") is not supported yet, and there is no excess return.
  - **Question:** is "transparent quality screen with a published track record" a fundable product, or should I fix the signal (point 1) before pitching at all? What would you want to see in the first 6 months?
