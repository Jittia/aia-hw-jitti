# output/

ใส่ผลงานของคุณที่นี่

- ภาพหน้าจอ dashboard หรือผลวิเคราะห์ (`.png`, `.jpg`)
- ลิงก์ผลงานที่เปิดดูได้ (เขียนไว้ในไฟล์นี้)
- ไฟล์ผลลัพธ์เล็ก ๆ ที่สร้างเอง เช่น `dashboard.html`

ห้ามใส่: ไฟล์ข้อมูลดิบที่ซื้อมา (เช่น SETSMART), บทวิเคราะห์โบรกเกอร์, ข้อมูลพอร์ตจริง

## ลิงก์ผลงาน

| File | What it is |
|---|---|
| [`dashboard.html`](dashboard.html) | **Main result.** One self-contained page: screening funnel, the 20-name watchlist (tier A / B) with the filing quote and SEC link per company, what the AI found in the top 100, and the backtest. Download and open in a browser (GitHub shows HTML as source). |
| [`shortlist.csv`](shortlist.csv) | The watchlist as data: tier, catalyst type, driver, verbatim evidence + SEC URL, Layer 1 numbers |
| [`layer2_review.csv`](layer2_review.csv) | All 100 companies the AI reviewed, including the rejects and why |
| [`backtest_report.md`](backtest_report.md) | Backtest method, every variant, every 10-bagger and why it was or was not caught |

All numbers come from SEC EDGAR and Yahoo Finance. No licensed screener data is in these files.
