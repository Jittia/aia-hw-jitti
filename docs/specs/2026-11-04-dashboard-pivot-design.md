# Moat Momentum · Dashboard pivot to the Moat Screener — design spec

Status: written from Jitti's request and answers, 2026-11-04. For review; no code yet.

## 1. Purpose

The project has pivoted from back-testing a prediction (v1.0–v3.0, all failed on unseen data) to a **screening tool** that finds strong candidates for a deeper look. The dashboard should show only what serves that tool. Everything else leaves the page but stays in the repo (code, data, logs) so it can be called back.

**Audience:** a senior executive we want to convince and who should then use the tool alone.

## 2. New structure

| Group | Tab | Status |
|---|---|---|
| Design | Introduction | new |
| Design | Methodology | rewritten (absorbs Terminology) |
| Design | How to Use | new |
| Action | Screener | as built (round 21) + "Add to Watchlist" |
| Action | Deep-Dive | rebuilt around the four Moat Screeners |
| Action | Watchlist | new |
| Evaluation | To be designed | blank template |
| Evaluation | Archive | new: the journey in short |

The site opens on Introduction the first time, then remembers the last tab (this browser only). The logo goes to Introduction.

## 3. Removed from the page (kept in the repo)

- Tabs: Scenarios, Proof, Track record, Demo, How it works, old Methodology v1.1, Terminology.
- Deep-Dive parts tied to v1.1–v3.0: Moat Score, five themes, scenario lists, risk-gate observations, Compounder card, Moat Map card, back-test numbers.
- The page stops loading `proof_data.js`, `track_data.js`, `demo_data.js`. The files, the Python modules, the Google Sheet, `track_record/` and the logs stay as they are.
- Archive (Evaluation) summarises what was removed and why, with a link to the GitHub repo for the full record.

## 4. Design tabs

### 4.1 Introduction (business case for an executive)

1. **The pain point:** thousands of listed companies; a moat is the reason returns last, but it is slow and costly to judge one by one, and most screens look at cheapness or past growth only.
2. **What the tool does:** narrows ~1,900 US companies to a short list worth a Deep-Dive, in minutes, from public SEC filings.
3. **How we got here (honest):** we first tried to *predict* future compounders with scores and rules; three versions failed their out-of-sample tests. Lesson: a screen cannot replace judgment, but it can point judgment to the right places. So the tool screens and explains; the analyst decides.
4. **The direction we chose:** four questions from well-known research, each answering a different part of "is the moat real and growing?", plus a risk check and an overlap view.
5. **Infographics (inline SVG):** a funnel (universe → scope and risk → four Moat Screeners → overlap → Deep-Dive → Watchlist) and a "four questions" matrix.
6. **Quotes:** two or three short quotes from well-known investors on moats and durability (e.g. Buffett, Munger), each under ~30 words, with the source and year. Every quote is checked against a published source during the build; an unverified quote is not used.
7. **Close:** what the executive gets (time saved, consistent evidence, a shared watchlist) and what it is not (not a buy signal, not tested as a predictor).

### 4.2 Methodology

1. **Key concepts:** 12-month (TTM) figures from the latest 10-Q/10-K; clean figures (one-offs removed); point in time; invested capital, NOPAT, clean ROIC, cost-of-capital hurdle (9%).
2. **Screener Scope:** market value bands, sector mapping (our approximation from SIC), the three risk checks with formulas, defaults and sources.
3. **The four Moat Screeners:** for each, the question, X and Y with formulas, default lines, the research behind it (with links), what the top-right means, the two "improving" lists.
4. **Why these four and how they complement each other:** a table of what each one sees and misses (value creation now, durability of reinvestment, pricing power, price paid), and why appearing in several matters.
5. **Data sources and dates:** SEC EDGAR (filings), Yahoo Finance (prices only); retrieval dates shown.
6. **Benefits and blind spots:** strengths (consistent, fast, transparent, sourced); blind spots (no forward view, accounting quality, one hurdle for all, sector differences, missing tags, ADS and share-count issues, small-number noise). "A candidate list, not a verdict."
7. **Definitions:** every term the Screener uses (replaces the Terminology tab; v1.1-only terms are dropped).

### 4.3 How to Use

1. A simple wireframe of the Screener (Sections 1–3) with numbered callouts.
2. The workflow: set scope → apply risk check → read each Moat Screener (chart, side box, three lists) → compare in the Summary → open Deep-Dive → add to Watchlist with priority and note.
3. One worked example on real data (a company that appears in several Moat Screeners), chosen by a rule written down first: the top company of the Summary list ① with default settings.
4. Tips: adjusting lines, reading "not tested", clicking a list row to see the trail, sorting the Summary.

## 5. Action tabs

### 5.1 Screener

As built in round 21, plus an **Add to Watchlist** button (☆ / ★) on each Summary row and in each side box. A company already on the list shows ★.

### 5.2 Deep-Dive

1. **Company brief (SEC only):**
   - name, ticker, exchange, sector (our mapping) and SEC industry, state or country of incorporation, fiscal year end;
   - business description: the first paragraphs of Item 1 "Business" of the latest 10-K (about 1,000 characters), with the filing link and date; if extraction fails, "Not extracted" plus the 10-K link;
   - website: from SEC submissions where the company filed one; otherwise the SEC company page;
   - founding year: only when the 10-K text states it ("founded in …", "incorporated in …"), shown with the quoted phrase; otherwise left blank.
2. **Key numbers (12 months):** revenue and 3-year growth, gross and operating margin, net income, free cash flow, market value, P/E, EV/EBIT, earnings yield, clean ROIC, net debt ÷ EBITDA, interest cover; each with its source and date.
3. **Four Moat Screener results:** for each, the quadrant now, the percentile rank, the list it is in (①/②/③ or none), and a 5-point trend (now and 4 quarters back) as a small chart.
4. **Why look deeper / what to watch:** rule-based sentences generated from the numbers, the same rules for every company (e.g. "in the top-right of 3 of 4 Moat Screeners", "return on new capital fell for 3 quarters", "interest cover not tested: no interest expense tagged").
5. **12-quarter charts** that matter to the moat (revenue, gross and operating margin, ROIC) are kept from the current Deep-Dive.
6. An Add to Watchlist button.

### 5.3 Watchlist

1. Stored in the published page's database (`db` capability): one document per company `{cik, ticker, priority, note, added, updated}`. Everyone with access sees the same list; Claude can read it. Default access rules (signed-in people read; Contributors and up write).
2. Table: the same columns as Screener Section 3 (Company / Market cap / P/E TTM / # of moats / M1–M4 / six measures / Deep-Dive), plus **Priority** (A/B/C select) and **Note** (a large text box, several lines, grows with the text, saved automatically after typing stops). Remove button per row. Sort by any column; filter by priority.
3. Numbers are today's (live run), not frozen at the time of adding; the "added" date is shown.
4. Outside claude.ai (local preview) the database is unavailable: the list falls back to this browser only, with a clear notice.
5. Each row has a **Pitch deck** button (section 5.4).

### 5.4 Pitch deck (from a Watchlist row)

**Purpose:** a 5-slide HTML presentation to pitch one watchlist company to a senior executive. It follows the layout of a sell-side or buy-side equity note (summary first, evidence next, risks stated, sources on every page).

**How it works:**
- Built in the page from the tool's data and the row's Priority and Note. No new data, no AI-written text, so every company is presented the same way and every number traces to the tool.
- Opens full screen inside the dashboard (arrow keys, Esc to close).
- **Download .html** saves a self-contained file (fonts, styles and charts inline) that opens in any browser and prints to PDF one slide per page. It uses the `downloads` capability; the viewer confirms each save.
- Slides are 16:9 and scale down for a phone.

**Corporate identity (same on every slide):** Moat Momentum logo and name, the dashboard's navy / teal palette, serif headings and sans-serif body, a header band with company and ticker, and a footer with "Moat Momentum · screening output, not investment advice", data dates (SEC retrieved, price close) and the page number.

| # | Slide | Content |
|---|---|---|
| 1 | Investment snapshot | Company, ticker, sector, industry, market value, price date; Priority badge; one-line thesis (the first sentence of the Note, else the rule-based summary); key-stat strip: revenue, 3-year growth, clean ROIC, P/E, earnings yield, # of Moat Screeners passed |
| 2 | Business overview | 10-K business description (with link and date); key numbers table (12 months and 3 years back); 12-quarter revenue and margin chart |
| 3 | Moat assessment | Four mini 2×2 charts (company's dot, its 4-quarter trail, the lines), with quadrant, percentile and list (①/②/③) for each; one line on how the four fit together |
| 4 | Valuation and risk | P/E, EV/EBIT and earnings yield against the universe median; the three risk checks (pass / fail / not tested); rule-based "what to watch" |
| 5 | Analyst view and next steps | The full Note; rule-based "why look deeper"; standard Deep-Dive questions per weak or missing area; sources and method in short; disclaimer |

**Empty or missing data:** a section without data says so ("not available in filings") rather than hiding, so the five slides keep the same layout for every company. An empty Note shows "No analyst note yet".

## 6. Evaluation tabs

- **To be designed:** a blank template page with a title and a short "coming later" note.
- **Archive:** a short timeline: v1.0 Moat Score → v1.1 → v2.0 Compounder Signal → v3.0 Moat Map → Screener; for each, the idea, the result (with the honest failed numbers) and the lesson; the pivot decision; a link to the repo's `prompts.md` and `PROJECT_MEMORY.md`.

## 7. Data and code

| Unit | Change |
|---|---|
| `src/mm_brief.py` (new) | Item 1 description, founding-year phrase and website for each universe company, from the latest 10-K and SEC submissions → `output/data/brief_data.js` (cached; SEC client with User-Agent and rate limit) |
| `src/mm_run.py` | unchanged except loading the brief data path into meta if needed |
| `output/moat_momentum.html` | new tab structure; Introduction, Methodology, How to Use, Deep-Dive, Watchlist, Evaluation pages; old views removed from the page |
| `tests/` | unit tests for the description extractor (skips the table of contents, a known past failure), the founding-year phrase, the rule-based Deep-Dive sentences (Node), the watchlist store fallback, the pitch deck builder (Node: always 5 slides in the same order, company data present, missing data shown as "not available", no unescaped HTML from the Note) |

## 8. Product rules

- Every number shows its source and date. Plain language. No investment advice wording ("candidate", not "buy").
- Light, dark and 375 px; no console errors; the page works when the database is unavailable.
- Capabilities declared on publish: `db` (Watchlist) and `downloads` (pitch deck file).
- Out of scope: Google Sheet and pitch docs (still describe v1.1; a separate update if wanted), new back-tests.
