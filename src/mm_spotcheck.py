"""Moat Momentum · step 4: spot-check cleaned figures against the 10-K documents themselves.

Selection rule (stated before looking at results): the highest-ranked universe company in each of the 10 largest
SIC divisions (first two SIC digits) of the 2026-11-03 run, so 10 different industries are covered.
For each company, its last 3 fiscal years. For each year, every reported input that feeds the clean-up and the
themes is searched, formatted as filings print it (units, thousands or millions, with commas), in the text of the
10-K whose accession number our store records for that value. The clean values (clean OI, NOPAT, ROIC) are then
recomputed by hand from those inputs and compared with the engine.

Run:  .venv/bin/python src/mm_spotcheck.py
Out:  output/data/spotcheck.csv, data/cache/mm/spotcheck_docs/ (filing text cache, git-ignored)
"""
from __future__ import annotations

import gzip
import re
import warnings
from pathlib import Path

import pandas as pd
import yaml

from filing_text import html_to_text
from mm_fundamentals import TAG_PRIORITY, annual_table, known_as_of
from sec_client import SecClient

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache" / "mm"
DOCS = CACHE / "spotcheck_docs"
ITEMS = ["revenue", "cogs", "gross_profit_tag", "op_income", "net_income", "sga_tag", "cfo", "capex", "assets",
         "equity", "goodwill", "interest", "restructuring", "acq_costs", "gains"]
IMPAIR = ["GoodwillImpairmentLoss", "AssetImpairmentCharges", "ImpairmentOfLongLivedAssetsHeldForUse",
          "ImpairmentOfIntangibleAssetsExcludingGoodwill"]


def printed_forms(v: float) -> list[str]:
    a = abs(v)
    # most precise first, so a rounded form is used only when the filing prints no finer one
    forms = [f"{a:,.0f}", f"{a / 1e3:,.0f}", f"{a / 1e6:,.1f}", f"{a / 1e9:,.2f}", f"{a / 1e6:,.0f}", f"{a / 1e9:,.1f}"]
    return [f for f in dict.fromkeys(forms) if f not in ("0", "0.0", "0.00")]


LABELS = {
    "revenue": r"revenue|net sales|sales", "cogs": r"cost of", "gross_profit_tag": r"gross (profit|margin)",
    "op_income": r"operating (income|loss|profit)|income from operations|loss from operations",
    "net_income": r"net (income|loss|earnings)", "sga_tag": r"selling|general and administrative",
    "cfo": r"operating activities", "capex": r"property|plant|equipment|capital expenditure",
    "assets": r"total assets", "equity": r"(stockholders|shareholders)['’]? equity|total equity",
    "goodwill": r"goodwill", "interest": r"interest", "restructuring": r"restructuring",
    "acq_costs": r"acquisition|transaction", "gains": r"gain|loss|disposal|sale",
}


def find(text: str, v: float, label: str | None = None) -> tuple[str | None, bool]:
    """(printed form found, True if a matching line label sits within 400 characters before it)."""
    first = None
    for p in printed_forms(v):
        for m in re.finditer(rf"(?<![\d,.]){re.escape(p)}(?![\d,]|\.\d)", text):
            first = first or p
            if label and re.search(label, text[max(0, m.start() - 400):m.start()], re.I):
                return p, True
    return first, False


def primary_doc(sec: SecClient, cik: int, accn: str) -> str | None:
    idx = sec.get_json(f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn.replace('-', '')}/index.json")
    if not idx:
        return None
    htm = [i["name"] for i in idx["directory"]["item"] if i["name"].lower().endswith((".htm", ".html"))
           and "index" not in i["name"].lower() and not re.search(r"ex[-_]?\d|exhibit|R\d+\.htm", i["name"], re.I)]
    if not htm:
        return None
    sizes = {i["name"]: int(i.get("size") or 0) for i in idx["directory"]["item"] if i["name"] in htm}
    return max(htm, key=lambda n: sizes.get(n, 0))  # the 10-K body is the largest non-exhibit document


def doc_text(sec: SecClient, cik: int, accn: str) -> tuple[str, str]:
    DOCS.mkdir(parents=True, exist_ok=True)
    cache = DOCS / f"{accn}.txt.gz"
    if cache.exists():
        with gzip.open(cache, "rt", encoding="utf-8") as f:
            url, text = f.read().split("\n", 1)
        return url, text
    name = primary_doc(sec, cik, accn)
    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn.replace('-', '')}/{name}" if name else ""
    text = html_to_text(sec.session.get(url, timeout=90).text).replace("\xa0", " ") if url else ""
    with gzip.open(cache, "wt", encoding="utf-8") as f:
        f.write(url + "\n" + text)
    return url, text


def pick_companies(run: pd.DataFrame) -> pd.DataFrame:
    u = run[run["in_universe"]].copy()
    u["div"] = u["sic"].astype(int).astype(str).str.zfill(4).str[:2]
    top_div = u["div"].value_counts().head(10).index
    return u[u["div"].isin(top_div)].sort_values("rank").drop_duplicates("div").sort_values("rank")


def main() -> None:
    settings = yaml.safe_load((ROOT / "settings.yaml").read_text())
    tax = settings["data"]["tax_rate"]
    run = pd.read_pickle(CACHE / "run_latest.pkl")
    panel = pd.read_pickle(CACHE / "annual_latest.pkl") if (CACHE / "annual_latest.pkl").exists() else None
    facts = pd.read_pickle(CACHE / "facts.pkl")
    picks = pick_companies(run)
    sec = SecClient()
    rows = []
    for _, c in picks.iterrows():
        cik = int(c["cik"])
        f = known_as_of(facts[facts["cik"] == cik], None)
        f = f[f["form"].isin({"10-K", "10-K/A", "10-KT", "10-KT/A"})]

        d = annual_table(facts[facts["cik"] == cik], None, tax).sort_values("fy").tail(3)
        for _, y in d.iterrows():
            end = y["end"]
            for item in ITEMS + IMPAIR:
                tags = TAG_PRIORITY.get(item, [item])
                cand = f[f["tag"].isin(tags) & (f["end"] == end)]
                if cand.empty:
                    continue
                cand = cand.assign(p=cand["tag"].map({t: i for i, t in enumerate(tags)})).sort_values("p")
                if item not in ("assets", "equity", "goodwill"):
                    cand = cand[cand["kind"] == "A"]
                if cand.empty:
                    continue
                fact = cand.iloc[0]
                url, text = doc_text(sec, cik, fact["accn"])
                lab = LABELS.get(item, r"impairment" if item in IMPAIR else None)
                hit, near = find(text, fact["val"], lab) if text else (None, False)
                rows.append({"ticker": c["ticker"], "name": c["name"], "sic": int(c["sic"]), "sector": c["sic_desc"],
                             "fy": int(y["fy"]), "item": item, "tag": fact["tag"], "value": fact["val"],
                             "found_as": hit or "",
                             "status": ("matched" if len(re.sub(r"\D", "", hit)) >= 4 or near else "weak match (short number)") if hit else ("no document" if not text else
                                                                                 "zero (printed as a dash)" if fact["val"] == 0 else "NOT FOUND"),
                             "accn": fact["accn"], "filing": url})
            # hand recomputation of the clean figures from the inputs above
            parts = {r["item"]: r["value"] for r in rows if r["ticker"] == c["ticker"] and r["fy"] == int(y["fy"])}
            rows.append({"ticker": c["ticker"], "name": c["name"], "sic": int(c["sic"]), "sector": c["sic_desc"],
                         "fy": int(y["fy"]), "item": "check: clean OI = OI + one-offs", "tag": "",
                         "value": y["clean_oi"], "found_as": f"{parts.get('op_income', float('nan')) + y['one_offs']:.0f}",
                         "status": "matched" if abs(parts.get("op_income", 0) + y["one_offs"] - y["clean_oi"]) < 1 else "MISMATCH",
                         "accn": "", "filing": ""})
            rows.append({"ticker": c["ticker"], "name": c["name"], "sic": int(c["sic"]), "sector": c["sic_desc"],
                         "fy": int(y["fy"]), "item": "check: NOPAT = clean OI x (1 - tax)", "tag": "",
                         "value": y["nopat"], "found_as": f"{y['clean_oi'] * (1 - tax):.0f}",
                         "status": "matched" if abs(y["clean_oi"] * (1 - tax) - y["nopat"]) < 1 else "MISMATCH",
                         "accn": "", "filing": ""})
        print(f"  {c['ticker']:6} {c['sic_desc'][:40]:40} done", flush=True)
    df = pd.DataFrame(rows)
    out = ROOT / "output" / "data" / "spotcheck.csv"
    df.to_csv(out, index=False)
    inputs = df[~df["item"].str.startswith("check")]
    print(f"\ninputs matched {int((inputs.status == 'matched').sum())} / {int((inputs.status != 'zero (printed as a dash)').sum())} non-zero; "
          f"arithmetic checks {int((df[df.item.str.startswith('check')].status == 'matched').sum())} / {int(df.item.str.startswith('check').sum())}")
    print(inputs.status.value_counts().to_string())
    print(inputs[~inputs.status.isin(["matched", "zero (printed as a dash)"])][["ticker", "fy", "item", "tag", "value", "status"]].to_string(index=False))


if __name__ == "__main__":
    main()
