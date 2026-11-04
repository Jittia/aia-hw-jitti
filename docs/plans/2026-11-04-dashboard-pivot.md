# Moat Momentum · Dashboard pivot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the dashboard around the Moat Screener: Design (Introduction, Methodology, How to Use), Action (Screener, Deep-Dive, Watchlist with a 5-slide pitch deck), Evaluation (To be designed, Archive); remove v1.0–v3.0 content from the page.

**Architecture:** One new Python step (`mm_brief.py`) reads each universe company's latest 10-K and SEC submissions record into `output/data/brief_data.js`. Everything else is in `output/moat_momentum.html`. Pure JS functions (Deep-Dive sentences, watchlist store, deck builder) are unit-tested in Node by extracting them from the page, as `tests/test_screener_js.py` already does. The Watchlist uses the artifact `db` capability, with a browser-storage fallback; deck files use `downloads`.

**Tech Stack:** Python 3.10 (`.venv`), pandas, `sec_client.SecClient`; vanilla JS/SVG; Node for JS tests; claude.ai artifact runtime 0.2.96 (`db`, `downloads`).

**Spec:** `docs/specs/2026-11-04-dashboard-pivot-design.md` (binding).

## Global Constraints

- AGENTS.md: no commit or push until Jitti types save; every number shows source and date; trust sources only (SEC EDGAR for company data, Yahoo Finance for prices); plain language; replies in English (Jitti's choice).
- Removed views leave the page only: their Python modules, data files, `track_record/`, Google Sheet and logs stay untouched.
- No investment-advice wording: "candidate", "screening output, not investment advice".
- Every page: light, dark, 375 px, no console errors; works with the database unavailable.
- Quotes: each verified against a published source (WebSearch/WebFetch), under ~30 words, with attribution and year.

## Review Focus

1. A 10-K whose first "Item 1. Business" match is the table of contents (a known past failure, PROJECT_MEMORY 2026-11-02): the description must come from the real section, or show "Not extracted" with the 10-K link — never TOC text. Test in Task 1.
2. Watchlist with the database unavailable (local preview, signed-out viewer) or read-only (writes refused): fallback or a clear message, never a crash or silent loss. Test in Task 5.
3. A Note containing `<script>`, `&`, quotes or 5,000 characters: escaped everywhere (table, deck, download); the deck's slide 5 shows a long note without breaking the layout (it truncates with "continued in the dashboard"). Test in Task 6.
4. A watchlist company no longer in today's data (left the universe): it stays listed, marked "not in today's data", and its deck still builds with "not available". Test in Tasks 5–6.
5. Deck download declined by the viewer, or `downloads` unavailable: no error; the button hides when unavailable. Check in Task 6.

---

### Task 1: Company brief data (`mm_brief.py`)

**Files:** Create `src/mm_brief.py`, `tests/test_brief.py`; output `output/data/brief_data.js`

**Interfaces:**
- Produces: `item1_description(html: str, max_chars=1100) -> str | None` (skips the TOC: uses the "Item 1. Business" heading followed by ≥ 400 characters of prose before "Item 1A"; returns whole sentences); `founded_phrase(text) -> {"year": int, "phrase": str} | None` (matches "founded in YYYY", "incorporated in … in YYYY", "began operations in YYYY"; the year must be 1800–the filing year); `website(text) -> str | None` (matches "our (internet) website (address) is/at (https://)www.…"; excludes sec.gov); `build(companies, universe_ciks) -> dict` → `window.MM_BRIEF = {meta: {retrieved, source}, co: {cik: {desc, founded, website, hq, inc, fye, url, filed}}}` (hq and inc from submissions.zip addresses; cached raw 10-K text heads under `data/cache/mm/briefs/`).
- [ ] **Step 1: Failing tests:** `test_skips_table_of_contents` (HTML with a TOC line "Item 1. Business 4" then the real section → returns the real first paragraph); `test_none_when_no_section`; `test_founded_phrase` ("was founded in 1998" → 1998; "incorporated in Delaware in 2004" → 2004; "in 2030" with filing year 2026 → None); `test_website` ("Our website address is www.example.com" → "www.example.com"; "www.sec.gov" → None).
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS; run for the universe (background, ~20 min); print coverage of desc / founded / website and 5 random descriptions for a manual check of TOC leakage.

### Task 2: Site structure and removals

**Files:** Modify `output/moat_momentum.html`

- [ ] **Step 1:** New `TAB_GROUPS`: Design (intro "Introduction", method "Methodology", howto "How to Use"), Action (screener, deepdive, watchlist), Evaluation (tbd "To be designed", archive "Archive"). Default view: last tab from browser storage, else `intro`; logo → `#intro`. Stop loading `proof_data.js`, `track_data.js`, `demo_data.js`; load `brief_data.js`.
- [ ] **Step 2:** Remove from the page: `viewScreener` (Scenarios), `viewProof`, `viewTrack`, `viewDemo`, `viewHow`, old `viewMethod`, `viewLearn`, `scenarioCompare`, map/compounder cards and the v1.1 controls; keep the shared helpers the remaining views use. Old hashes (`#scenarios`, `#proof`, …) route to Archive.
- [ ] **Step 3:** Archive page (timeline v1.0 → v1.1 → v2.0 → v3.0 → Screener with the idea, the result and the lesson, numbers from `prompts.md`, links to the repo's `prompts.md` and `PROJECT_MEMORY.md`); To be designed page (title and "coming later").
- [ ] **Step 4:** Browser: every tab renders, old hashes land on Archive, no console errors.

### Task 3: Design pages (Introduction, Methodology, How to Use)

**Files:** Modify `output/moat_momentum.html`

- [ ] **Step 1:** Verify 2–3 investor quotes on moats and durability with WebSearch/WebFetch (exact wording, speaker, year, source URL); record them in the task notes. Drop any quote that cannot be verified.
- [ ] **Step 2:** Introduction per spec §4.1: the pain point, what the tool does, how we got here (honest failures, from Archive numbers), the direction chosen; inline SVG funnel with today's live counts (universe → scope → risk → Moat Screeners → overlap ①); "four questions" matrix; quotes; closing "what you get / what it is not".
- [ ] **Step 3:** Methodology per spec §4.2: concepts, Screener Scope, the four Moat Screeners (question, X/Y formulas, default lines, research links reused from the round 20 verified list), complement table (what each sees / misses), sources and dates, benefits and blind spots, definitions (the round 20 Screener terms plus clean ROIC, NOPAT, invested capital, TTM, EV).
- [ ] **Step 4:** How to Use per spec §4.3: wireframe SVG of Screener Sections 1–3 with numbered callouts; the workflow steps; worked example = top company of Summary list ① with default settings (rule stated on the page, computed live); tips.
- [ ] **Step 5:** Browser: light, dark, 375 px; links open in a new tab.

### Task 4: Deep-Dive rebuild

**Files:** Modify `output/moat_momentum.html`; Test `tests/test_screener_js.py`

**Interfaces:**
- Produces (JS, pure): `ddNotes(r, lines, inLists) -> {look: string[], watch: string[]}` from a company's `SCR.co` row, the current lines and its list memberships. Rules (same for all): look = top-right count ≥ 2 ("in the top-right of N of 4 Moat Screeners"), in ② or ③ ("improving toward the top-right in …"), clean ROIC above the line for all 5 points, gross margin up 4 quarters in a row; watch = any risk check fail or not tested (named), Y or X falling 3 of the last 4 quarters in any group, missing values per group ("Compounding Runway not shown: capital grew less than 10%"), extreme values (pinned off the chart).
- [ ] **Step 1: Failing tests (Node):** `test_dd_notes_strengths`, `test_dd_notes_watch_items` (risk not tested, falling ROIC, missing G2), `test_dd_notes_empty_row` (no data → no exception, one "not enough data" item).
- [ ] **Step 2:** FAIL. **Step 3:** Implement `ddNotes`; new `viewDeep`: brief (spec §5.2.1, with "Not extracted" fallback), key numbers (12 months, from `c.mm`, `MM_DEEP` and `SCR.co`, each with source/date), four Moat Screener cards (quadrant, percentile among all companies with default lines, list ①②③, mini 2×2 SVG with 4-quarter trail), notes, kept 12-quarter charts (revenue, margins, ROIC), ☆ Add to Watchlist. Company picker (search box) stays.
- [ ] **Step 4:** PASS; browser check on 3 companies (one large, one with missing G2, one ADS: BeOne).

### Task 5: Watchlist

**Files:** Modify `output/moat_momentum.html`; Test `tests/test_screener_js.py`

**Interfaces:**
- Produces (JS): `wlStore` with `init() -> Promise<"db"|"local"|"none">`, `all() -> entries`, `put(entry)`, `remove(cik)`, `onChange(fn)`; entry `{cik, ticker, priority: "A"|"B"|"C"|"", note, added, updated}`. Uses `claude.use("db")` collection `watchlist` (doc id = cik; `onSnapshot` once); falls back to `localStorage["mm-watchlist"]` when `use` resolves null; "none" if storage throws. Write failures (`not_granted`, rules) surface a message and keep the typed text.
- [ ] **Step 1: Failing tests (Node, with stubbed `claude` and `localStorage`):** `test_store_local_fallback`, `test_store_db_put_and_remove`, `test_store_write_refused_keeps_text`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement store; ☆/★ on Screener Summary rows and side boxes and in Deep-Dive; Watchlist view: Summary columns + Priority select + Note (auto-growing textarea, saves 800 ms after typing stops and on blur, shows "Saved"/"Not saved") + added date + Remove + Pitch deck; sort by any column, filter by priority; rows not in today's data marked.
- [ ] **Step 4:** PASS; browser: add, edit note, change priority, reload keeps them (local fallback), remove.

### Task 6: Pitch deck

**Files:** Modify `output/moat_momentum.html`; Test `tests/test_screener_js.py`

**Interfaces:**
- Produces (JS, pure): `buildDeck(d) -> string` (complete `<!doctype html>` document, inline CSS and SVG, no external requests) where `d = {co, brief, scr, deep, entry, meta, lines, medians}`; exactly 5 `<section class="slide">` in spec §5.4 order; every user text escaped; missing data → "not available in filings"; note over 1,800 characters truncated on slide 5 with "continued in the dashboard". Print CSS: one slide per page, 16:9.
- [ ] **Step 1: Failing tests (Node):** `test_deck_five_slides_in_order`, `test_deck_escapes_note`, `test_deck_missing_data`, `test_deck_long_note_truncated`, `test_deck_no_external_urls_except_sources` (no `<script src`/`<link` to fonts).
- [ ] **Step 2:** FAIL. **Step 3:** Implement `buildDeck` (Moat Momentum identity: logo SVG, palette and fonts from the page tokens, header band, footer with disclaimer, dates, page n/5); presenter overlay (iframe `srcdoc`, arrows, Esc, focus trap); Download .html via `claude.use("downloads")` (button hidden when null; a decline is not an error).
- [ ] **Step 4:** PASS; browser: open deck for 2 companies (one complete, one with missing data), arrow through, 375 px.

### Task 7: Review, publish, verify

- [ ] Independent review (fresh reviewer, Opus) with this Review Focus; fix Critical/Important with a failing test first; republish with `capabilities: {db: {}, downloads: true}`; one `ArtifactData list` of `watchlist`; report rulings and deferred minors; tell Jitti it is ready for save.
