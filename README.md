# Moat Momentum (US, SEC EDGAR)

> การบ้าน AI Investor Alpha · **Strengthening moats, found in the filings.**

| | |
|---|---|
| **ชื่อเล่น** | Jitti |
| **กลุ่ม** | G03 |
| **โจทย์ 1 บรรทัด** | Find US companies whose competitive moat is strengthening in their official SEC filings (returns on capital, pricing power, scale, peer gap), before they become recognised leaders, and prove the signal with point-in-time data |
| **ลิงก์ผลงาน** | [web page](output/moat_momentum.html) (download `output/` and open) · [Proof](output/proof.html) · [spot-check](output/spotcheck.html) · [brand guide](output/brand_guide.html) · [spec](spec.md) |
| **สถานะ** | พร้อมตรวจ: steps 1–9 of the brief done (pitch pack drafted) |

![Moat Momentum screener](output/dashboard.jpg)

---

## Results (as of 2026-11-03, Methodology v1.0)

- **What it does:** scores 1,870 US-listed companies on whether their competitive position is improving, using only SEC 10-K data: clean ROIC vs a 9% hurdle, pricing power, scale, gains against SIC peers and profit quality. A risk gate runs first (debt, Altman Z'', Beneish, dilution, stock pay, acquisitions). Output: a 25-name shortlist, a Deep-Dive for every company, a Google Sheet, and a frozen, fingerprinted track record.
- **Data checked against 10-Ks:** 331 of 333 non-zero inputs found in the filing text, 60 of 60 hand recalculations match ([spot-check](output/spotcheck.html)).
- **Does it work?** Point-in-time back-tests, settings locked before the run, everything tried reported ([Proof](output/proof.html)):
  - Picks stay above their industry 3 years later (+8.3 peer-rank points, clean ROIC +5.4 pp).
  - But they do **not** keep improving: 26.9% kept improving vs 48.6% for other companies; 38.0% deteriorated vs 21.8%. The same holds in all 17 variants.
  - Market test Jul 2013 – Oct 2026: 14.3% a year, the same as the S&P 500 (14.3%), with higher volatility (18.6% vs 14.3%).
- **Decision:** v1.0 is accepted as a screen for high-quality, improving businesses, not as a predictor ([spec](spec.md) §7b). A v1.1 must be designed in advance and tested on unseen years.
- **Pitch pack** (Google Docs and Slides, in the founder's Drive): methodology whitepaper, one-pager and a 13-slide deck. Every number comes from the validation outputs; prices, volumes and the ask are left as marked assumptions. HTML reading copies are in [`output/pitch/`](output/pitch/).
- **Earlier work:** the catalyst-of-change radar (Phase 1 / 1.5) is kept in [`archive/`](archive/phase1.5-catalyst-radar/) and under the git tag `phase1.5-catalyst-radar`. Why it was replaced: `prompts.md` round 9.
- **Method in detail:** [`spec.md`](spec.md), [`prompts.md`](prompts.md) rounds 9–12, [`PROJECT_MEMORY.md`](PROJECT_MEMORY.md), [`src/`](src/), [`tests/`](tests/) (21 tests).

## ไฟล์ใน repo นี้

| ไฟล์ | ใส่อะไร |
|---|---|
| `spec.md` | โจทย์ของคุณ 5 หัวข้อ (หัวใจของการบ้าน) |
| `prompts.md` | บันทึกขั้นตอนทุกรอบ: ทำอะไร, prompt, ผลที่ได้, ตัดสินใจเพราะอะไร |
| `PROJECT_MEMORY.md` | ปัญหาที่เจอ, วิธีแก้, และกฎที่ได้จากบทเรียน |
| `output/` | ภาพหน้าจอ หรือลิงก์ผลงาน |
| `help.md` | ติดตรงไหน 3 ข้อ ให้ผู้สอนเตรียมคำตอบ |
| `archive/` | งานรุ่นก่อน (catalyst-of-change radar) เก็บไว้ดูย้อนหลัง |
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
- [x] `prompts.md` มีบันทึกอย่างน้อย 3 รอบ และทุก commit มี entry คู่กัน (12 rounds)
- [x] `PROJECT_MEMORY.md` มีปัญหาหรือบทเรียนอย่างน้อย 1 ข้อ
- [x] `output/` มีภาพหรือลิงก์อย่างน้อย 1 ชิ้น
- [ ] `help.md` เขียนครบ 3 ข้อ (AI draft for Moat Momentum written 2026-11-03; Jitti to review and edit)
- [x] ไม่มี key, password หรือข้อมูลพอร์ตจริงในทุกไฟล์
- [ ] ส่งลิงก์แล้ว
