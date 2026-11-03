# Moat Momentum v2.0 · Compounder Signal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hand-weighted Moat Score ranking with a Compounder Signal whose signals are chosen on 2013–2019 quarterly screens and tested once on 2020–2023, then ship it as Methodology v2.0.

**Architecture:** New modules build point-in-time quarterly and TTM rows (`mm_quarterly`), the 10 signals per screen date (`mm_signals`), the six-condition winner label (`mm_outcomes`), and the training/test run (`mm_discover`). The existing fiscal-year engine (`score_as_of` with `ttm=False`) keeps providing universe B, the risk gate and the context Moat Score. Live run, web page, Sheet and track record then switch to the signal.

**Tech Stack:** Python 3.10 (`.venv`), pandas, numpy, PyYAML, unittest; one static HTML page with vanilla JS; Yahoo monthly prices already cached in `data/cache/mm/prices_monthly.pkl`.

**Spec:** `docs/specs/2026-11-03-compounder-signal-design.md` (reading copy `output/compounder_signal_spec.html`). Read it before any task.

## Global Constraints

- Repo rules (AGENTS.md): **no git commit or push except when Jitti types save / `/save`**. Each task ends with a full test run instead of a commit. No API keys, tokens or paid data in any file. Every number shown has a source and retrieval date.
- Point-in-time: a screen dated D uses only facts with `filed <= D`. Outcomes may use all data.
- Screen dates: `MM-15` for March, May, August, November. Training 2013-03-15 … 2019-11-15 (28 screens). Test 2020-03-15 … 2023-11-15 (16 screens).
- Universe B: TTM-or-FY revenue ≥ $100M, ≥ 5 fiscal years, SIC outside 6000–6799, US exchange only in live runs. No market-value floor.
- Winner (all six, over 12 quarters): revenue CAGR ≥ 0.20; CAGR − peer-group median CAGR ≥ 0.10; revenue up at +4, +8, +12 quarters vs the point 4 quarters before; clean ROIC > 0.09 at ≥ 2 of the +4/+8/+12 points and ROIC(+12) ≥ ROIC(0) − 0.02; gross margin(+12) ≥ gross margin(0) − 0.02 (skipped if missing); (goodwill(+12) − goodwill(0)) / assets(0) < 0.25. No end point = "no outcome" (NaN), never False.
- Signals (exact set): `s01_roic_chg`, `s02_incr_roic`, `s03_gm_chg`, `s04_gm_accel`, `s05_om_chg`, `s08_rev_excess`, `s09_rev_accel`, `s10_peer_rank_chg`, `s11_fcf_margin_chg`, `s14_roic_rank`. Each ranked 0–100 within the v1.x industry peer group.
- Keep rule: signal's top 10% winner rate > universe winner rate in ≥ 5 of 7 training years, in the expected direction (s14: whichever direction wins ≥ 5 of 7). Combination = equal-weighted mean of kept ranks. Pass = test-period top-10% winner rate ≥ 2.0 × test-period base rate.
- The test period is evaluated exactly once, by `mm_discover.py test`, after `train` has written the kept signals. Never edit kept signals after seeing the test.
- Run tests with `.venv/bin/python -m unittest discover tests`.
- Plain-language, English UI text; no programming jargon on the web page.

## Review Focus

1. A company whose fiscal year changes (10-KT, transition period): quarter derivation must skip, not produce a 6- or 9-month "quarter". Test in Task 2.
2. A filer that tags only year-to-date figures in 10-Qs (no 3-month facts): single quarters must come from YTD differences, and Q4 from annual − 9 months. Test in Task 2.
3. Tiny or negative denominators (revenue near 0, negative invested capital): signals must be NaN, not ±inf, so ranks are not poisoned. Test in Task 3.
4. A company acquired in year 2 of the window: label must be NaN (no outcome), not a loser, and must be counted separately. Test in Task 4.
5. 52/53-week fiscal calendars: "same quarter a year earlier" must match within ±20 days, not exact dates. Test in Task 2.

---

### Task 1: Freeze the v1.2 experiment and revert live to v1.1

**Files:**
- Create: `output/data/archive_v1.2/` (copies of `validation.json`, `market.json`), `output/data/ttm_study.json`
- Modify: `settings.yaml` (`methodology_version: "1.1"`, `data.ttm: false`, comment line explaining v1.2 not adopted)
- Delete: `track_record/2026-11-03_v1.2.json`
- Test: `tests/test_moat.py`

**Interfaces:**
- Produces: `output/data/ttm_study.json` with keys `first_test` `{v12_hit, v10_hit}` = 0.361/0.269, `no_overlap` `{v12_hit: 0.348, v12_fa: 0.343, v10_hit: 0.390, v10_fa: 0.278}`, `market_cagr` `{ttm: 0.122, fiscal_years: 0.156, sp500: 0.143}`, `source`, `date` "2026-11-03". Task 8 reads it for the Proof tab.

- [ ] **Step 1:** Copy current `output/data/validation.json` and `market.json` into `output/data/archive_v1.2/`; write `ttm_study.json` with the values above (they are from this session's runs; cite `validation_rows.pkl` and `market.json` as source).
- [ ] **Step 2:** Edit `settings.yaml` as listed; delete the v1.2 freeze file.
- [ ] **Step 3:** Re-run live and derived outputs: `.venv/bin/python src/mm_run.py && .venv/bin/python src/mm_sheet_payload.py && .venv/bin/python src/mm_track.py verify && .venv/bin/python src/mm_track.py page`. Expected: universe ≈ 1,9xx, 25 shortlist, track verify prints OK for 2 files.
- [ ] **Step 4:** Re-run `.venv/bin/python src/mm_validate.py` and `rm data/cache/mm/market_portfolios.pkl; .venv/bin/python src/mm_market.py` (background, ~20 min each) so `validation.json`/`market.json` describe v1.1 again. Expected: shortlist hit ≈ 0.262 (matches the "Fiscal years only" variant of the v1.2 run).
- [ ] **Step 5:** Run all tests. Expected: 24 pass.

### Task 2: Quarterly rows (`mm_quarterly.py`)

**Files:**
- Create: `src/mm_quarterly.py`, `tests/test_compounder.py`

**Interfaces:**
- Consumes: `mm_fundamentals.known_as_of`, `scoring_table(facts, as_of, tax, cash, ttm=True, with_quarters=True)` → `(series, cand)`; `cand` has one row per `(cik, end)` for every 10-K year and 10-Q TTM point with `_derive` columns (`revenue`, `gross_profit`, `clean_oi`, `nopat`, `ic`, `fcf`, `goodwill`, `assets`, `filed`, `accn`, `is_ttm`).
- Produces:
  - `quarter_flows(k: pd.DataFrame) -> pd.DataFrame` — one row per `(cik, end)` fiscal quarter with single-quarter `q_revenue`, `q_gross_profit`, `q_op_income`, `q_one_offs`, `q_clean_oi`; 3-month facts used when tagged, else YTD difference, Q4 = annual − 9-month YTD; a period whose length is not 80–100 days is dropped.
  - `ttm_panel(facts, as_of, tax, cash) -> pd.DataFrame` — `cand` rows filed by `as_of` merged with `quarter_flows`, plus `roic_ttm` = nopat ÷ mean(ic now, ic 4 quarters earlier) where that mean > 0, `gross_margin`, `op_margin` (clean), `fcf_margin`, `asset_turnover`.
  - `lag_q(panel, col, n) -> pd.Series` — value of `col` for the same company at the row whose `end` is within ±20 days of `end − 3n months`; NaN otherwise.

- [ ] **Step 1: Write failing tests** in `tests/test_compounder.py` (import `fact`, `synthetic` from `tests/test_moat.py`):
  - `test_q4_is_annual_minus_9m`: FY2022 revenue 1210, 9M YTD 2022 = 900 → Q4 `q_revenue` == 310.
  - `test_ytd_only_filer`: H1 YTD 580 and Q1 3-month 270, no Q2 3-month fact → Q2 `q_revenue` == 310.
  - `test_transition_period_skipped`: a 10-KT covering 6 months produces no quarter row for that period.
  - `test_lag_matches_53_week_year`: ends 2023-07-01 and 2022-06-25 → `lag_q(..., 4)` finds the 2022 row.
  - `test_point_in_time`: `ttm_panel(..., as_of="2023-07-31")` has no row filed 2023-08-01.
- [ ] **Step 2:** Run `.venv/bin/python -m unittest tests.test_compounder -v`. Expected: FAIL (module not found).
- [ ] **Step 3:** Implement the three functions. Reuse `scoring_table` for TTM; do not duplicate the clean-up logic.
- [ ] **Step 4:** Run tests. Expected: all pass. Then a real-data check: Apple `q_revenue` for the quarter ending 2025-06-28 equals the 3-month figure in its 10-Q (print it with the filing URL; record in the task notes).
- [ ] **Step 5:** Run all tests.

### Task 3: Signals per screen (`mm_signals.py`)

**Files:**
- Create: `src/mm_signals.py`
- Test: `tests/test_compounder.py`

**Interfaces:**
- Consumes: `ttm_panel`, `lag_q` (Task 2); `mm_score.score_as_of(scoring_table(..., ttm=False), companies, as_of, settings, live)` for universe, `industry_group`, gate columns and context `moat_score`; `mm_score.rank_in_groups(values, group, sic)`.
- Produces:
  - `SIGNALS: list[tuple[str, int]]` — the 10 names with expected direction (+1, or 0 for s14 = "decide in training").
  - `signals_at(facts, companies, screen: str, settings: dict, live: bool) -> pd.DataFrame` — one row per universe company: `cik, ticker, name, sic, industry_group, end, filed, accn, moat_score, gate_removed, gate_flags, gate_reasons`, raw signal columns (names above) and rank columns `r_<name>` (0–100 within group, higher raw = higher rank; direction applied later).
- Definitions (latest TTM row per company at the screen):
  - `s01` roic_ttm − lag 4; `s02` (nopat − nopat lag 4) ÷ (ic − ic lag 4) when ic grew ≥ 10%, clipped to [−1, 2]; `s03` q gross margin − same quarter lag 4; `s04` s03 − s03 at lag 2; `s05` q clean op margin − lag 4; `s08` q revenue YoY growth − group median of the same; `s09` q revenue YoY growth − that growth at lag 2; `s10` peer rank (mean group percentile of roic_ttm, gross_margin, op_margin, asset_turnover) now − the same computed on lag-4 values; `s11` fcf_margin − lag 4; `s14` group percentile of roic_ttm.

- [ ] **Step 1: Write failing tests:**
  - `test_signal_definitions`: a synthetic two-company panel with known values gives `s03` == 0.05 and `s09` == 0.10 for company 1.
  - `test_bad_denominators_are_nan`: revenue 0 or negative invested capital → the affected signals are NaN, and `np.isinf(df[[...]]).any().any()` is False.
  - `test_universe_matches_v11`: the set of `cik` in `signals_at(..., "2016-05-15", live=False)` equals the `in_universe` set of `score_as_of` at the same date (real data; skip if `facts.pkl` missing).
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement `SIGNALS` and `signals_at`. Replace ±inf with NaN before ranking.
- [ ] **Step 4:** Run. Expected: pass. Print coverage (share non-NaN per signal) at 2016-05-15 and 2026-08-15 into the task notes.
- [ ] **Step 5:** Run all tests.

### Task 4: Winner label (`mm_outcomes.py`)

**Files:**
- Create: `src/mm_outcomes.py`
- Test: `tests/test_compounder.py`

**Interfaces:**
- Consumes: `ttm_panel(facts, None, ...)` (all data), `lag_q`.
- Produces: `label(panel_all: pd.DataFrame, rows: pd.DataFrame) -> pd.DataFrame` — for each `(cik, end)` in `rows` (the screen's latest TTM point per company, with `industry_group`), columns `c1_cagr … c6_organic` (bool or NaN), `cagr3`, `winner` (True/False/NaN). Peer median CAGR = median `cagr3` of `rows` in the same `industry_group`.

- [ ] **Step 1: Write failing tests**, one per condition on a synthetic company that passes all six, then breaks exactly one:
  - `test_all_six_pass` → `winner` True.
  - `test_cagr_19pct_fails` (c1), `test_peer_excess_9pt_fails` (c2), `test_one_down_year_fails` (c3), `test_roic_one_of_three_fails` (c4), `test_gm_drop_3pt_fails` (c5), `test_goodwill_30pct_fails` (c6) → `winner` False.
  - `test_gross_margin_missing_skips_c5` → `winner` True.
  - `test_acquired_is_nan`: no row at +12 quarters → `winner` NaN.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement `label`.
- [ ] **Step 4:** Run. Expected: pass. Real-data check: base rate across all 44 screens printed (expect roughly 1%; the spec's annual check gave 1.1%).
- [ ] **Step 5:** Run all tests.

### Task 5: Discovery run (`mm_discover.py`) — training, then the single test

**Files:**
- Create: `src/mm_discover.py`
- Modify: `settings.yaml` (new block `compounder: {train: [2013, 2019], test: [2020, 2023], screen_days: ["03-15","05-15","08-15","11-15"], top_share: 0.10, keep_years: 5, pass_multiple: 2.0, shortlist_size: 25}`)
- Test: `tests/test_compounder.py`

**Interfaces:**
- Consumes: `signals_at`, `label`, `SIGNALS`.
- Produces:
  - `screens(settings, period: str) -> list[str]` (`"train"` | `"test"` | `"all"`).
  - `build_rows(settings, period) -> pd.DataFrame` cached to `data/cache/mm/discovery_rows_<period>.pkl` (signals + labels + `screen`, `year`).
  - `keep_rule(rows: pd.DataFrame, settings) -> dict` → `{"kept": {name: direction}, "by_year": {name: {year: {"top_rate", "base_rate", "n_top", "winners_top"}}}}`.
  - `combine(rows: pd.DataFrame, kept: dict) -> pd.Series` (Compounder Signal 0–100: mean of `r_<name>` or `100 − r_<name>` for direction −1; NaN if fewer than half the kept signals are present).
  - CLI: `python src/mm_discover.py train` writes `output/data/discovery.json` (`train` section, `kept`, timestamp, settings fingerprint). `python src/mm_discover.py test` refuses to run if `discovery.json` already has a `test` section; otherwise adds `test`: pooled and per-year top-10% rate, base rate, multiple, `passed` bool, every test-period top-10% pick with outcome.

- [ ] **Step 1: Write failing tests:**
  - `test_keep_rule_years`: synthetic rows where signal A beats base in 5/7 years, B in 4/7 → kept == {A: +1}.
  - `test_keep_rule_direction`: a +1 signal whose bottom decile wins is not kept; s14 kept with direction −1 when its bottom decile wins 5/7.
  - `test_combine_flips_negative`: ranks 80 (dir +1) and 30 (dir −1) → 75.
  - `test_test_runs_once`: second `test` call raises `SystemExit`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement. Long loop prints one line per screen.
- [ ] **Step 4:** Run tests. Then `.venv/bin/python src/mm_discover.py train` (background). Expected: `discovery.json` with 10 signals × 7 years and a `kept` list.
- [ ] **Step 5: STOP — show Jitti the training table and kept signals (approval ★).** Only after Jitti says go: `.venv/bin/python src/mm_discover.py test`. Record pass/fail verbatim.

### Task 6: Price test for the Compounder shortlist

**Files:**
- Modify: `src/mm_market.py` (new function and a `compounder` section in `market.json`)

**Interfaces:**
- Consumes: `data/cache/mm/discovery_rows_{train,test}.pkl`, `combine`, `kept`, `prices()`, `sec_status()`, `stats()`.
- Produces: `compounder_portfolio(rows, kept, settings) -> pd.DataFrame` (screen, cik, ticker of the top 25 after `gate_removed` is excluded); `market.json["compounder"]` with neutral / survivors / worst CAGR, vol, max drawdown, by-year returns for (a) test screens 2020-03-15 → hold to 2024-02, (b) all screens 2013-03-15 → 2026-10, each vs `^SP500TR`, `QUAL`, equal-weight universe and the v1.1 shortlist. Each holding is held from the month-end after the screen to the month-end after the next screen.

- [ ] **Step 1:** Implement, reusing the neutral/worst/survivor logic in `main()` by extracting it into `run_paths(members_by_period, rets, status, spx) -> dict` (one refactor, used by both old and new sections).
- [ ] **Step 2:** Run `.venv/bin/python src/mm_market.py`. Expected: old sections unchanged to 3 decimals vs Task 1 output; new `compounder` section present.
- [ ] **Step 3:** Run all tests.

### Task 7: Live run v2.0

**Files:**
- Modify: `src/mm_run.py`, `settings.yaml` (`methodology_version: "2.0"`), `src/mm_track.py` (record `compounder_signal`, `period`, `filing_used` per name)

**Interfaces:**
- Consumes: `signals_at(..., live=True)`, `combine`, `discovery.json["kept"]`.
- Produces: in `site_data.js` per company: `cs` (Compounder Signal), `cs_rank`, `sig` (array of `r_<name>` in `meta.sig_cols` order), `period`, `ttm`; `meta.kept` (names + directions), `meta.sig_cols`; shortlist = top 25 by `cs` among `~gate_removed`. `moat_score` and themes stay as context. `deep_data.js` keeps the series, `periods` and `q` (12-quarter) blocks.

- [ ] **Step 1:** Implement; screen date = run date (`--as-of`, default today).
- [ ] **Step 2:** Run `mm_run.py`, `mm_sheet_payload.py`, `mm_track.py freeze`, `verify`, `page`. Expected: 25 names, freeze file `<as_of>_v2.0.json`, all fingerprints OK.
- [ ] **Step 3:** Run all tests.

### Task 8: Web page, Sheet and Proof

**Files:**
- Modify: `output/moat_momentum.html`, `src/mm_proof.py`, `src/mm_sheet_payload.py`

**Interfaces:**
- Consumes: `site_data.js` fields from Task 7, `discovery.json`, `market.json["compounder"]`, `ttm_study.json`.
- Produces: JS `computeCS(s)` mirroring `combine` (mean of kept ranks, flip for −1, ≥ half present, toggles from `s.signals_on`); Screener sorted by `cs`; Deep-Dive "Compounder Signal" card with each signal's rank and plain-English label; Scenarios toggles per kept signal; Proof sections in order: v2.0 test result (pass/fail first), training table, price test, v1.x results, v1.2 TTM experiment; Methodology v2.0 text and change-log row; Sheet tab `compounder` (rank, ticker, name, cs, each signal rank, period, filing).

- [ ] **Step 1:** Implement page and generators.
- [ ] **Step 2:** Parity check in the browser pane (server `moat-site`): `computeCS(DEFAULT)` vs `c.cs` max abs diff < 0.01 and identical shortlist; no console errors on any tab; phone width 375 px has no horizontal scroll.
- [ ] **Step 3:** Regenerate `proof.html`, `proof_data.js`, Sheet CSVs; run all tests.

### Task 9: Records and documents

**Files:**
- Modify: `README.md`, `output/README.md`, `spec.md` (status table), `help.md` (only if Jitti asks), pitch Google Docs/Slides (after Jitti reviews results)

- [ ] **Step 1:** Update READMEs and `spec.md` status with v2.0 results (pass or fail stated in the first line).
- [ ] **Step 2:** Republish the dashboard artifact (same file path as before).
- [ ] **Step 3:** Ask Jitti whether to update the whitepaper, one-pager and deck now; do so only on yes, in the same files (links unchanged).
- [ ] **Step 4:** Tell Jitti the work is ready for `/save` (prompts.md entry, PROJECT_MEMORY lessons — including the TTM look-ahead lesson — commit `รอบ N: ...`, push).
