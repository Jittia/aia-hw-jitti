# 10-Bagger Catalyst Watchlist Scanner

> การบ้าน AI Investor Alpha · Phase 1 (US)

| | |
|---|---|
| **ชื่อเล่น** | Jitti |
| **กลุ่ม** | G03 · 10-bagger catalyst watchlist |
| **โจทย์ 1 บรรทัด** | Find companies that could return 10x in 5 years because of a *new* catalyst (new TAM, new S-curve, turnaround, new market), proven by the numbers first, not by the news |
| **ลิงก์ผลงาน** | [`output/`](output/): [dashboard](output/dashboard.html) (download and open), [watchlist CSV](output/shortlist.csv), [backtest report](output/backtest_report.md) |
| **สถานะ** | พร้อมตรวจ (Phase 1: US) |

![Dashboard](output/dashboard.jpg)

---

## Results (Phase 1, as of 2026-11-02)

- **Pipeline:**
  - **Layer 1:** 3,073 US stocks → 2,499 companies that file quarterly 10-Qs → scored on SEC XBRL numbers (revenue growth and acceleration, margin change, turnaround, dilution, size and 10x plausibility, acquisition penalty).
  - **Layer 2:** AI reads the top 100 companies' own filings; every quote is verified by code → **20-name watchlist**.
- **Watchlist:**
  - **Tier A (confirmed catalyst):** 1 name, DERM (new product Emrosi = 44% of product revenue).
  - **Tier B (watch next quarter):** 19 names.
  - Most of the top 100 were *not* new catalysts: 32 cyclical rebounds, 13 one-offs, 23 with no clear driver.
- **Backtest** (point-in-time, survivors only):
  - The top 100 held 5 / 3 ten-baggers in the 2019 / 2018 windows, **3.4x / 2.3x better than random**, with 13 / 15 names returning 5x+.
  - Small companies (< $300M) became 10-baggers ~10x more often than $1–10B companies.
- **Accuracy:**
  - TTM revenue matches an independent screener within 1% for 96.5% of companies.
  - 19/19 hand-checked inputs for DERM, TRT and AAPL match their filings.
  - 7 tests pass.
- **Limits:**
  - About half of all 10-baggers could not be caught on the start date (revenue still falling, or no revenue yet).
  - The backtest ignores delisted companies.
  - Weights were chosen on the same two windows, so the real test is tracking this list forward. See [`help.md`](help.md).
- **Method in detail:** [`spec.md`](spec.md) (the brief), [`prompts.md`](prompts.md) (7 rounds: what, why, results), [`PROJECT_MEMORY.md`](PROJECT_MEMORY.md) (problems and rules learned), [`src/`](src/) (code).

## ไฟล์ใน repo นี้

| ไฟล์ | ใส่อะไร |
|---|---|
| `spec.md` | โจทย์ของคุณ 5 หัวข้อ (หัวใจของการบ้าน) |
| `prompts.md` | บันทึกขั้นตอนทุกรอบ: ทำอะไร, prompt, ผลที่ได้, ตัดสินใจเพราะอะไร |
| `PROJECT_MEMORY.md` | ปัญหาที่เจอ, วิธีแก้, และกฎที่ได้จากบทเรียน |
| `output/` | ภาพหน้าจอ หรือลิงก์ผลงาน |
| `help.md` | ติดตรงไหน 3 ข้อ ให้ผู้สอนเตรียมคำตอบ |
| `AGENTS.md` | คำสั่งให้ AI ทุกค่ายทำงานใน repo นี้ (`CLAUDE.md` และ `GEMINI.md` ชี้มาที่ไฟล์นี้) |
| `.claude/commands/save.md` | ขั้นตอนของคำสั่ง `/save` |

## ก่อนเริ่มทำการบ้านทุกครั้ง

- [ ] เปิดโฟลเดอร์ `homework/aia-hw-…` ของคุณเป็นที่ทำงานใน Claude
- [ ] ถามว่า "ตอนนี้ทำถึงไหน" Claude ต้องตอบจาก `prompts.md` ได้ (ถ้าตอบไม่ได้ = เปิดผิดโฟลเดอร์)
- [ ] เช็ก model · effort · permission
- [ ] ดูคอมเมนต์ผู้สอนในแท็บ Issues ของ repo บน GitHub

ระหว่างทำ: เปิด Plan mode ก่อนงานใหม่ · ทำทีละรอบ · ทุกตัวเลขต้องมี source · ติดตรงไหนจดลง `help.md`

## บันทึกงานทุกรอบ: พิมพ์ `/save`

ทำงานเสร็จแต่ละรอบ ให้พิมพ์ `/save` ใน Claude (ใส่สรุปสั้น ๆ ต่อท้ายได้ เช่น `/save ร่าง spec รอบแรก`) AI จะทำให้ครบ:

1. ตรวจว่าไม่มี key หรือข้อมูลส่วนตัว
2. เพิ่มบันทึกขั้นตอนใน `prompts.md`
3. บันทึกปัญหาและบทเรียนใน `PROJECT_MEMORY.md` ถ้ามี
4. commit ด้วยข้อความ `รอบ N: ทำอะไร` แล้ว push ขึ้น GitHub

ใช้ Codex หรือ Gemini: พิมพ์ว่า `save` ได้เหมือนกัน (ขั้นตอนเดียวกัน อยู่ใน `.claude/commands/save.md`)

ถ้า commit เองหรืออัปโหลดผ่านหน้าเว็บ GitHub ให้เขียน entry ใน `prompts.md` เองตามแบบฟอร์มในไฟล์

## ไทม์ไลน์

| วัน | ทำอะไร |
|---|---|
| เสาร์ 31 ต.ค. · 17:45 | repo + spec ร่างแรก |
| **พุธ 4 พ.ย. · 21:00** | **Deadline: ส่งฉบับพร้อมตรวจ** |
| พฤ–ศ 5–6 พ.ย. | ผู้สอนคอมเมนต์ใน Issues ของ repo นี้ |
| เสาร์ 7 พ.ย. · 13:30 | Repair Clinic ในห้อง |

ส่งลิงก์ repo ครั้งเดียวในวันเรียน ผ่าน **Google Form ที่ผู้สอนแจกในห้อง (สแกน QR บนจอ)** งานที่ `/save` เพิ่มภายหลังจะอัปเดตใน repo เอง ไม่ต้องส่งซ้ำ

## ห้ามขึ้น Public

repo นี้ใครก็เปิดดูได้ ห้ามใส่สิ่งเหล่านี้เด็ดขาด

- API key · password · token · ไฟล์ `.env`
- พอร์ตจริง · จำนวนหุ้น · เลขบัญชี · ข้อมูลส่วนตัว
- ข้อมูล SETSMART ที่ซื้อมา (ไฟล์ดิบ)
- บทวิเคราะห์โบรกเกอร์ (ติดลิขสิทธิ์)

ถ้าเผลอ push key ขึ้นไปแล้ว: **เปลี่ยน key ใหม่ทันที** การลบไฟล์ทิ้งอย่างเดียวไม่พอ เพราะประวัติใน git ยังเก็บไว้

## เช็กก่อนส่ง

- [x] repo เป็น Public และเปิดได้จากหน้าต่าง incognito (checked 2026-11-02: page loads without login)
- [x] `spec.md` ครบ 5 หัวข้อ
- [x] `prompts.md` มีบันทึกอย่างน้อย 3 รอบ และทุก commit มี entry คู่กัน (7 rounds)
- [x] `PROJECT_MEMORY.md` มีปัญหาหรือบทเรียนอย่างน้อย 1 ข้อ
- [x] `output/` มีภาพหรือลิงก์อย่างน้อย 1 ชิ้น
- [ ] `help.md` เขียนครบ 3 ข้อ (AI draft written; Jitti to review and edit)
- [x] ไม่มี key, password หรือข้อมูลพอร์ตจริงในทุกไฟล์
- [ ] ส่งลิงก์แล้ว
