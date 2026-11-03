"""Phase 1.5: "change events" from each company's history, each dated by when it became public.

Numeric events (from data/cache/history.pkl), recorded at the ONSET (first quarter the condition holds after a quarter
where it did not), so a company that keeps growing does not fire every quarter:
  rev_accel      quarterly YoY growth up ≥ rev_accel_pp vs 2 quarters earlier and ≥ rev_accel_min_growth
  gm_step        TTM gross margin ≥ gm_step_pp higher than a year earlier
  turn_positive  TTM operating income or FCF goes from ≤ 0 (a year earlier) to > 0
  contract_jump  contract liabilities or RPO ≥ contracted_jump higher than a year earlier
Industry excess (cycle filter, used by stages): company TTM growth minus the median TTM growth of its industry in the
same calendar quarter.

Run:  python src/events.py      Out: data/cache/events.pkl, data/cache/history_x.pkl (history + industry excess)
"""
from __future__ import annotations

import pandas as pd

from score import load_config
from sec_client import DATA_CACHE

HISTORY = DATA_CACHE / "history.pkl"
OUT_EVENTS = DATA_CACHE / "events.pkl"
OUT_HISTORY = DATA_CACHE / "history_x.pkl"


def add_industry_excess(h: pd.DataFrame) -> pd.DataFrame:
    h = h.copy()
    h["cal_q"] = pd.to_datetime(h["end"]).dt.to_period("Q")
    med = h.groupby(["industry", "cal_q"])["yoy_ttm"].transform("median")
    n = h.groupby(["industry", "cal_q"])["yoy_ttm"].transform("count")
    h["industry_median_yoy"] = med.where(n >= 5)          # fewer than 5 peers = no reliable median
    h["excess_yoy"] = h["yoy_ttm"] - h["industry_median_yoy"]
    return h


def onset(cond: pd.Series) -> pd.Series:
    prev = cond.shift(1, fill_value=False)
    return cond & ~prev


def company_events(g: pd.DataFrame, ev: dict) -> list[dict]:
    g = g.sort_values("end").reset_index(drop=True)
    end = pd.to_datetime(g["end"])
    g2, g4 = g.shift(2), g.shift(4)  # 2 and 4 rows back = half a year / a year in a contiguous history
    # Rows compared must really be that far apart, otherwise a gap in the history would fake a change.
    half_ok = (end - pd.to_datetime(g2["end"])).dt.days.between(170, 200)
    year_ok = (end - pd.to_datetime(g4["end"])).dt.days.between(350, 380)
    conds = {
        "rev_accel": half_ok & (g["yoy_q"] - g2["yoy_q"] >= ev["rev_accel_pp"]) & (g["yoy_q"] >= ev["rev_accel_min_growth"]),
        "gm_step": year_ok & (g["gm_ttm"] - g4["gm_ttm"] >= ev["gm_step_pp"]),
        "turn_positive": year_ok & (((g4["oi_ttm"] <= 0) & (g["oi_ttm"] > 0)) | ((g4["fcf_ttm"] <= 0) & (g["fcf_ttm"] > 0))),
        "contract_jump": (g["contract_yoy"] >= ev["contracted_jump"]) | (g["rpo_yoy"] >= ev["contracted_jump"]),
    }
    out = []
    for name, c in conds.items():
        c = c.fillna(False).astype(bool)
        for i in g.index[onset(c)]:
            r = g.loc[i]
            out.append({"cik": r["cik"], "ticker": r["ticker"], "event": name, "kind": "numeric", "end": r["end"],
                        "known_date": r["known_date"], "url": r["url"], "yoy_q": r["yoy_q"], "yoy_ttm": r["yoy_ttm"]})
    return out


def main() -> None:
    cfg = load_config()["radar"]
    h = pd.read_pickle(HISTORY)
    h = h[h["known_date"] > h["end"]]  # mis-tagged periods (see history.py)
    for col in ("gm_ttm", "oi_ttm", "fcf_ttm", "contract_yoy", "rpo_yoy"):  # absent if no company reports it
        if col not in h:
            h[col] = float("nan")
    h = add_industry_excess(h)
    h.to_pickle(OUT_HISTORY)
    rows = []
    for _, g in h.groupby("cik"):
        rows += company_events(g, cfg["events"])
    ev = pd.DataFrame(rows).sort_values(["known_date", "ticker"])
    ev.to_pickle(OUT_EVENTS)
    print(f"events: {len(ev):,} from {ev['cik'].nunique()} companies")
    print(ev["event"].value_counts().to_string())
    print(f"known_date range: {ev['known_date'].min()} → {ev['known_date'].max()}")


if __name__ == "__main__":
    main()
