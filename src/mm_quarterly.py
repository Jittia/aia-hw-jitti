"""Moat Momentum v2.0 · quarterly rows (spec docs/specs/2026-11-03-compounder-signal-design.md §4).

quarter_flows(k)   single fiscal quarters from point-in-time facts:
                   a 3-month fact when tagged, else year to date − the previous year to date (same fiscal-year start),
                   and Q4 = full year − 9 months. Only periods of 80–100 days count as quarters.
ttm_panel(...)     one row per company and period end (10-K years and 10-Q TTM points, from mm_fundamentals), with the
                   single-quarter figures (q_*) and the 12-month ratios the signals use.
lag_q(panel, col, n)  the value n quarters earlier for the same company (period ends matched within ±20 days).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from mm_fundamentals import ANNUAL_FORMS, POINT_TAGS, _derive, known_as_of, scoring_table

DAY = pd.Timedelta(days=1)


def quarter_flows(k: pd.DataFrame, tax_rate: float = 0.21, excess_cash_pct: float = 0.02) -> pd.DataFrame:
    flows = k[k["kind"].isin(["A", "Q", "YTD"]) & k["start"].notna()].copy()
    flows["tag"] = flows["tag"].astype(str)
    flows = flows[~flows["tag"].isin(POINT_TAGS)]
    flows["nq"] = ((flows["end"] - flows["start"]).dt.days / 91.3).round().astype(int)
    flows = flows[flows["nq"].between(1, 4)]
    flows.loc[(flows["kind"] == "A") & ~flows["form"].isin(ANNUAL_FORMS), "nq"] = 0  # annual values only from 10-K
    # n-quarter span minus the (n−1)-quarter span with the same fiscal-year start = the last quarter
    prev = flows[["cik", "tag", "start", "nq", "end", "val"]].rename(columns={"end": "q_start", "val": "prev"})
    prev["nq"] += 1
    longer = flows[flows["nq"] >= 2].merge(prev, on=["cik", "tag", "start", "nq"])
    longer["qval"] = longer["val"] - longer["prev"]
    longer["q_start"] = longer["q_start"] + DAY
    direct = flows[flows["nq"] == 1].assign(qval=lambda x: x["val"], q_start=lambda x: x["start"])
    q = pd.concat([direct.assign(prio=0), longer.assign(prio=1)], ignore_index=True)
    q = q[(q["end"] - q["q_start"]).dt.days.between(80, 100)]
    q = q.sort_values(["prio", "filed"]).drop_duplicates(["cik", "tag", "end"], keep="first")

    from mm_fundamentals import REVENUE_TAGS
    rev = q[q["tag"].isin(REVENUE_TAGS)].copy()
    rev["rank"] = rev["tag"].map({t: i for i, t in enumerate(REVENUE_TAGS)})
    rev = rev.sort_values(["cik", "end", "rank"]).drop_duplicates(["cik", "end"])
    years = rev[["cik", "end", "qval", "tag", "accn", "filed", "q_start"]].rename(
        columns={"qval": "revenue", "tag": "revenue_tag", "q_start": "fy_start"})
    years = years[years["revenue"].notna()]
    wide = q.merge(years[["cik", "end"]], on=["cik", "end"]).pivot_table(
        index=["cik", "end"], columns="tag", values="qval", aggfunc="first")
    w = years.set_index(["cik", "end"]).join(wide, how="left", rsuffix="_q")
    w.columns = [str(c) for c in w.columns]
    d = _derive(w, tax_rate, excess_cash_pct)
    out = d[["cik", "end", "accn", "filed", "fy_start"]].rename(columns={"fy_start": "q_start"})
    for c in ("revenue", "gross_profit", "op_income", "one_offs", "clean_oi"):
        out[f"q_{c}"] = d[c]
    return out.reset_index(drop=True)


def lag_q(panel: pd.DataFrame, col: str, n: int) -> pd.Series:
    """Value of `col` for the same company at the period ending n quarters earlier (±20 days)."""
    left = pd.DataFrame({"cik": panel["cik"].to_numpy(), "target": (panel["end"] - pd.DateOffset(months=3 * n)).to_numpy(),
                         "pos": np.arange(len(panel))})
    right = pd.DataFrame({"cik": panel["cik"].to_numpy(), "target": panel["end"].to_numpy(), "v": panel[col].to_numpy()})
    m = pd.merge_asof(left.sort_values("target"), right.sort_values("target"), on="target", by="cik",
                      direction="nearest", tolerance=pd.Timedelta(days=20))
    return pd.Series(m.sort_values("pos")["v"].to_numpy(dtype=float), index=panel.index)


def _ratio(a: pd.Series, b: pd.Series) -> pd.Series:
    r = a / b.where(b > 0)
    return r.where(np.isfinite(r))


def ttm_panel(facts: pd.DataFrame, as_of: str | None, tax_rate: float = 0.21,
              excess_cash_pct: float = 0.02) -> pd.DataFrame:
    _, cand = scoring_table(facts, as_of, tax_rate, excess_cash_pct, ttm=False, with_quarters=True)
    cand = cand.sort_values("is_ttm").drop_duplicates(["cik", "end"], keep="first")  # a 10-K year wins over a TTM row
    q = quarter_flows(known_as_of(facts, as_of), tax_rate, excess_cash_pct)
    p = cand.merge(q.drop(columns=["accn", "filed"]), on=["cik", "end"], how="left")
    p = p.sort_values(["cik", "end"]).reset_index(drop=True)
    ic_avg = pd.concat([p["ic"], lag_q(p, "ic", 4)], axis=1).mean(axis=1)
    p["roic_ttm"] = _ratio(p["nopat"], ic_avg)
    p["gross_margin"] = _ratio(p["gross_profit"], p["revenue"])
    p["op_margin"] = _ratio(p["clean_oi"], p["revenue"])
    p["fcf_margin"] = _ratio(p["fcf"], p["revenue"])
    p["asset_turnover"] = _ratio(p["revenue"], p["assets"])
    p["q_gross_margin"] = _ratio(p["q_gross_profit"], p["q_revenue"])
    p["q_op_margin"] = _ratio(p["q_clean_oi"], p["q_revenue"])
    return p
