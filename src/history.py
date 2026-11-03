"""Phase 1.5: each company's full quarterly history, computed once, every row stamped with when it became public.

Why: Phase 1 recomputed everything per as-of date (~4 min each). Here every quarter carries `known_date`
(the SEC filing date of the latest input it needs), so a point-in-time view on any date is just
`known_date <= date`. Values are the FIRST reported ones (earliest filing per period, from `facts_as_of`),
so later restatements never leak backwards.

Columns per quarter end (`end`):
  rev_q, rev_ttm, yoy_q (quarter vs same quarter a year ago), yoy_ttm, gm_ttm, om_ttm, oi_ttm, fcf_ttm,
  contract (contract liabilities / deferred revenue, instant), rpo (instant), dilution (diluted shares YoY,
  split-safe: both numbers from the same filing), acq_ratio, gw_ratio (acquisition flags), shares (latest count),
  known_date, url (filing behind the quarter's revenue)

Run:  python src/history.py      Out: data/cache/history.pkl (all included companies)
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor

import pandas as pd

from edgar import facts_as_of, load_companyfacts
from quarters import _is_quarter_gap, quarterly
from sec_client import DATA_CACHE, DATA_PRIVATE

TODAY = "2026-11-02"
OUT = DATA_CACHE / "history.pkl"


def _q(cik: str, metric: str) -> pd.DataFrame:
    q = quarterly(cik, metric, TODAY)
    return q.set_index("end")[["val", "filed", "url"]] if not q.empty else pd.DataFrame(columns=["val", "filed", "url"])


def _ttm(q: pd.DataFrame) -> pd.DataFrame:
    """Rolling 4 contiguous quarters; known when the last needed quarter was filed."""
    ends = list(q.index)
    rows = {}
    for i in range(3, len(ends)):
        w = ends[i - 3:i + 1]
        if all(_is_quarter_gap(a, b) for a, b in zip(w, w[1:])):
            rows[ends[i]] = {"ttm": float(q.loc[w, "val"].sum()), "filed": max(q.loc[w, "filed"])}
    return pd.DataFrame.from_dict(rows, orient="index")


def _instant(cik: str, metric: str) -> pd.DataFrame:
    f = facts_as_of(cik, metric, TODAY)
    if f.empty:
        return pd.DataFrame(columns=["val", "filed"])
    return f.drop_duplicates("end", keep="first").set_index("end")[["val", "filed"]]


def _dilution(cik: str) -> pd.Series:
    """Per filing: latest-period diluted shares vs the same-length period a year earlier in that filing."""
    cf = load_companyfacts(cik) or {}
    facts = cf.get("facts", {}).get("us-gaap", {}).get(
        "WeightedAverageNumberOfDilutedSharesOutstanding", {}).get("units", {}).get("shares", [])
    out = {}
    by_accn: dict[str, list] = {}
    for f in facts:
        if f.get("start"):
            by_accn.setdefault(f["accn"], []).append(f)
    for same in by_accn.values():
        cur = max(same, key=lambda f: f["end"])
        days = (pd.Timestamp(cur["end"]) - pd.Timestamp(cur["start"])).days
        for f in same:
            gap = (pd.Timestamp(cur["end"]) - pd.Timestamp(f["end"])).days
            f_days = (pd.Timestamp(f["end"]) - pd.Timestamp(f["start"])).days
            if 350 <= gap <= 380 and abs(f_days - days) <= 10 and f["val"] > 0:
                out.setdefault(cur["end"], cur["val"] / f["val"] - 1)   # first filing for that period wins
                break
    return pd.Series(out, dtype=float)


def company_history(cik: str) -> pd.DataFrame:
    try:
        rev = _q(cik, "revenue")
    except FileNotFoundError:
        return pd.DataFrame()
    if len(rev) < 5:
        return pd.DataFrame()
    rev_t = _ttm(rev)
    if rev_t.empty:
        return pd.DataFrame()
    gp_t = _ttm(_q(cik, "gross_profit"))
    if gp_t.empty:
        cost_t = _ttm(_q(cik, "cost_of_revenue"))
        if not cost_t.empty:
            gp_t = cost_t.assign(ttm=rev_t["ttm"].reindex(cost_t.index) - cost_t["ttm"]).dropna()
    oi_t, cfo_t, capex_t = _ttm(_q(cik, "operating_income")), _ttm(_q(cik, "cfo")), _ttm(_q(cik, "capex"))
    acq = _q(cik, "acquisitions")
    contract, rpo, gw = _instant(cik, "contract_liab"), _instant(cik, "rpo"), _instant(cik, "goodwill")
    dil = _dilution(cik)

    h = pd.DataFrame(index=rev_t.index)
    h["rev_q"] = rev["val"].reindex(h.index)
    h["rev_ttm"] = rev_t["ttm"]
    h["known_date"] = rev_t["filed"]
    h["url"] = rev["url"].reindex(h.index)

    def year_ago(s: pd.Series) -> pd.Series:
        """Value at the end date ~1 year earlier (350–380 days), aligned to each row."""
        idx = pd.to_datetime(s.index)
        out = []
        for d in pd.to_datetime(h.index):
            m = s[(d - idx).days.to_series(index=s.index).between(350, 380)]
            out.append(m.iloc[-1] if len(m) else float("nan"))
        return pd.Series(out, index=h.index)

    h["yoy_q"] = h["rev_q"] / year_ago(rev["val"]) - 1
    h["yoy_ttm"] = h["rev_ttm"] / year_ago(rev_t["ttm"]) - 1
    if not gp_t.empty:
        h["gm_ttm"] = gp_t["ttm"].reindex(h.index) / h["rev_ttm"]
    if not oi_t.empty:
        h["oi_ttm"] = oi_t["ttm"].reindex(h.index)
        h["om_ttm"] = h["oi_ttm"] / h["rev_ttm"]
    if not cfo_t.empty:
        capex = capex_t["ttm"].reindex(h.index).fillna(0.0) if not capex_t.empty else 0.0
        h["fcf_ttm"] = cfo_t["ttm"].reindex(h.index) - capex
    for name, s in (("contract", contract), ("rpo", rpo)):
        if not s.empty:
            h[name] = s["val"].reindex(h.index)
            h[f"{name}_yoy"] = h[name] / year_ago(s["val"]) - 1
    h["dilution"] = dil.reindex(h.index)

    # Acquisition flags as in signals.py: cash paid over 8 quarters / goodwill added over ~2 years, vs revenue a year ago.
    rev_ttm_ya = year_ago(rev_t["ttm"])
    if not acq.empty:
        a = acq["val"]
        h["acq_ratio"] = [a[(a.index <= e) & (pd.to_datetime(a.index) > pd.Timestamp(e) - pd.Timedelta(days=730))].sum()
                          for e in h.index] / rev_ttm_ya
    else:
        h["acq_ratio"] = 0.0
    if not gw.empty:
        g = gw["val"]
        gi = pd.to_datetime(g.index)
        added = []
        for e in pd.to_datetime(h.index):
            now, old = g[gi <= e], g[gi <= e - pd.Timedelta(days=700)]
            added.append(max(float(now.iloc[-1]) - (float(old.iloc[-1]) if len(old) else 0.0), 0.0) if len(now) else 0.0)
        h["gw_ratio"] = pd.Series(added, index=h.index) / rev_ttm_ya
    else:
        h["gw_ratio"] = 0.0

    h.insert(0, "cik", cik)
    h.index.name = "end"
    h = h.reset_index()
    # A filing dated before its own period end means a mis-tagged period (7 of ~106k rows); not usable.
    return h[h["known_date"] > h["end"]]


def main() -> None:
    uni = pd.read_csv(DATA_PRIVATE / f"universe_with_cik_{TODAY}.csv", dtype={"cik": str})
    uni = uni[uni["include_flag"] & uni["is_primary_class"]]
    with ProcessPoolExecutor(max_workers=6) as pool:
        parts = list(pool.map(company_history, uni["cik"].tolist(), chunksize=20))
    hist = pd.concat([p for p in parts if not p.empty], ignore_index=True)
    hist = hist.merge(uni[["cik", "ticker", "sector", "industry"]], on="cik", how="left")
    hist.to_pickle(OUT)
    print(f"companies with history: {hist['cik'].nunique()} / {len(uni)} · company-quarters: {len(hist):,} · "
          f"first quarter {hist['end'].min()} · output {OUT}")


if __name__ == "__main__":
    main()
