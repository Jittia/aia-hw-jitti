"""Moat Momentum · Calculation check: one audit record per Screener company
(spec docs/specs/2026-11-04-calculation-check-design.md §5).

raw_row(k_c, parts_c, end, is_ttm)   the raw tag values the tool used at one period end, rebuilt with the same rules as
                                     annual_table / ttm_rows, and each value's filed parts (fiscal year, year to date,
                                     a year earlier, or the balance sheet), each with its filing
company_record(...)                  the three points (now, 4 and 12 quarters back), every input as components with
                                     `used` flags, the building blocks re-derived by mm_fundamentals._derive, and a
                                     `check` list of any difference from the Screener's panel (empty = reconciles)
panel_and_records(as_of)             every Screener company, for tests and the export
Display only: nothing here changes a calculation.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from mm_fundamentals import ANNUAL_FORMS, POINT_TAGS, REVENUE_TAGS, ST_AFS, ST_HTM, ST_TOTAL, TAG_PRIORITY, _derive

ROOT = Path(__file__).resolve().parent.parent
SHARES = "WeightedAverageNumberOfDilutedSharesOutstanding"
# points at which each input is read by a measure (spec §2): everything now; past points only for growth, invested
# capital (q4, q12), NOPAT 12 quarters back and gross-margin change (q4)
NEED = {"revenue": ("now", "q4", "q12"), "gross_profit": ("now", "q4"), "op_income": ("now", "q4", "q12"),
        "oneoffs": ("now", "q4", "q12"), "equity": ("now", "q4", "q12"), "cash": ("now", "q4", "q12"),
        "st_invest": ("now", "q4", "q12"), "debt": ("now", "q4", "q12")}
SHARDS = 16
BLOCKS = ("revenue", "gross_profit", "op_income", "one_offs", "clean_oi", "nopat", "da", "ebitda", "cfo", "interest",
          "equity", "cash", "excess_cash", "debt", "ic")


def _d(x) -> str | None:
    return None if x is None or pd.isna(x) else str(pd.Timestamp(x).date())


def _f(x) -> float | None:
    return None if x is None or pd.isna(x) else float(x)


def raw_row(k_c: pd.DataFrame, parts_c: pd.DataFrame, end: pd.Timestamp, is_ttm: bool,
            flow_tags: dict | None = None) -> tuple[dict, dict]:
    """(w, parts): w = {tag: value} plus `revenue`, `revenue_tag` as _derive expects; parts = {tag: [part, ...]}.
    A balance-sheet (instant) value never replaces a 12-month value, and is ignored for any tag in `flow_tags`
    (the tags that are flows somewhere in the run): annual_table and ttm_rows join instants with an "_i" suffix
    when a flow column of the same tag exists, so the tool never reads them (e.g. a goodwill impairment tagged as a
    balance in one filing)."""
    end = pd.Timestamp(end)
    w, parts = {}, {}
    if is_ttm:
        pc = parts_c[parts_c["end"] == end].drop_duplicates("tag")  # first per tag, as ttm_rows keeps it
        for r in pc.itertuples():
            t = str(r.tag)
            w[t] = float(r.ttm)
            ytd = {"kind": "YTD", "val": float(r.val), "accn": r.accn, "start": _d(r.start), "end": _d(r.end)}
            parts[t] = [ytd] if t in POINT_TAGS else [
                {"kind": "FY", "val": float(r.a_val), "accn": r.a_accn, "start": _d(r.a_start), "end": _d(r.a_end)},
                ytd, {"kind": "PRIOR", "val": float(r.p_val), "accn": r.p_accn, "start": _d(r.p_start), "end": _d(r.p_end)}]
        rev = [t for t in REVENUE_TAGS if t in w]
        inst = k_c[(k_c["kind"] == "I") & (k_c["end"] == end)]
    else:
        ka = k_c[k_c["form"].isin(ANNUAL_FORMS)]
        fl = ka[(ka["kind"] == "A") & (ka["end"] == end)].assign(dur=lambda x: (x["end"] - x["start"]).dt.days)
        rv = fl[fl["tag"].isin(REVENUE_TAGS)].assign(
            prio=lambda x: x["tag"].map({t: i for i, t in enumerate(REVENUE_TAGS)}), gap=lambda x: (x["dur"] - 364).abs())
        rv = rv.sort_values(["prio", "gap"])
        for r in fl.sort_values("dur").drop_duplicates("tag").itertuples():
            t = str(r.tag)
            w[t] = float(r.val)
            parts[t] = [{"kind": "FY", "val": float(r.val), "accn": r.accn, "start": _d(r.start), "end": _d(r.end)}]
        rev = []
        if len(rv):  # annual revenue is chosen by tag priority, then the duration closest to a year
            r = rv.iloc[0]
            t = str(r["tag"])
            rev = [t]
            w[t] = float(r["val"])
            parts[t] = [{"kind": "FY", "val": float(r["val"]), "accn": r["accn"], "start": _d(r["start"]), "end": _d(r["end"])}]
        inst = ka[(ka["kind"] == "I") & (ka["end"] == end)]
    for r in inst.drop_duplicates("tag", keep="last").itertuples():
        t = str(r.tag)
        if t in w or (flow_tags and t in flow_tags[is_ttm]):
            continue
        w[t] = float(r.val)
        parts[t] = [{"kind": "BAL", "val": float(r.val), "accn": r.accn, "start": None, "end": _d(r.end)}]
    w["revenue_tag"] = rev[0] if rev else None
    w["revenue"] = w[rev[0]] if rev else np.nan
    return w, parts


def _first(w: dict, tags: list[str]) -> str | None:
    return next((t for t in tags if t in w and pd.notna(w[t])), None)


def _sum_any(*vals) -> float | None:
    v = [x for x in vals if x is not None and pd.notna(x)]
    return float(sum(v)) if v else None


def _comp(w, parts, tag, sign=1, used=True, abs_=False) -> dict:
    v = w.get(tag) if tag else None
    return {"tag": tag, "sign": sign, "used": used and tag is not None and v is not None and pd.notna(v),
            "value": None if v is None or pd.isna(v) else (abs(v) if abs_ else float(v)),
            "parts": parts.get(tag, []) if tag else []}


def debt_parts(w: dict, parts: dict) -> list[dict]:
    """Every debt tag present, `used` exactly as mm_fundamentals._derive builds `debt`."""
    g = lambda t: w.get(t) if t in w and pd.notna(w[t]) else None  # noqa: E731
    ltd_cur, debt_cur = g("LongTermDebtCurrent"), g("DebtCurrent")
    use_ltd = g("LongTermDebt") is not None
    split = [t for t in ("LongTermDebtNoncurrent",) if g(t) is not None] + \
            (["LongTermDebtCurrent"] if ltd_cur is not None else (["DebtCurrent"] if debt_cur is not None else []))
    use_split = not use_ltd and bool(split)
    cl = [t for t in ("LongTermDebtAndCapitalLeaseObligations", "LongTermDebtAndCapitalLeaseObligationsCurrent") if g(t) is not None]
    use_cl = not use_ltd and not use_split and bool(cl)  # leases are inside this total
    used_debtcur = ltd_cur is None and debt_cur is not None
    st = [] if used_debtcur else [t for t in ("ShortTermBorrowings", "CommercialPaper") if g(t) is not None]
    fl = []
    if not use_cl:
        if g("FinanceLeaseLiability") is not None:
            fl = ["FinanceLeaseLiability"]
        elif g("FinanceLeaseLiabilityNoncurrent") is not None or g("FinanceLeaseLiabilityCurrent") is not None:
            fl = [t for t in ("FinanceLeaseLiabilityNoncurrent", "FinanceLeaseLiabilityCurrent") if g(t) is not None]
        elif g("CapitalLeaseObligations") is not None:
            fl = ["CapitalLeaseObligations"]
    used = set((["LongTermDebt"] if use_ltd else []) + (split if use_split else []) + (cl if use_cl else []) + st + fl)
    cand = ["LongTermDebt", "LongTermDebtNoncurrent", "LongTermDebtCurrent", "DebtCurrent", "LongTermDebtAndCapitalLeaseObligations",
            "LongTermDebtAndCapitalLeaseObligationsCurrent", "ShortTermBorrowings", "CommercialPaper", "FinanceLeaseLiability",
            "FinanceLeaseLiabilityNoncurrent", "FinanceLeaseLiabilityCurrent", "CapitalLeaseObligations"]
    return [_comp(w, parts, t, 1, t in used) for t in cand if g(t) is not None]


def st_invest_parts(w: dict, parts: dict) -> list[dict]:
    """Every short-term investment tag present, `used` exactly as mm_fundamentals.short_term_investments builds it:
    the first filed total, else the first available-for-sale tag + the first held-to-maturity tag."""
    g = lambda t: w.get(t) if t in w and pd.notna(w[t]) else None  # noqa: E731
    first = lambda tags: next((t for t in tags if g(t) is not None), None)  # noqa: E731
    total = first(ST_TOTAL)
    used = {total} if total else {t for t in (first(ST_AFS), first(ST_HTM)) if t}
    return [_comp(w, parts, t, 1, t in used) for t in ST_TOTAL + ST_AFS + ST_HTM if g(t) is not None]


def oneoff_parts(w: dict, parts: dict) -> list[dict]:
    """Impairment (the largest of three ways it is tagged), restructuring, litigation, deal costs, less asset-sale gains,
    `used` exactly as _derive builds `one_offs`."""
    g = lambda t: w.get(t) if t in w and pd.notna(w[t]) else None  # noqa: E731
    intang = "ImpairmentOfIntangibleAssetsExcludingGoodwill" if g("ImpairmentOfIntangibleAssetsExcludingGoodwill") is not None \
        else ("ImpairmentOfIntangibleAssetsIndefinitelivedExcludingGoodwill"
              if g("ImpairmentOfIntangibleAssetsIndefinitelivedExcludingGoodwill") is not None else None)
    sum_tags = [t for t in ("GoodwillImpairmentLoss", intang, "ImpairmentOfLongLivedAssetsHeldForUse") if t and g(t) is not None]
    alts = [(["AssetImpairmentCharges"], g("AssetImpairmentCharges")),
            (["GoodwillAndIntangibleAssetImpairment"], g("GoodwillAndIntangibleAssetImpairment")),
            (sum_tags, _sum_any(*[g(t) for t in sum_tags]))]
    present = [a for a in alts if a[1] is not None]
    imp_used = set(max(present, key=lambda a: a[1])[0]) if present else set()
    out = [_comp(w, parts, t, 1, t in imp_used) for t in
           ["AssetImpairmentCharges", "GoodwillAndIntangibleAssetImpairment", "GoodwillImpairmentLoss",
            "ImpairmentOfIntangibleAssetsExcludingGoodwill", "ImpairmentOfIntangibleAssetsIndefinitelivedExcludingGoodwill",
            "ImpairmentOfLongLivedAssetsHeldForUse"] if g(t) is not None]
    for metric, sign in (("restructuring", 1), ("litigation", 1), ("acq_costs", 1), ("gains", -1)):
        t = _first(w, TAG_PRIORITY[metric])
        if t:
            out.append(_comp(w, parts, t, sign))
    return out


def _derived(cik: int, end, w: dict, tax: float, cash_pct: float) -> pd.Series:
    row = {k: v for k, v in w.items() if k not in ("revenue_tag",)}
    df = pd.DataFrame([row | {"revenue_tag": w["revenue_tag"], "accn": None, "filed": None, "fy_start": None}],
                      index=pd.MultiIndex.from_tuples([(cik, pd.Timestamp(end))], names=["cik", "end"]))
    return _derive(df, tax, cash_pct).iloc[0]


def items_at(w: dict, parts: dict, d: pd.Series) -> dict:
    """Each input as {"value": the tool's value, "comps": [components with used flags and filed parts]}."""
    v = lambda c: _f(d.get(c))  # noqa: E731
    rev = w.get("revenue_tag")
    cogs = _first(w, TAG_PRIORITY["cogs"])  # without GrossProfit or a cost of revenue the tool has no gross profit
    gp = [_comp(w, parts, "GrossProfit")] if _first(w, ["GrossProfit"]) else \
        [_comp(w, parts, rev), _comp(w, parts, cogs, -1)] if cogs and rev else []
    da_tag = _first(w, TAG_PRIORITY["da_tag"])
    da = [_comp(w, parts, da_tag)] if da_tag else \
        [_comp(w, parts, t) for t in ("Depreciation", "AmortizationOfIntangibleAssets") if _first(w, [t])]
    one = {k: _first(w, TAG_PRIORITY[k]) for k in ("op_income", "cfo", "interest", "equity", "cash_tag")}
    return {
        "revenue": {"value": v("revenue"), "comps": [_comp(w, parts, rev)] if rev else []},
        "gross_profit": {"value": v("gross_profit"), "comps": gp},
        "op_income": {"value": v("op_income"), "comps": [_comp(w, parts, one["op_income"])]},
        "oneoffs": {"value": v("one_offs"), "comps": oneoff_parts(w, parts)},
        "da": {"value": v("da"), "comps": da},
        "cfo": {"value": v("cfo"), "comps": [_comp(w, parts, one["cfo"])]},
        "interest": {"value": v("interest"), "comps": [_comp(w, parts, one["interest"], abs_=True)]},
        "equity": {"value": v("equity"), "comps": [_comp(w, parts, one["equity"])]},
        "cash": {"value": _f(w.get(one["cash_tag"])) if one["cash_tag"] else None, "comps": [_comp(w, parts, one["cash_tag"])]},
        "st_invest": {"value": v("st_invest"), "comps": st_invest_parts(w, parts)},
        "debt": {"value": v("debt"), "comps": debt_parts(w, parts)},
        # diluted average share count: the market-value fallback when no cover-page count is filed
        "shares": {"value": _f(w.get(SHARES)), "comps": [_comp(w, parts, SHARES)] if SHARES in w else []},
    }


def points(panel_c: pd.DataFrame, as_of: str) -> dict:
    """The rows the Screener uses: the latest 12-month row, and the rows 4 and 12 quarters earlier (±20 days)."""
    p = panel_c.sort_values("end")
    p = p[p["end"] >= pd.Timestamp(as_of) - pd.Timedelta(days=548)]
    if not len(p):
        return {}
    now = panel_c.loc[p.index[-1]]
    out = {"now": now}
    for key, n in (("q4", 4), ("q12", 12)):
        gap = (panel_c["end"] - (now["end"] - pd.DateOffset(months=3 * n))).abs()
        out[key] = panel_c.loc[gap.idxmin()] if len(gap) and gap.min() <= pd.Timedelta(days=20) else None
    return out


def company_record(cik: int, k_c: pd.DataFrame, parts_c: pd.DataFrame, panel_c: pd.DataFrame, live: dict | None,
                   as_of: str = "2026-11-03", tax: float = 0.21, cash_pct: float = 0.02,
                   flow_tags: dict | None = None) -> dict:
    pts = points(panel_c, as_of)
    rec = {"cik": int(cik), "ticker": (live or {}).get("ticker"), "pts": {}, "items": {}, "blocks": {}, "check": []}
    used_accn = set()
    for key in ("now", "q4", "q12"):
        r = pts.get(key)
        if r is None:
            continue
        w, parts = raw_row(k_c, parts_c, r["end"], bool(r["is_ttm"]), flow_tags)
        d = _derived(cik, r["end"], w, tax, cash_pct)
        rec["pts"][key] = {"end": _d(r["end"]), "ttm": bool(r["is_ttm"])}
        rec["items"][key] = items_at(w, parts, d)
        rec["blocks"][key] = {b: _f(d.get(b)) for b in BLOCKS}
        for b in BLOCKS:  # the honesty check: re-derived value == the Screener's panel value
            a, e = _f(d.get(b)), _f(r.get(b))
            if (a is None) != (e is None) or (a is not None and abs(a - e) > max(1.0, 1e-9 * abs(e))):
                rec["check"].append([key, b, a, e])
        for it in rec["items"][key].values():
            for c in it["comps"]:
                used_accn.update(p["accn"] for p in c["parts"])
    # items keyed by item first, then point (what the page and the sheet read)
    rec["items"] = {name: {k: rec["items"][k][name] for k in rec["items"]} for name in next(iter(rec["items"].values()), {})}
    f = k_c[k_c["accn"].isin(used_accn)].groupby("accn").agg(form=("form", "first"), filed=("filed", "first"), period=("end", "max"))
    rec["filings"] = {a: {"form": r.form, "filed": _d(r.filed), "period": _d(r.period)} for a, r in f.iterrows()}
    if live:
        cover = live.get("cover_shares")
        cover = cover if cover is not None and pd.notna(cover) and cover > 0 else None
        rec["mkt"] = {"price": _f(live.get("price")), "date": live.get("price_date"),
                      "shares": cover if cover else _f(live.get("shares")), "shares_src": "cover page" if cover else "diluted",
                      "cover_raw": _f(live.get("cover_raw")), "ads_ratio": live.get("ads_ratio"),
                      "mcap": _f(live.get("mcap")), "ev": _f(live.get("ev")),
                      "cover_accn": live.get("cover_accn") if cover else None, "cover_end": live.get("cover_end") if cover else None}
    return rec


def _ok(x) -> bool:
    return x is not None and np.isfinite(x)


def recompute(rec: dict) -> dict:
    """The Screener's measures at the latest point from the record's building blocks (rules of
    mm_screener.group_series / risk_measures and mm_quarterly.ttm_panel). None where the Screener has none."""
    b = rec["blocks"]
    n, q4, q12 = b.get("now", {}), b.get("q4") or {}, b.get("q12") or {}
    div = lambda a, c: a / c if _ok(a) and _ok(c) and c > 0 else None  # noqa: E731
    r = div(n.get("revenue"), q12.get("revenue"))
    growth = r ** (1 / 3) - 1 if r is not None and r > 0 else None
    ics = [v for v in (n.get("ic"), q4.get("ic")) if _ok(v)]
    roic = div(n.get("nopat"), sum(ics) / len(ics)) if ics else None
    nopat = n.get("nopat")
    g2x = (n["ic"] - q4["ic"]) / nopat if _ok(nopat) and nopat > 0 and _ok(n.get("ic")) and _ok(q4.get("ic")) else None
    g2y = None
    if _ok(n.get("ic")) and _ok(q12.get("ic")) and _ok(nopat) and _ok(q12.get("nopat")):
        dic = n["ic"] - q12["ic"]
        if dic > 0 and dic >= 0.10 * abs(q12["ic"]):
            g2y = (nopat - q12["nopat"]) / dic
    gm = lambda p: div(p.get("gross_profit"), p.get("revenue"))  # noqa: E731
    g3y = gm(n) - gm(q4) if gm(n) is not None and gm(q4) is not None else None
    ev = (rec.get("mkt") or {}).get("ev")
    g4y = n.get("clean_oi") / ev if _ok(ev) and ev > 0 and _ok(n.get("clean_oi")) else None
    debt, cash = n.get("debt") or 0.0, n.get("cash") or 0.0
    coi, da, it = n.get("clean_oi"), n.get("da") or 0.0, n.get("interest")
    ebitda = coi + da if _ok(coi) else None
    net = debt - cash
    if ebitda is not None and ebitda <= 0 and net > 0:
        nd = float("inf")
    else:
        nd = net / ebitda if ebitda is not None and ebitda > 0 else None
    return {"g1": [growth, roic], "g2": [g2x, g2y], "g3": [growth, g3y], "g4": [roic, g4y],
            "ic": coi / it if _ok(coi) and _ok(it) and it > 0 else None, "nd": nd,
            "cd": div(n.get("cfo"), debt) if debt > 0 else None}


def reconcile(rec: dict, scr_co: dict, tol: float = 1e-4, ev_tol: float = 1e-4) -> list:
    """Differences between the record's measures and the Screener's stored values (rounded to 4, 2 and 3 places)."""
    m, out = recompute(rec), []
    def cmp(name, a, e, t):
        if a is not None and a == float("inf"):
            a = 999.0
        if (a is None) != (e is None) or (a is not None and abs(a - e) > t):
            out.append([name, a, e])
    for g in ("g1", "g2", "g3", "g4"):
        cmp(g + "x", m[g][0], scr_co[g][0][0], tol)
        e = scr_co[g][0][1]
        cmp(g + "y", m[g][1], e, max(tol, ev_tol * abs(e)) if g == "g4" and e is not None else tol)
    cmp("ic", m["ic"], scr_co["ic"], 0.006)
    cmp("nd", m["nd"], scr_co["nd"], 0.006)
    cmp("cd", m["cd"], scr_co["cd"], 0.0006)
    return out


def live_rows(mmap: pd.DataFrame, daily: pd.Series, ratios: dict, price_date: str, cover_meta: dict | None = None) -> dict:
    """cik → the live market inputs the Screener used: Yahoo close × shares (cover page, ADS-adjusted, else diluted).
    cover_meta: cik → {accn, end, form} of the cover page the count came from."""
    out, cover_meta = {}, cover_meta or {}
    for r in mmap.itertuples():
        t = r.ticker if isinstance(r.ticker, str) else None
        cover = getattr(r, "cover_shares", np.nan)
        ratio = ratios.get(int(r.cik))
        ratio = ratio.get("ratio") if isinstance(ratio, dict) else ratio  # load_ratios(): cik → {ticker, ratio, …}
        # the count exactly as filed; the ratio is shown only when mm_adr.adjust_cover actually divided this count
        raw = _f(cover_meta.get(int(r.cik), {}).get("raw"))
        divided = ratio and raw and _ok(cover) and cover > 0 and abs(raw / cover - ratio) <= 0.01 * ratio
        shown_ratio = ratio if divided else None
        out[int(r.cik)] = {"ticker": t.replace("-", ".") if t else None, "price": _f(daily.get(t)) if t else None,
                           "price_date": price_date, "cover_shares": _f(cover),
                           "cover_raw": raw if raw is not None else _f(cover), "ads_ratio": shown_ratio,
                           "shares": _f(getattr(r, "shares", np.nan)), "mcap": _f(r.mcap), "ev": _f(r.ev),
                           "cover_accn": cover_meta.get(int(r.cik), {}).get("accn"),
                           "cover_end": cover_meta.get(int(r.cik), {}).get("end")}
    return out


def panel_and_records(as_of: str, live: dict | None = None, ciks: set | None = None, facts: pd.DataFrame | None = None,
                      panel: pd.DataFrame | None = None):
    """Yield (cik, record) for every Screener company (CIKs from output/data/site_data.js unless given).
    `facts` and `panel` (ttm_panel at `as_of`) are loaded or computed when not passed in."""
    import yaml
    from mm_fundamentals import known_as_of, ttm_parts
    from mm_quarterly import ttm_panel
    s = yaml.safe_load((ROOT / "settings.yaml").read_text())["data"]
    tax, cash_pct = s["tax_rate"], s["excess_cash_pct_revenue"]
    if ciks is None:
        site = json.loads((ROOT / "output" / "data" / "site_data.js").read_text().split("=", 1)[1].rstrip().rstrip(";"))
        ciks = {int(c) for c in site["scr"]["co"]}
    if facts is None:
        facts = pd.read_pickle(ROOT / "data" / "cache" / "mm" / "facts.pkl")
    # computed over ALL companies, as mm_run does: which tags exist as flows anywhere in the run decides whether a
    # balance-sheet copy of a flow tag is read (see raw_row), so a subset run can differ from the dashboard
    if panel is None:
        panel = ttm_panel(facts, as_of, tax, cash_pct)
    panel = panel[panel["cik"].isin(ciks) & (panel["filed"] <= pd.Timestamp(as_of))]
    k = known_as_of(facts, as_of)
    parts = ttm_parts(k)
    ka = k[k["form"].isin(ANNUAL_FORMS) & (k["kind"] == "A")]
    flow_tags = {True: set(parts["tag"].astype(str)), False: set(ka["tag"].astype(str))}  # {is_ttm: tags that are flows}
    k = k[k["cik"].isin(ciks)]
    parts = parts[parts["cik"].isin(ciks)]
    kg, pg, ng = dict(tuple(k.groupby("cik"))), dict(tuple(parts.groupby("cik"))), dict(tuple(panel.groupby("cik")))
    empty = parts.iloc[:0]
    for cik in sorted(ciks):
        if cik not in ng:
            continue
        yield cik, company_record(cik, kg[cik], pg.get(cik, empty), ng[cik], (live or {}).get(cik), as_of, tax, cash_pct,
                                    flow_tags)


def _n(x):
    """Whole dollars where the value is whole (keeps the file small); None stays None."""
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return None
    return int(x) if float(x).is_integer() else round(float(x), 6)


def compact(rec: dict, pages: dict | None = None) -> dict:
    """The record as the page reads it (window.MM_AUDIT.co[cik]):
    t ticker · pts {now|q4|q12: [end, is 12-month]} · f [[accession, form, period, filed]] ·
    it {item: {point: [value, [[tag, sign, used 0/1, value, [[kind, value, filing index, start, end, page]]]]]}} ·
    b {point: [BLOCKS values]} · m market inputs · ck re-derivation differences (empty = reconciles).
    page: "" = not looked up, None = not located in the filing, else the printed page label."""
    accns = list(rec["filings"])
    fi = {a: i for i, a in enumerate(accns)}
    pages = pages or {}
    def part(p, tag):
        key = f"{tag}|{p['start'] or ''}|{p['end']}"
        pg = pages.get(p["accn"], {}).get(key, "") if p["accn"] in pages else ""
        return [p["kind"], _n(p["val"]), fi.get(p["accn"]), p["start"], p["end"], pg]
    it = {name: {pt: [_n(v["value"]), [[c["tag"], c["sign"], int(c["used"]), _n(c["value"]),
                                         [part(p, c["tag"]) for p in c["parts"]]]
                                        for c in v["comps"] if c["used"]]]
                 for pt, v in by_pt.items() if pt in NEED.get(name, ("now",))} for name, by_pt in rec["items"].items()}
    m = dict(rec["mkt"]) if rec.get("mkt") else None
    if m and m.get("cover_accn"):
        m["cover_page"] = pages.get(m["cover_accn"], {}).get(f"EntityCommonStockSharesOutstanding||{m['cover_end']}", "") \
            if m["cover_accn"] in pages else ""
    return {"t": rec.get("ticker"), "pts": {k: [v["end"], v["ttm"]] for k, v in rec["pts"].items()},
            "f": [[a, rec["filings"][a]["form"], rec["filings"][a]["period"], rec["filings"][a]["filed"]] for a in accns],
            "it": it, "b": {k: [_n(v.get(b)) for b in BLOCKS] for k, v in rec["blocks"].items()},
            "m": m, "ck": rec["check"]}


def shard_of(cik: int) -> int:
    return int(cik) % SHARDS


def export(records, meta: dict, out_dir: Path, pages_dir: Path | None = None, scr_co: dict | None = None) -> dict:
    """Write out_dir/aNN.js (NN = CIK mod 16), each `window.MM_AUDIT = window.MM_AUDIT || {co: {}}; …` adding its
    companies, so the page loads only the part a Deep-Dive needs. Returns the meta with counts. A company whose
    measures differ from the Screener keeps its record with `rc` (the differences) so the page says so."""
    pages = {}
    if pages_dir and pages_dir.exists():
        for f in pages_dir.glob("*.json"):
            try:
                pages[f.stem] = json.loads(f.read_text())
            except ValueError:  # an unreadable cache file: its pages show as not looked up; the page job refetches it
                print(f"  audit: skipped unreadable {f.name}", flush=True)
    parts, n_rec, n = {}, 0, 0
    for cik, rec in records:
        c = compact(rec, pages)
        if scr_co is not None and str(cik) in scr_co:
            d = reconcile(rec, scr_co[str(cik)])
            if d:
                c["rc"] = d
            else:
                n_rec += 1
        parts.setdefault(shard_of(cik), {})[str(cik)] = c
        n += 1
    meta = dict(meta, n=n, reconciled=n_rec, blocks=list(BLOCKS), shards=SHARDS)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("a*.js"):
        old.unlink()
    size = 0
    for k, co in parts.items():
        p = out_dir / f"a{k:02d}.js"
        p.write_text("window.MM_AUDIT = window.MM_AUDIT || {co: {}}; window.MM_AUDIT.meta = "
                     + json.dumps(meta, separators=(",", ":"), default=str) + "; Object.assign(window.MM_AUDIT.co, "
                     + json.dumps(co, separators=(",", ":"), default=str) + ");\n", encoding="utf-8")
        size += p.stat().st_size
    meta["bytes"] = size
    return meta


def load_export(out_dir: Path) -> dict:
    """All parts back as {meta, co} (tests and the page-number job)."""
    data = {"meta": {}, "co": {}}
    for p in sorted(out_dir.glob("a*.js")):
        t = p.read_text()
        data["meta"] = json.loads(t.split("window.MM_AUDIT.meta = ", 1)[1].split("; Object.assign", 1)[0])
        data["co"].update(json.loads(t.split("Object.assign(window.MM_AUDIT.co, ", 1)[1].rsplit(");", 1)[0]))
    return data


def _read_pages(pages_dir: Path) -> dict:
    pages = {}
    for f in pages_dir.glob("*.json"):
        try:
            pages[f.stem] = json.loads(f.read_text())
        except ValueError:
            print(f"  audit: skipped unreadable {f.name}", flush=True)
    return pages


def refresh_pages(out_dir: Path, pages_dir: Path) -> None:
    """Put the latest page-number cache into an existing export (only the page fields change), so a finished
    `src/mm_pages.py` run does not need the whole data pipeline again. Run: python src/mm_audit.py pages"""
    data, pages = load_export(out_dir), _read_pages(pages_dir)
    for c in data["co"].values():
        for by_pt in c["it"].values():
            for _v, comps in by_pt.values():
                for tag, _s, _u, _val, parts in comps:
                    for p in parts:
                        if p[2] is not None and c["f"][p[2]][0] in pages:
                            p[5] = pages[c["f"][p[2]][0]].get(f"{tag}|{p[3] or ''}|{p[4]}", "")
        m = c.get("m") or {}
        if m.get("cover_accn") in pages:
            m["cover_page"] = pages[m["cover_accn"]].get(f"EntityCommonStockSharesOutstanding||{m['cover_end']}", "")
    meta = data["meta"]
    for k in range(meta.get("shards", SHARDS)):
        co = {cik: v for cik, v in data["co"].items() if shard_of(int(cik)) == k}
        if co:
            (out_dir / f"a{k:02d}.js").write_text(
                "window.MM_AUDIT = window.MM_AUDIT || {co: {}}; window.MM_AUDIT.meta = "
                + json.dumps(meta, separators=(",", ":"), default=str) + "; Object.assign(window.MM_AUDIT.co, "
                + json.dumps(co, separators=(",", ":"), default=str) + ");\n", encoding="utf-8")


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["pages"]:
        refresh_pages(ROOT / "output" / "data" / "audit", ROOT / "data" / "cache" / "mm" / "pages")
        print("pages refreshed in output/data/audit")
