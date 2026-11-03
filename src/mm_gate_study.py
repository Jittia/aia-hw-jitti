"""Moat Momentum · risk-gate study (2026-11-03): why large, strong companies fail the gate, and what each
alternative rule does to the back-test. Variants were written down before running them; all results are reported.

Run:  .venv/bin/python src/mm_gate_study.py
Out:  output/data/gate_study.json
"""
from __future__ import annotations

import copy
import json
import warnings
from pathlib import Path

from functools import partial

import pandas as pd
import yaml

from mm_fundamentals import scoring_table
from mm_score import score_as_of
from mm_validate import attach_outcomes, outcome_panel, summarise

annual_table = partial(scoring_table, ttm=False)  # the study (v1.1) was run on fiscal years

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache" / "mm"


def variants(base: dict) -> dict[str, dict]:
    v = {"A. Default v1.0": copy.deepcopy(base)}
    s = copy.deepcopy(base); s["risk_gate"]["beneish_m"]["mode"] = "flag"; v["B. Beneish as flag"] = s
    s = copy.deepcopy(base); s["risk_gate"]["beneish_m"]["growth_neutral"] = True; v["C. Beneish ignoring sales growth"] = s
    s = copy.deepcopy(base); s["risk_gate"]["altman_z"]["mode"] = "flag"; v["D. Altman as flag"] = s
    s = copy.deepcopy(base); s["risk_gate"]["altman_z"]["only_if_weak_cover"] = True; v["E. Altman remove only if interest cover < 3"] = s
    s = copy.deepcopy(base); s["risk_gate"]["beneish_m"]["growth_neutral"] = True; s["risk_gate"]["altman_z"]["only_if_weak_cover"] = True
    v["F. C + E (proposal)"] = s
    s = copy.deepcopy(base); s["risk_gate"]["beneish_m"]["mode"] = "off"; s["risk_gate"]["altman_z"]["mode"] = "off"; v["G. Beneish and Altman off"] = s
    s = copy.deepcopy(base); s["risk_gate"]["beneish_m"].update(growth_neutral=True, mode="flag"); s["risk_gate"]["altman_z"]["only_if_weak_cover"] = True
    v["H. Beneish (ignoring growth) as flag + E"] = s
    return v


def main() -> None:
    settings = yaml.safe_load((ROOT / "settings.yaml").read_text())
    facts, companies = pd.read_pickle(CACHE / "facts.pkl"), pd.read_pickle(CACHE / "companies.pkl")
    top = pd.read_pickle(CACHE / "top100.pkl")
    V = variants(settings)
    out = outcome_panel(facts, companies, settings)
    rows = {k: [] for k in V}
    for y in settings["validation"]["years"]:
        as_of = f"{y}-06-30"
        d = annual_table(facts, as_of, settings["data"]["tax_rate"], settings["data"]["excess_cash_pct_revenue"])
        for name, s in V.items():
            res = score_as_of(d, companies, as_of, s, live=False)["results"]
            u = res[res["in_universe"]].copy()
            u["year"] = y
            o = attach_outcomes(u, out)
            o.index = u.index
            rows[name].append(pd.concat([u[["year", "cik", "industry_group", "shortlist", "moat_strengthening", "gate_removed"]], o], axis=1))
        print(f"  {y}", flush=True)
    d_now = annual_table(facts, None, settings["data"]["tax_rate"], settings["data"]["excess_cash_pct_revenue"])
    report = {}
    for name, s in V.items():
        r = pd.concat(rows[name], ignore_index=True)
        r["strong"] = r["moat_strengthening"] & ~r["gate_removed"]
        live = score_as_of(d_now, companies, "2026-11-03", s, live=True)["results"]
        lu = live[live["in_universe"]]
        t = lu[lu["cik"].isin(top["cik"])]
        report[name] = {
            "shortlist": summarise(r.copy(), "shortlist")["flagged"],
            "strengthening": summarise(r.copy(), "strong")["flagged"],
            "removed_share_universe": float(r["gate_removed"].mean()),
            "live_removed_universe": int(lu["gate_removed"].sum()),
            "live_removed_top100": int(t["gate_removed"].sum()),
            "live_removed_top100_names": sorted(t.loc[t["gate_removed"], "ticker"].dropna().tolist()),
            "live_shortlist": sorted(lu.loc[lu["shortlist"], "ticker"].dropna().tolist()),
        }
    report["_base_rate"] = summarise(pd.concat(rows["A. Default v1.0"], ignore_index=True).assign(
        strong=lambda x: x["moat_strengthening"] & ~x["gate_removed"]), "shortlist")["rest"]
    (ROOT / "output" / "data" / "gate_study.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    for k, v in report.items():
        if k.startswith("_"):
            continue
        sl, st = v["shortlist"], v["strengthening"]
        print(f"{k:45} SL hit {sl['hit_rate_3y']:.3f} FA {sl['false_alarm_3y']:.3f} top20 {sl['reach_top20_roic_3y']:.3f} | "
              f"STR n {st['n']} hit {st['hit_rate_3y']:.3f} FA {st['false_alarm_3y']:.3f} | removed {v['removed_share_universe']:.1%} | "
              f"live removed {v['live_removed_universe']} top100 {v['live_removed_top100']}")


if __name__ == "__main__":
    main()
