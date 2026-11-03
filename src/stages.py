"""Phase 1.5: stage machine (Radar → Emerging → Confirmed / Broken), point-in-time per company-quarter.

Each history row (one company, one quarter) is evaluated on its own known_date D, using only what was public on D:
  Radar      ≥1 change event of a `radar_events` type known in (D − recent_days, D]
  Emerging   a recent NUMERIC event, growth beats the industry median by ≥ industry_excess_pp, organic
             (acquisition flags off), dilution ≤ max_dilution, TTM revenue ≥ min_rev, and 5x plausible:
             required revenue CAGR ≤ max_required_cagr at the sector exit P/S (market cap = raw price × SEC shares on D)
  Confirmed  Emerging on this row and the previous row (consecutive quarters)
  Broken     was Emerging/Confirmed on the previous row and is not any more

Run as a library (event_study.py, live run). `python src/stages.py` builds data/cache/shares_hist.pkl.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from edgar import facts_as_of
from sec_client import DATA_CACHE, DATA_PRIVATE

SHARES_HIST = DATA_CACHE / "shares_hist.pkl"
RECENT_DAYS = 200      # an event counts as "recent" for ~2 quarters after it became public
ACQ_LIMIT = 0.10       # same thresholds as config.yaml penalties.acquisitive_*


# ---------- share-count history (for market cap on any past date) ----------
def company_shares(cik: str) -> pd.DataFrame:
    """All share counts with their filing date, best source first: cover page, balance sheet, diluted quarterly average."""
    parts = []
    try:
        for prio, (concept, tax, quarterly_only) in enumerate([
                ("EntityCommonStockSharesOutstanding", "dei", False),
                ("CommonStockSharesOutstanding", "us-gaap", False),
                ("WeightedAverageNumberOfDilutedSharesOutstanding", "us-gaap", True)]):
            f = facts_as_of(cik, concept, "2026-11-02", taxonomy=tax, unit="shares")
            if f.empty:
                continue
            if quarterly_only:
                f = f[f["period_days"].between(80, 100)]
            parts.append(f[["end", "val", "filed"]].assign(prio=prio))
    except FileNotFoundError:
        return pd.DataFrame()
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts).assign(cik=cik)


def shares_on(sh: pd.DataFrame, date: str) -> float:
    """Latest count public on `date`, no older than ~13 months; best source wins among the freshest quarter."""
    if sh.empty:
        return np.nan
    c = sh[(sh["filed"] <= date) & (pd.to_datetime(sh["end"]) >= pd.Timestamp(date) - pd.Timedelta(days=400))]
    if c.empty:
        return np.nan
    latest = c[c["end"] == c["end"].max()]
    return float(latest.sort_values("prio").iloc[0]["val"])


# ---------- stages ----------
def required_cagr(mcap: pd.Series, rev_ttm: pd.Series, sector: pd.Series, plaus: dict, multiple: float,
                  years: int) -> pd.Series:
    exit_ps = sector.map(plaus["exit_ps_by_sector"]).fillna(plaus["exit_ps_default"])
    return (multiple * mcap / exit_ps / rev_ttm) ** (1 / years) - 1


def add_recent_events(hist: pd.DataFrame, events: pd.DataFrame, radar_events: list[str]) -> pd.DataFrame:
    """Which events were public and recent on each row's known_date. Independent of stage thresholds,
    so it is computed once and reused across a threshold grid. Only `radar_events` types trigger Radar;
    all types are listed in recent_events as context."""
    h = hist.sort_values(["cik", "end"]).copy()
    kd = pd.to_datetime(h["known_date"])
    ev = events.assign(kd=pd.to_datetime(events["known_date"]))
    recent_any, recent_num, recent_types = [], [], []
    ev_by = {c: g for c, g in ev.groupby("cik")}
    for cik, d in zip(h["cik"], kd):
        g = ev_by.get(cik)
        if g is None:
            recent_any.append(False); recent_num.append(False); recent_types.append("")
            continue
        m = g[(g["kd"] <= d) & (g["kd"] > d - pd.Timedelta(days=RECENT_DAYS))]
        recent_any.append(bool(m["event"].isin(radar_events).any()))
        recent_num.append(bool((m["kind"] == "numeric").any()))
        recent_types.append("+".join(sorted(set(m["event"]))))
    h["radar"], h["recent_numeric"], h["recent_events"] = recent_any, recent_num, recent_types
    return h


def evaluate(hist: pd.DataFrame, events: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Adds radar / emerging / confirmed / broken / stretch_10x columns (needs mcap_usd)."""
    r, st = cfg["radar"], cfg["radar"]["stages"]
    h = (hist if "recent_numeric" in hist else add_recent_events(hist, events, r["radar_events"])
         ).sort_values(["cik", "end"]).copy()

    h["req_cagr"] = required_cagr(h["mcap_usd"], h["rev_ttm"], h["sector"], cfg["plausibility"],
                                  r["target_multiple"], r["horizon_years"])
    organic = ~((h["acq_ratio"].fillna(0) > ACQ_LIMIT) | (h["gw_ratio"].fillna(0) > ACQ_LIMIT))
    h["emerging"] = (h["recent_numeric"] & (h["excess_yoy"] >= st["industry_excess_pp"]) & organic
                     & ~(h["dilution"] > st["max_dilution"]) & (h["rev_ttm"] >= r["min_rev_ttm_usd"])
                     & (h["req_cagr"] <= st["max_required_cagr"]))
    prev_em = h.groupby("cik")["emerging"].shift(1, fill_value=False)
    h["confirmed"] = h["emerging"] & prev_em
    h["broken"] = prev_em & ~h["emerging"]
    h["stretch_10x"] = h["emerging"] & (required_cagr(h["mcap_usd"], h["rev_ttm"], h["sector"], cfg["plausibility"],
                                                      r["stretch_multiple"], r["horizon_years"]) <= st["max_required_cagr"])
    return h


def main() -> None:
    uni = pd.read_csv(DATA_PRIVATE / "universe_with_cik_2026-11-02.csv", dtype={"cik": str})
    uni = uni[uni["include_flag"] & uni["is_primary_class"]]
    with ProcessPoolExecutor(max_workers=6) as pool:
        parts = list(pool.map(company_shares, uni["cik"].tolist(), chunksize=20))
    sh = pd.concat([p for p in parts if not p.empty], ignore_index=True)
    sh.to_pickle(SHARES_HIST)
    print(f"share history: {sh['cik'].nunique()} companies · {len(sh):,} counts → {SHARES_HIST}")


if __name__ == "__main__":
    main()
