"""Moat Momentum v3.0 · the one-time test of R1, R2, R3 (spec docs/specs/2026-11-04-moat-map-v3-design.md §6).

Main (pass/fail): 11 quarterly dates 2021-03-15 … 2023-08-15; winner = moat-compounder label; a rule passes when its whole
list becomes compounders ≥ 2× as often as the rest (pooled) and more often than the rest in each of 2021, 2022, 2023.
Reported, not deciding: top-25 lists; v1.1 and v2.0 on the same dates and measure; 12-month share returns of each top 25
vs the S&P 500 (dates to 2025-08-15, three missing-price cases); share still in the Compounder quadrant 4 quarters later;
results without COVID rebounds. Nothing is re-tuned. Refuses to overwrite an existing result.

Run:  .venv/bin/python src/mm_v3_test.py      → output/data/v3_test.json (rows cached in data/cache/mm/v3_rows.pkl)
      .venv/bin/python src/mm_v3_test.py correct → after the 2026-11-04 review: past market values recomputed with
      Yahoo splits undone (adjusted close × later split ratios); R3 and gap results rerun on the same rows and rules,
      written to a `split_fix` section; the original sections stay as run. R1/R2 do not use prices and are unchanged.
"""
from __future__ import annotations

import hashlib
import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache" / "mm"
OUT = ROOT / "output" / "data" / "v3_test.json"
MAIN_DATES = [f"{y}-{md}" for y in (2021, 2022, 2023) for md in ("03-15", "05-15", "08-15", "11-15")][:11]
PRICE_DATES = [f"{y}-{md}" for y in range(2021, 2026) for md in ("03-15", "05-15", "08-15", "11-15")][:19]
RULES = ["r1", "r2", "r3"]
PASS_MULTIPLE, YEARS = 2.0, (2021, 2022, 2023)


def guard(path: Path = OUT) -> None:
    if path.exists():
        raise SystemExit(f"{path.name} already holds the v3.0 test result; the test is run once (spec §6).")


def _rate(w: pd.Series) -> float:
    return float(w.astype(bool).mean()) if len(w) else float("nan")


def passes(rows: pd.DataFrame, rule_col: str) -> dict:
    r = rows[rows["winner"].notna()]
    inn = r[rule_col].fillna(False).astype(bool)
    lst, rest = _rate(r.loc[inn, "winner"]), _rate(r.loc[~inn, "winner"])
    by_year = {}
    for y in YEARS:
        g = r[r["year"] == y]
        gi = g[rule_col].fillna(False).astype(bool)
        by_year[y] = {"list": _rate(g.loc[gi, "winner"]), "rest": _rate(g.loc[~gi, "winner"]), "n_list": int(gi.sum()),
                      "winners_list": int(g.loc[gi, "winner"].astype(bool).sum())}
    mult = lst / rest if rest else float("nan")
    every = all(np.isfinite(v["list"]) and v["list"] > v["rest"] for v in by_year.values())
    return {"list_rate": lst, "rest_rate": rest, "multiple": mult, "n_list": int(inn.sum()),
            "winners_list": int(r.loc[inn, "winner"].astype(bool).sum()), "by_year": by_year,
            "passed": bool(np.isfinite(mult) and mult >= PASS_MULTIPLE - 1e-12 and every)}


def build_rows(settings: dict, dates: list[str], with_label: bool) -> pd.DataFrame:
    from mm_moatmap import map_at, top25, value_at
    from mm_outcomes import label
    facts, companies = pd.read_pickle(CACHE / "facts.pkl"), pd.read_pickle(CACHE / "companies.pkl")
    px, cover = pd.read_pickle(CACHE / "prices_monthly.pkl"), pd.read_pickle(CACHE / "cover_shares.pkl")
    panel_all = pd.read_pickle(CACHE / "ttm_panel_all.pkl")
    parts = []
    for d in dates:
        m = value_at(map_at(facts, companies, d, settings, live=False), d, px, cover, live=False)
        for rule in RULES:
            m[f"top_{rule}"] = m.index.isin(top25(m, rule).index)
        if with_label:
            lab = label(panel_all, m.dropna(subset=["end"])[["cik", "end", "industry_group"]])
            m = m.merge(lab.drop(columns=["end"]), on="cik", how="left")
        m["year"] = int(d[:4])
        parts.append(m)
        print(f"  {d}: universe {len(m)}, R1 {int(m['r1'].sum())}, R2 {int(m['r2'].sum())}, R3 {int(m['r3'].sum())}", flush=True)
    return pd.concat(parts, ignore_index=True)


def compare_v1_v2(settings: dict) -> dict:
    """v1.1 and v2.0 on the same 11 dates and the same winner label (discovery test rows, labels fixed 2026-11-04)."""
    from mm_discover import combine, rows_path
    r = pd.read_pickle(rows_path(settings, "test"))
    r = r[r["screen"].isin(MAIN_DATES)].copy()
    r["cs"] = combine(r, json.loads((ROOT / "output" / "data" / "discovery.json").read_text())["kept"])
    ok = r["winner"].notna()
    base = _rate(r.loc[ok, "winner"])
    out = {"base_rate": base}
    el = r[~r["gate_removed"].astype(bool)]
    for name, col in (("v11", "moat_score"), ("v20", "cs")):
        t10 = pd.concat([g.dropna(subset=[col]).nlargest(round(0.1 * g[col].notna().sum()), col) for _, g in r.groupby("screen")])
        t25 = el.dropna(subset=[col]).sort_values(col, ascending=False).groupby("screen").head(25)
        for k, t in (("top10", t10), ("top25", t25)):
            t = t[t["winner"].notna()]
            out[f"{name}_{k}"] = {"rate": _rate(t["winner"]), "multiple": _rate(t["winner"]) / base if base else None,
                                  "winners": int(t["winner"].astype(bool).sum()), "n": int(len(t))}
    return out


def price_test(rows: pd.DataFrame) -> dict:
    """12-month equal-weight return of each rule's top 25 from the month-end after each date, vs the S&P 500."""
    from mm_market import BENCH, hold_paths, prices, sec_status, stats  # noqa: F401
    px = pd.read_pickle(CACHE / "prices_monthly.pkl")
    rets = px.pct_change(fill_method=None)
    spx = rets["^SP500TR"]
    status = sec_status(set(rows["cik"]))
    out = {}
    for rule in RULES:
        per = []
        for d, g in rows[rows[f"top_{rule}"]].groupby("date"):
            start = pd.Period(d[:7], "M")
            months = [m for m in pd.period_range(start + 1, start + 12, freq="M") if m in rets.index]
            if len(months) < 12:
                continue
            mem = g.assign(ticker=g["ticker"].map(lambda t: t.replace(".", "-") if isinstance(t, str) else None))
            hp = hold_paths(mem, months, start, f"{int(d[:4]) + 2}{d[4:]}", rets, px, status, spx)
            res = {s: float((1 + hp[s]).prod() - 1) for s in ("survivors", "neutral", "worst") if s in hp}
            res["spx"] = float((1 + spx.reindex(months)).prod() - 1)
            res["date"] = d
            per.append(res)
        df = pd.DataFrame(per)
        out[rule] = {"dates": len(df), "avg_neutral": float(df["neutral"].mean()) if len(df) else None,
                     "avg_worst": float(df["worst"].mean()) if len(df) else None,
                     "avg_survivors": float(df["survivors"].mean()) if "survivors" in df and len(df) else None,
                     "avg_spx": float(df["spx"].mean()) if len(df) else None,
                     "beat_spx_share": float((df["neutral"] > df["spx"]).mean()) if len(df) else None,
                     "per_date": df.round(4).to_dict("records")}
    return out


def still_top_right(rows: pd.DataFrame) -> dict:
    """Share of each rule list in the Compounder quadrant (x ≥ 10%, y ≥ 0) 4 quarters later (all-filings panel)."""
    from mm_moatmap import positions
    p = positions(pd.read_pickle(CACHE / "ttm_panel_all.pkl"))
    later = p[["cik", "end", "x", "y"]].rename(columns={"x": "x_next", "y": "y_next"})
    later["end"] = (later["end"] - pd.DateOffset(years=1)).astype("datetime64[ns]")
    left = rows.dropna(subset=["end"])[["cik", "end"] + RULES].copy()
    left["end"] = pd.to_datetime(left["end"]).astype("datetime64[ns]")
    m = pd.merge_asof(left.sort_values("end"), later.sort_values("end"), on="end", by="cik", direction="nearest",
                      tolerance=pd.Timedelta(days=20))
    ok = m["x_next"].notna() & m["y_next"].notna()
    inq = (m["x_next"] >= 0.10) & (m["y_next"] >= 0)
    return {rule: {"share": float(inq[ok & m[rule].astype(bool)].mean()), "n": int((ok & m[rule].astype(bool)).sum())}
            for rule in RULES} | {"rest": float(inq[ok & ~m[RULES].any(axis=1)].mean())}


def correct(path: Path = OUT) -> dict:
    from mm_market import splits_history
    from mm_moatmap import top25, value_at
    report = json.loads(path.read_text())
    if "split_fix" in report:
        raise SystemExit("split_fix already written")
    rows = pd.read_pickle(CACHE / "v3_rows.pkl")
    px, cover = pd.read_pickle(CACHE / "prices_monthly.pkl"), pd.read_pickle(CACHE / "cover_shares.pkl")
    splits = splits_history(sorted({t.replace(".", "-") for t in rows["ticker"].dropna()}))
    drop = ["cover_shares", "mcap", "ev", "ev_sales", "ev_ebit", "pe", "fcf_yield", "g_implied", "gap", "r3", "top_r3"]
    parts = []
    for d, g in rows.groupby("date", sort=False):
        v = value_at(g.drop(columns=[c for c in drop if c in g]), d, px, cover, live=False, splits=splits)
        v["top_r3"] = v.index.isin(top25(v, "r3").index)
        parts.append(v)
    fixed = pd.concat(parts, ignore_index=True)
    fixed.to_pickle(CACHE / "v3_rows_splitfix.pkl")
    main_rows = fixed[fixed["date"].isin(MAIN_DATES)]
    fix = {"note": "past market values with Yahoo splits undone; R3 and gap recomputed on the same rows and rules",
           "r3": passes(main_rows, "r3"), "top25_r3": passes(main_rows, "top_r3"),
           "no_rebound_r3": passes(main_rows[~main_rows["rebound"].fillna(False).astype(bool)], "r3"),
           "coverage": {"gap": float(main_rows["gap"].notna().mean()),
                        "gap_among_r1_r2": float(main_rows.loc[main_rows["r1"] | main_rows["r2"], "gap"].notna().mean())},
           "price_r3": {k: v for k, v in price_test(fixed)["r3"].items()}}
    report["split_fix"] = fix
    path.write_text(json.dumps(report, indent=1, default=float), encoding="utf-8")
    return fix


def main() -> None:
    guard()
    settings = yaml.safe_load((ROOT / "settings.yaml").read_text())
    cache = CACHE / "v3_rows.pkl"
    if cache.exists():
        rows = pd.read_pickle(cache)
    else:
        main_rows = build_rows(settings, MAIN_DATES, with_label=True)
        extra = build_rows(settings, [d for d in PRICE_DATES if d not in MAIN_DATES], with_label=False)
        rows = pd.concat([main_rows, extra], ignore_index=True)
        rows.to_pickle(cache)
    main_rows = rows[rows["date"].isin(MAIN_DATES)]
    report = {"run": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "settings_sha256": hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest(),
              "dates": MAIN_DATES, "rules": {}, "top25": {}, "no_rebound": {}}
    for rule in RULES:
        report["rules"][rule] = passes(main_rows, rule)
        report["top25"][rule] = passes(main_rows, f"top_{rule}")
        report["no_rebound"][rule] = passes(main_rows[~main_rows["rebound"].fillna(False).astype(bool)], rule)
    report["coverage"] = {"xy": float((main_rows["x"].notna() & main_rows["y"].notna()).mean()),
                          "gap": float(main_rows["gap"].notna().mean()),
                          "gap_among_r1_r2": float(main_rows.loc[main_rows["r1"] | main_rows["r2"], "gap"].notna().mean())}
    report["compare"] = compare_v1_v2(settings)
    report["price"] = price_test(rows)
    report["still_top_right"] = still_top_right(rows)
    OUT.write_text(json.dumps(report, indent=1, default=float), encoding="utf-8")
    for rule in RULES:
        r = report["rules"][rule]
        print(f"{rule}: list {r['list_rate']:.3%} vs rest {r['rest_rate']:.3%} = {r['multiple']:.2f}x · passed {r['passed']}")


if __name__ == "__main__":
    import sys
    correct() if sys.argv[1:] == ["correct"] else main()
