# output/

ใส่ผลงานของคุณที่นี่

- ภาพหน้าจอ dashboard หรือผลวิเคราะห์ (`.png`, `.jpg`)
- ลิงก์ผลงานที่เปิดดูได้ (เขียนไว้ในไฟล์นี้)
- ไฟล์ผลลัพธ์เล็ก ๆ ที่สร้างเอง เช่น `dashboard.html`

ห้ามใส่: ไฟล์ข้อมูลดิบที่ซื้อมา (เช่น SETSMART), บทวิเคราะห์โบรกเกอร์, ข้อมูลพอร์ตจริง

## ลิงก์ผลงาน

**Phase 1.5 (current):**

| File | What it is |
|---|---|
| [`dashboard.html`](dashboard.html) | **Main result.** Catalyst-of-change radar: stage funnel, Tier A (Confirmed + AI-verified catalyst) and Tier B (Emerging) with each company's dated change events and SEC links, the AI-vetoed names, and the event study. Download and open in a browser (GitHub shows HTML as source). |
| [`dashboard.jpg`](dashboard.jpg) | Screenshot of the dashboard (funnel and the top of Tier A) |
| [`watchlist.csv`](watchlist.csv) | Tier A / B / vetoed names as data: stage, recent events, growth vs industry, margins, dilution, growth needed for 5x, 10x-stretch flag, AI catalyst + verbatim quote + SEC URL |
| [`event_study_report.md`](event_study_report.md) | Did each signal and stage lead to ≥5x more often than all companies? 2012→2021, tuning vs holdout, threshold grid |

**Phase 1 (kept for the record, superseded):**

| File | What it is |
|---|---|
| [`shortlist.csv`](shortlist.csv) | Phase 1 one-date watchlist (1 tier A, 19 tier B) |
| [`layer2_review.csv`](layer2_review.csv) | Phase 1: the 100 companies the AI reviewed, including the rejects and why |
| [`backtest_report.md`](backtest_report.md) | Phase 1 backtest (10x target, two windows) |

All numbers come from SEC EDGAR and Yahoo Finance. No licensed screener data is in these files.
