"""Day 3: Layer 1 quant signals per company, point-in-time (spec.md material question 1).

Signals use the latest quarter whose TTM is visible on `as_of` (Q0), compared with Q-4 and Q-8:
  rev_growth     TTM revenue YoY at Q0
  rev_accel      rev_growth(Q0) − rev_growth(Q-4)             (acceleration, percentage points)
  gm_delta       TTM gross margin Q0 − Q-4                     (pp; gross profit = revenue − cost if not reported)
  om_delta       TTM operating margin Q0 − Q-4                 (pp)
  turnaround     TTM operating income or FCF went from ≤ 0 at Q-4 to > 0 at Q0
  share_growth   diluted weighted shares vs a year earlier, from the same filing (dilution, split-safe)
  rev_vs_peak    TTM revenue vs the highest earlier TTM        (> 0 = new high, < 0 = still recovering)
  max_q_share    largest single quarter as a share of TTM      (lumpy revenue, e.g. milestone payments)
Every value comes from SEC companyfacts; `rev_url` points to the filing behind the latest revenue quarter.
"""
from __future__ import annotations

import pandas as pd

from edgar import load_companyfacts
from quarters import quarterly, ttm

MAX_STALENESS_DAYS = 200  # latest quarter must end within ~2 quarters of as_of


def _ttm_map(cik: str, metric: str, as_of: str) -> tuple[dict[str, float], pd.DataFrame]:
    q = quarterly(cik, metric, as_of)
    t = ttm(q)
    return dict(zip(t["end"], t["ttm"])), q


def _back(ends: list[str], e0: str, n: int) -> str | None:
    i = ends.index(e0)
    return ends[i - n] if i - n >= 0 else None


def _ratio(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den <= 0:
        return None
    return num / den


def company_signals(cik: str, as_of: str) -> dict:
    rev, rev_q = _ttm_map(cik, "revenue", as_of)
    if not rev:
        return {"cik": cik, "status": "no_revenue_ttm"}
    ends = sorted(rev)
    e0 = ends[-1]
    if (pd.Timestamp(as_of) - pd.Timestamp(e0)).days > MAX_STALENESS_DAYS:
        # Later quarters exist but cannot form 4 contiguous quarters (usually a fiscal-year change).
        status = "quarter_gap" if rev_q["end"].max() > e0 else "stale"
        return {"cik": cik, "status": status, "q0_end": e0}
    e4, e8 = _back(ends, e0, 4), _back(ends, e0, 8)
    r0, r4, r8 = rev[e0], rev.get(e4), rev.get(e8)
    if r4 is None or r4 <= 0 or r0 <= 0:
        return {"cik": cik, "status": "no_revenue_history", "q0_end": e0, "rev_ttm": r0}

    g0 = r0 / r4 - 1
    g4 = (r4 / r8 - 1) if r8 and r8 > 0 else None

    gp, _ = _ttm_map(cik, "gross_profit", as_of)
    if e0 not in gp or e4 not in gp:
        cost, _ = _ttm_map(cik, "cost_of_revenue", as_of)
        gp = {e: rev[e] - cost[e] for e in (e0, e4) if e in cost and e in rev}
    oi, _ = _ttm_map(cik, "operating_income", as_of)
    cfo, _ = _ttm_map(cik, "cfo", as_of)
    capex, _ = _ttm_map(cik, "capex", as_of)
    fcf = {e: cfo[e] - capex.get(e, 0.0) for e in (e0, e4) if e in cfo}

    gm0, gm4 = _ratio(gp.get(e0), r0), _ratio(gp.get(e4), r4)
    om0, om4 = _ratio(oi.get(e0), r0), _ratio(oi.get(e4), r4)

    turn_oi = e0 in oi and e4 in oi and oi[e4] <= 0 < oi[e0]
    turn_fcf = e0 in fcf and e4 in fcf and fcf[e4] <= 0 < fcf[e0]

    share_growth = diluted_share_growth(cik, as_of)

    # Rebound vs new growth: is TTM revenue above every earlier TTM (prior peak)?
    prior_ttm = [rev[e] for e in ends[:-1]]
    rev_vs_peak = (r0 / max(prior_ttm) - 1) if prior_ttm and max(prior_ttm) > 0 else None
    # Lumpy revenue (e.g. biotech milestone payments): one quarter carries most of the TTM.
    last4 = rev_q[rev_q["end"] <= e0].tail(4)["val"]
    max_q_share = float(last4.max() / r0) if r0 > 0 and len(last4) == 4 else None

    latest_q = rev_q[rev_q["end"] == e0].iloc[0]
    return {
        "cik": cik, "status": "ok", "q0_end": e0,
        "rev_ttm": r0, "rev_ttm_prior": r4,
        "rev_growth": g0,
        "rev_accel": (g0 - g4) if g4 is not None else None,
        "gm": gm0, "gm_delta": (gm0 - gm4) if gm0 is not None and gm4 is not None else None,
        "om": om0, "om_delta": (om0 - om4) if om0 is not None and om4 is not None else None,
        "oi_ttm": oi.get(e0), "fcf_ttm": fcf.get(e0),
        "turnaround": bool(turn_oi or turn_fcf),
        "turnaround_type": "+".join(t for t, ok in (("op_income", turn_oi), ("fcf", turn_fcf)) if ok),
        "share_growth": share_growth,
        "rev_vs_peak": rev_vs_peak,
        "max_q_share": max_q_share,
        "rev_filed": latest_q["filed"], "rev_url": latest_q["url"],
    }


def diluted_share_growth(cik: str, as_of: str) -> float | None:
    """Diluted weighted shares, latest period vs the same-length period a year earlier, both taken
    from the SAME latest filing. Filings restate comparatives for stock splits, so this is split-safe
    (raw cover-page share counts across filings are not)."""
    cf = load_companyfacts(cik)
    facts = (cf or {}).get("facts", {}).get("us-gaap", {}).get(
        "WeightedAverageNumberOfDilutedSharesOutstanding", {}).get("units", {}).get("shares", [])
    facts = [f for f in facts if f["filed"] <= as_of and f.get("start")]
    if not facts:
        return None
    latest_accn = max(facts, key=lambda f: (f["filed"], f["end"]))["accn"]
    same = [f for f in facts if f["accn"] == latest_accn]
    cur = max(same, key=lambda f: f["end"])
    days = (pd.Timestamp(cur["end"]) - pd.Timestamp(cur["start"])).days
    for f in same:
        gap = (pd.Timestamp(cur["end"]) - pd.Timestamp(f["end"])).days
        f_days = (pd.Timestamp(f["end"]) - pd.Timestamp(f["start"])).days
        if 350 <= gap <= 380 and abs(f_days - days) <= 10 and f["val"] > 0:
            return cur["val"] / f["val"] - 1
    return None
