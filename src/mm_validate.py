"""Moat Momentum · step 5: fundamental validation 2013–2023 (brief §6A) and robustness (§6C).

For each year Y in settings.validation.years the screen is re-run as of Y-06-30 using ONLY facts filed by then
(point-in-time store). No exchange filter is applied in the past, so companies that later delisted, merged or went
bankrupt are included (less survivorship bias). Outcomes are read 1, 3 and 5 fiscal years later from the latest data.

Outcome measures for a company scored on fiscal year t:
  peer rank   average industry percentile of clean ROIC, gross margin, operating margin, asset turnover (0–100)
  hit         peer rank at t+3 higher than at t ("moat position kept improving")
  false alarm peer rank at t+3 more than 10 points below t ("deteriorated")
  lead time   not in the industry's top 20% on ROIC at t, and in it at least once in t+1..t+3
  also: change in clean ROIC and gross margin, revenue CAGR, each minus the industry median change
Groups compared within the same years and industries: shortlist, all "Moat Strengthening" (not removed), and
everyone else in the universe (base rate). Companies with no later 10-K are counted as "no outcome", not dropped.

Run:  .venv/bin/python src/mm_validate.py
Out:  output/data/validation.json, output/sheet/validation.csv, data/cache/mm/validation_rows.pkl
"""
from __future__ import annotations

import copy
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from mm_fundamentals import annual_table, scoring_table
from mm_score import add_panel_columns, score_as_of

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache" / "mm"


def variants(base: dict) -> dict[str, dict]:
    v = {"Default (locked settings)": copy.deepcopy(base)}
    s = copy.deepcopy(base); s["data"]["ttm"] = False; v["Fiscal years only (v1.1 method)"] = s
    s = copy.deepcopy(base); s["scoring"]["blend"] = {"level": 70, "trend": 20, "consistency": 10}; v["Proven Leaders (70% level)"] = s
    s = copy.deepcopy(base)
    for k in s["risk_gate"]:
        if isinstance(s["risk_gate"][k], dict):
            s["risk_gate"][k]["mode"] = "remove"
    v["Strict Risk (all rules remove)"] = s
    s = copy.deepcopy(base); s["risk_gate"]["altman_z"]["mode"] = "flag"; v["Altman Z'' as flag"] = s
    s = copy.deepcopy(base)
    for k in s["risk_gate"]:
        if isinstance(s["risk_gate"][k], dict):
            s["risk_gate"][k]["mode"] = "off"
    v["No risk gate"] = s
    s = copy.deepcopy(base); s["scoring"]["confirm_themes"] = 4; v["Confirm 4 of 5 themes"] = s
    s = copy.deepcopy(base); s["scoring"]["confirm_themes"] = 2; v["Confirm 2 of 5 themes"] = s
    for t in base["scoring"]["theme_weights"]:
        for delta in (10, -10):
            s = copy.deepcopy(base)
            s["scoring"]["theme_weights"][t] = max(0, s["scoring"]["theme_weights"][t] + delta)
            v[f"Weight {t} {'+' if delta > 0 else '−'}10"] = s
    return v


def outcome_panel(facts: pd.DataFrame, companies: pd.DataFrame, settings: dict) -> pd.DataFrame:
    p = add_panel_columns(annual_table(facts, None, settings["data"]["tax_rate"],
                                       settings["data"]["excess_cash_pct_revenue"]), companies, settings)
    p["roic_top20"] = p.groupby(["pgroup", "fy"])["roic"].rank(pct=True) >= 0.8
    return p.set_index(["cik", "fy"])


def attach_outcomes(res: pd.DataFrame, out: pd.DataFrame) -> pd.DataFrame:
    r = res[["cik", "fy", "pgroup" if "pgroup" in res else "industry_group"]].copy()
    r.columns = ["cik", "fy", "grp"]
    base = out.reindex(pd.MultiIndex.from_arrays([r["cik"], r["fy"]]))
    r["rank0"], r["roic0"], r["gm0"], r["rev0"], r["top0"] = (base["peer_level_rank"].to_numpy(), base["roic"].to_numpy(),
                                                               base["gross_margin"].to_numpy(), base["revenue"].to_numpy(),
                                                               base["roic_top20"].to_numpy())
    for h in (1, 3, 5):
        f = out.reindex(pd.MultiIndex.from_arrays([r["cik"], r["fy"] + h]))
        r[f"rank{h}"], r[f"roic{h}"], r[f"gm{h}"], r[f"rev{h}"] = (f["peer_level_rank"].to_numpy(), f["roic"].to_numpy(),
                                                                    f["gross_margin"].to_numpy(), f["revenue"].to_numpy())
        r[f"top{h}"] = f["roic_top20"].to_numpy()
    r["reached_top"] = (r[["top1", "top2", "top3"]].fillna(False).any(axis=1)
                        if "top2" in r else False)
    f2 = out.reindex(pd.MultiIndex.from_arrays([r["cik"], r["fy"] + 2]))
    r["reached_top"] = pd.concat([r["top1"], pd.Series(f2["roic_top20"].to_numpy(), index=r.index), r["top3"]],
                                 axis=1).fillna(False).astype(bool).any(axis=1)
    for h in (1, 3, 5):
        r[f"d_rank{h}"] = r[f"rank{h}"] - r["rank0"]
        r[f"d_roic{h}"] = r[f"roic{h}"].clip(-1, 1) - r["roic0"].clip(-1, 1)
        r[f"d_gm{h}"] = r[f"gm{h}"].clip(-1, 1) - r["gm0"].clip(-1, 1)
        r[f"g_rev{h}"] = (r[f"rev{h}"] / r["rev0"]) ** (1 / h) - 1
    return r.drop(columns=["cik", "fy", "grp"])


def summarise(rows: pd.DataFrame, flag_col: str) -> dict:
    """Flagged vs the rest, each outcome minus the same-year same-industry median of the whole universe."""
    out = {}
    g = rows.groupby(["year", "industry_group"])
    for m in ["d_rank1", "d_rank3", "d_rank5", "d_roic1", "d_roic3", "d_roic5", "d_gm3", "g_rev3"]:
        rows[f"x_{m}"] = rows[m] - g[m].transform("median")
    for name, sub in (("flagged", rows[rows[flag_col]]), ("rest", rows[~rows[flag_col]])):
        has3 = sub["rank3"].notna() & sub["rank0"].notna()
        s3 = sub[has3]
        not_top = sub[(sub["top0"] == False) & sub["rank1"].notna()]  # noqa: E712
        out[name] = {
            "n": int(len(sub)), "companies": int(sub["cik"].nunique()),
            "no_outcome_3y": round(float(1 - has3.mean()), 3) if len(sub) else None,
            "hit_rate_3y": round(float((s3["d_rank3"] > 0).mean()), 3) if len(s3) else None,
            "false_alarm_3y": round(float((s3["d_rank3"] < -10).mean()), 3) if len(s3) else None,
            "reach_top20_roic_3y": round(float(not_top["reached_top"].mean()), 3) if len(not_top) else None,
            **{f"median_excess_{m}": round(float(sub[f"x_{m}"].median()), 4) if sub[f"x_{m}"].notna().any() else None
               for m in ["d_rank1", "d_rank3", "d_rank5", "d_roic1", "d_roic3", "d_roic5", "d_gm3", "g_rev3"]},
        }
    return out


def main() -> None:
    settings = yaml.safe_load((ROOT / "settings.yaml").read_text())
    facts = pd.read_pickle(CACHE / "facts.pkl")
    companies = pd.read_pickle(CACHE / "companies.pkl")
    out = outcome_panel(facts, companies, settings)
    md = settings["validation"]["as_of_month_day"]
    V = variants(settings)
    rows_by_variant = {k: [] for k in V}
    for y in settings["validation"]["years"]:
        as_of = f"{y}-{md}"
        tables = {t: scoring_table(facts, as_of, settings["data"]["tax_rate"], settings["data"]["excess_cash_pct_revenue"], ttm=t)
                  for t in {bool(s["data"].get("ttm")) for s in V.values()}}
        for name, s in V.items():
            res = score_as_of(tables[bool(s["data"].get("ttm"))], companies, as_of, s, live=False)["results"]
            u = res[res["in_universe"]].copy()
            u["year"] = y
            o = attach_outcomes(u.assign(industry_group=u["industry_group"]), out)
            o.index = u.index
            keep = ["year", "cik", "ticker", "name", "fy", "industry_group", "sic", "revenue", "moat_score", "rank",
                    "shortlist", "moat_strengthening", "gate_removed", "themes_improving"]
            rows_by_variant[name].append(pd.concat([u[keep], o], axis=1))
        print(f"  {y}: universe {len(u)}, shortlist {int(u['shortlist'].sum())}", flush=True)

    report = {"lock": (Path(__file__).parent.parent / "settings.yaml").name, "variants": {}}
    for name, parts in rows_by_variant.items():
        rows = pd.concat(parts, ignore_index=True)
        rows["strong"] = rows["moat_strengthening"] & ~rows["gate_removed"]
        rows["mid"] = rows["revenue"] >= rows.groupby("year")["revenue"].transform("median")
        rep = {"shortlist": summarise(rows.copy(), "shortlist"), "strengthening": summarise(rows.copy(), "strong")}
        if name == "Default (locked settings)":
            rows.to_pickle(CACHE / "validation_rows.pkl")
            rep["by_year"] = {int(y): summarise(g.copy(), "shortlist")["flagged"] for y, g in rows.groupby("year")}
            per = {"2013–2017": rows["year"].between(2013, 2017), "2018–2021": rows["year"].between(2018, 2021),
                   "2022–2023": rows["year"].between(2022, 2023)}
            rep["sub_periods"] = {k: summarise(rows[m].copy(), "shortlist") for k, m in per.items()}
            rep["size"] = {"larger half": summarise(rows[rows["mid"]].copy(), "strong"),
                           "smaller half": summarise(rows[~rows["mid"]].copy(), "strong")}
            div = rows["sic"].astype(int) // 100
            rep["sector_exclusions"] = {
                "excl. energy & mining (SIC 10–14, 29)": summarise(rows[~(div.between(10, 14) | (div == 29))].copy(), "shortlist"),
                "excl. tech (SIC 35–36, 73)": summarise(rows[~div.isin([35, 36, 73])].copy(), "shortlist")}
            sl = rows[rows["shortlist"]].copy()
            sl["outcome"] = np.where(sl["rank3"].isna(), "no outcome", np.where(sl["d_rank3"] > 0, "hit",
                                     np.where(sl["d_rank3"] < -10, "false alarm", "flat")))
            rep["shortlist_names"] = sl[["year", "ticker", "name", "fy", "moat_score", "rank0", "rank3", "d_rank3",
                                         "roic0", "roic3", "outcome"]].round(4).to_dict("records")
        report["variants"][name] = rep
    (ROOT / "output" / "data" / "validation.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    d = report["variants"]["Default (locked settings)"]
    for k in ("shortlist", "strengthening"):
        print(k, json.dumps(d[k], indent=0)[:900])


if __name__ == "__main__":
    main()
