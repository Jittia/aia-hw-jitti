"""Phase 1.5: event study — do change events and radar stages lead to ≥5x more often than the base rate?

For every event onset and every first entry into a stage, with known_date in the study window:
  entry month   = the month the filing became public (month-end price, i.e. after the filing date)
  forward ret   = adjusted close 60 months later / entry month (Yahoo total return)
  base rate     = share of ALL priced companies reaching the target from that same month (cross-section)
  lift          = hit rate of the group / average base rate over the group's entry months
Tuning window: known_date ≤ study.tune_end · holdout: after tune_end up to study.end (2018-01 → 2021-10).

SURVIVORSHIP BIAS: universe = companies listed on 2026-11-02, so rates are optimistic; lifts compare like with like.

Run:  python src/event_study.py      Out: output/event_study_report.md, data/cache/stage_history.pkl
"""
from __future__ import annotations

import copy
import itertools

import numpy as np
import pandas as pd

from events import OUT_EVENTS, OUT_HISTORY
from filing_events import OUT as FILING_EVENTS
from insiders import OUT as INSIDER_EVENTS
from prices import yahoo_ticker
from prices_monthly import OUT as PRICES
from score import load_config
from sec_client import DATA_CACHE, ROOT
from stages import SHARES_HIST, add_recent_events, evaluate, shares_on

REPORT = ROOT / "output" / "event_study_report.md"
STAGE_HISTORY = DATA_CACHE / "stage_history.pkl"
H = 60  # months


def load() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    hist = pd.read_pickle(OUT_HISTORY)
    # All change events: numeric (events.py) + insider cluster buys (insiders.py) + 8-K items (filing_events.py).
    ev = pd.concat([pd.read_pickle(OUT_EVENTS), pd.read_pickle(INSIDER_EVENTS), pd.read_pickle(FILING_EVENTS)],
                   ignore_index=True)
    px = pd.read_pickle(PRICES)
    hist["ytk"] = hist["ticker"].map(yahoo_ticker)
    ev["ytk"] = ev["ticker"].map(yahoo_ticker)
    return hist, ev, px


def add_market_cap(hist: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    sh = pd.read_pickle(SHARES_HIST)
    by = {c: g for c, g in sh.groupby("cik")}
    months = pd.to_datetime(hist["known_date"]).dt.to_period("M")
    caps = []
    for cik, t, d, m in zip(hist["cik"], hist["ytk"], hist["known_date"], months):
        p = raw[t].get(m, np.nan) if t in raw else np.nan
        caps.append(p * shares_on(by.get(cik, pd.DataFrame()), d) if pd.notna(p) else np.nan)
    return hist.assign(mcap_usd=caps, entry_month=months)


def forward(df: pd.DataFrame, adj: pd.DataFrame, month_col: str = "entry_month") -> pd.Series:
    out = []
    for t, m in zip(df["ytk"], df[month_col]):
        if t not in adj:
            out.append(np.nan)
            continue
        s = adj[t]
        a, b = s.get(m, np.nan), s.get(m + H, np.nan)
        out.append(b / a if pd.notna(a) and pd.notna(b) and a > 0 else np.nan)
    return pd.Series(out, index=df.index)


def base_rates(adj: pd.DataFrame, target: float) -> pd.DataFrame:
    fwd = adj.shift(-H) / adj
    return pd.DataFrame({"base_hit": (fwd >= target).sum(axis=1) / fwd.notna().sum(axis=1),
                         "base_5x": (fwd >= 5).sum(axis=1) / fwd.notna().sum(axis=1),
                         "base_n": fwd.notna().sum(axis=1)})


def summarize(g: pd.DataFrame, base: pd.DataFrame) -> dict:
    g = g[g["fwd"].notna()]
    if g.empty:
        return {"n": 0}
    b = base["base_5x"].reindex(g["entry_month"]).mean()
    hit5 = (g["fwd"] >= 5).mean()
    return {"n": len(g), "companies": g["cik"].nunique(), "hit_3x": (g["fwd"] >= 3).mean(), "hit_5x": hit5,
            "hit_10x": (g["fwd"] >= 10).mean(), "median": g["fwd"].median(), "halved": (g["fwd"] < 0.5).mean(),
            "base_5x": b, "lift_5x": hit5 / b if b else np.nan}


def windows(df: pd.DataFrame, cfg: dict) -> dict[str, pd.DataFrame]:
    s = cfg["radar"]["study"]
    k = df["known_date"]
    return {"tune": df[(k >= s["start"]) & (k <= s["tune_end"])], "holdout": df[(k > s["tune_end"]) & (k <= s["end"])]}


def stage_entries(sh: pd.DataFrame, col: str) -> pd.DataFrame:
    prev = sh.groupby("cik")[col].shift(1, fill_value=False)
    return sh[sh[col] & ~prev]


def _fmt(r: pd.Series) -> str:
    if not r.get("n"):
        return "| — | — | — | — | — | — | — | — |"
    # Index by name: r.median would be the pandas Series.median method, not the column.
    return (f"| {int(r['n']):,} | {int(r['companies']):,} | {r['hit_3x']:.1%} | {r['hit_5x']:.1%} | {r['hit_10x']:.1%} | "
            f"{r['median']:.2f}x | {r['halved']:.1%} | **{r['lift_5x']:.2f}x** |")


def write_report(res: pd.DataFrame, grid: pd.DataFrame, cfg: dict) -> None:
    s, st = cfg["radar"]["study"], cfg["radar"]["stages"]
    head = "| Group | Window | Entries | Companies | ≥3x | ≥5x | ≥10x | Median | Halved | Lift (5x) |"
    lines = [
        "---", "title: Event study — catalyst-of-change radar (Phase 1.5)", "type: note", "created: 2026-11-02",
        "updated: 2026-11-02", "tags: [event-study, US, radar]",
        "sources: [SEC EDGAR XBRL companyfacts, SEC submissions index, SEC Insider Transactions Data Sets, Yahoo Finance via yfinance]",
        "status: draft", "---", "",
        "# Event study: do catalyst-of-change signals lead to ≥5x?", "",
        f"Every event onset and every first entry into a stage, dated by its **SEC filing date**, is followed for "
        f"**{H // 12} years** from the month-end after the filing. Tuning window: {s['start']} → {s['tune_end']}; "
        f"**holdout**: after {s['tune_end']} → {s['end']} (not used to choose anything).", "",
        "- **Lift (5x)** = share of entries reaching ≥5x ÷ share of *all* priced companies reaching ≥5x from the same "
        "months. 1.0 = no better than random.",
        "- Prices: Yahoo Finance adjusted close (retrieved 2026-11-02). Fundamentals and events: SEC EDGAR (filing dates).",
        "", "> **Survivorship bias:** only companies listed on 2026-11-02 are included, so all hit rates are optimistic. "
        "Lifts compare groups drawn from the same survivors, so they are the fairer number.",
        "> **Overlap:** a company can enter a stage several times; each entry counts.", ""]
    look = {(r.group, r.window): r for r in res.itertuples()}
    L = lambda g, w: look[(g, w)].lift_5x if (g, w) in look else float("nan")
    H5 = lambda g, w: look[(g, w)].hit_5x if (g, w) in look else float("nan")
    base_h = look[("all company-quarters", "holdout")].base_5x
    lines += [
        "## Findings", "",
        f"1. **Confirmed works out of sample:** holdout lift **{L('stage entry: confirmed', 'holdout'):.2f}x** "
        f"({H5('stage entry: confirmed', 'holdout'):.1%} reached ≥5x vs {base_h:.1%} for all companies); "
        f"Emerging {L('stage entry: emerging', 'holdout'):.2f}x. Spec target was ≥1.5x.",
        f"2. **Radar alone has no out-of-sample edge** (holdout {L('stage entry: radar', 'holdout'):.2f}x). "
        "The edge comes from the Emerging filters: beating the industry median, organic growth, limited dilution and "
        "5x plausibility. Radar is a logbook, not a signal.",
        f"3. **Most robust single events:** gross-margin step-up ({L('event: gm_step', 'tune'):.2f}x tune / "
        f"{L('event: gm_step', 'holdout'):.2f}x holdout) and turning profitable "
        f"({L('event: turn_positive', 'tune'):.2f}x / {L('event: turn_positive', 'holdout'):.2f}x). "
        f"Revenue acceleration and contracted-revenue jumps faded in the holdout.",
        f"4. **8-K officer changes and material agreements carry no signal** "
        f"({L('event: officer_change', 'tune'):.2f}x / {L('event: material_deal', 'tune'):.2f}x tune); insider "
        f"cluster buys were flat in tuning ({L('event: insider_cluster', 'tune'):.2f}x) though "
        f"{L('event: insider_cluster', 'holdout'):.2f}x in the holdout. None of them triggers Radar; they are context.",
        "5. **Tuning to the best in-sample result overfits:** see the grid. Thresholds stay at values set before the study.",
        "",
        "## Results", "", head, "|---|---|---|---|---|---|---|---|---|---|"]
    for r in res.itertuples():
        lines.append(f"| {r.group} | {r.window} " + _fmt(pd.Series(r._asdict())))
    lines += ["", f"Stage thresholds used above (config.yaml): industry excess ≥ {st['industry_excess_pp']:.0%}, "
              f"required revenue CAGR for 5x ≤ {st['max_required_cagr']:.0%}, Confirmed = {st['confirm_quarters']} quarters.", "",
              "## Threshold grid (Emerging / Confirmed entries)", "",
              "Chosen on the tuning window only; holdout shown next to it for honesty.", "",
              "| Industry excess ≥ | Required CAGR ≤ | Stage | Tune n | Tune ≥5x | Tune lift | Holdout n | Holdout ≥5x | Holdout lift |",
              "|---|---|---|---|---|---|---|---|---|"]
    piv = grid.pivot_table(index=["industry_excess_pp", "max_required_cagr", "stage"], columns="window",
                           values=["n", "hit_5x", "lift_5x"]).reset_index()
    for r in piv.itertuples(index=False):
        exc, rq, stage = r[0], r[1], r[2]
        vals = dict(zip([c for c in piv.columns[3:]], r[3:]))
        get = lambda m, w: vals.get((m, w), float("nan"))
        rq_txt = "no limit" if rq > 5 else f"{rq:.0%}"
        lines.append(f"| {exc:.0%} | {rq_txt} | {stage} | {get('n', 'tune'):,.0f} | {get('hit_5x', 'tune'):.1%} | "
                     f"{get('lift_5x', 'tune'):.2f}x | {get('n', 'holdout'):,.0f} | {get('hit_5x', 'holdout'):.1%} | "
                     f"{get('lift_5x', 'holdout'):.2f}x |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    cfg = load_config()
    hist, ev, px = load()
    adj, raw = px["adj"], px["raw"]
    hist = add_market_cap(hist, raw)
    hist["fwd"] = forward(hist, adj)
    hist = add_recent_events(hist, ev, cfg["radar"]["radar_events"])
    ev = ev.assign(entry_month=pd.to_datetime(ev["known_date"]).dt.to_period("M"))
    ev["fwd"] = forward(ev, adj)
    base = base_rates(adj, cfg["radar"]["target_multiple"])

    rows = []
    # 1. every company-quarter (sanity: should be close to the base rate)
    for w, g in windows(hist, cfg).items():
        rows.append({"group": "all company-quarters", "window": w, **summarize(g, base)})
    # 2. each event type (onsets)
    for name, ge in ev.groupby("event"):
        for w, g in windows(ge, cfg).items():
            rows.append({"group": f"event: {name}", "window": w, **summarize(g, base)})
    # 3. stage entries with config thresholds
    sh = evaluate(hist, ev, cfg)
    # Two-key combination: a numeric change and an insider cluster buy, both recent on the same date.
    sh["numeric_plus_insider"] = sh["recent_numeric"] & sh["recent_events"].str.contains("insider_cluster")
    sh["emerging_plus_insider"] = sh["emerging"] & sh["numeric_plus_insider"]
    for col in ("radar", "emerging", "confirmed", "numeric_plus_insider", "emerging_plus_insider"):
        for w, g in windows(stage_entries(sh, col), cfg).items():
            rows.append({"group": f"stage entry: {col}", "window": w, **summarize(g, base)})
    res = pd.DataFrame(rows)

    # 4. threshold grid for Emerging/Confirmed, chosen on tune only
    grid = []
    for exc, rq in itertools.product([0.0, 0.05, 0.10, 0.20, 0.30], [0.40, 0.60, 0.80, 9.0]):
        c = copy.deepcopy(cfg)
        c["radar"]["stages"].update(industry_excess_pp=exc, max_required_cagr=rq)
        s2 = evaluate(hist, ev, c)
        for col in ("emerging", "confirmed"):
            for w, g in windows(stage_entries(s2, col), c).items():
                grid.append({"industry_excess_pp": exc, "max_required_cagr": rq, "stage": col, "window": w, **summarize(g, base)})
    grid = pd.DataFrame(grid)

    sh.to_pickle(STAGE_HISTORY)
    pd.to_pickle({"results": res, "grid": grid, "base": base}, DATA_CACHE / "event_study.pkl")
    write_report(res, grid, cfg)
    print(f"report: {REPORT.relative_to(ROOT)}")
    with pd.option_context("display.width", 250, "display.float_format", "{:.3f}".format):
        print(res.to_string(index=False))
        t = grid[grid["window"] == "tune"].sort_values("lift_5x", ascending=False)
        print("\nGRID (tune, top 12 by 5x lift):")
        print(t.head(12).to_string(index=False))


if __name__ == "__main__":
    main()
