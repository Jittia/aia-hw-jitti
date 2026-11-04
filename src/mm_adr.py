"""ADS (American Depositary Share) ratios from SEC 10-K cover pages.

Yahoo quotes an ADS ticker per ADS, but the SEC cover page counts ordinary shares. When one ADS represents N
ordinary shares, price × cover shares overstates market value N times (BeOne Medicines, ONC: N = 13 gave $524.7B).

ads_ratio(text, ticker)   ordinary shares per ADS, read from the cover line that names `ticker`; None if no such line
adjust_cover(cover, r)    cover-page share counts expressed in ADS (val ÷ ratio), only where the ratio applied then
fetch_ratios(...)         reads the latest 10-K main document of each candidate company from SEC EDGAR (cached)
Run: .venv/bin/python src/mm_adr.py  → data/cache/mm/adr_ratios.json (ratio, filing URL, retrieved date)
"""
from __future__ import annotations

import html
import json
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "cache" / "mm" / "adr_ratios.json"

WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
         "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
         "eighteen": 18, "nineteen": 19, "twenty": 20, "twenty-five": 25, "thirty": 30, "forty": 40, "fifty": 50,
         "one-half": 0.5, "one-third": 1 / 3, "one-quarter": 0.25, "one-fourth": 0.25, "one-fifth": 0.2, "one-tenth": 0.1}
PAT = re.compile(r"american depositary shares?\b.{0,160}?\beach(?:\s+ads)?\s+(?:representing|represents)\s+"
                 r"([0-9][0-9,.]*|[a-z]+(?:-[a-z]+)?)\s+(?:of\s+(?:one|an?)\s+)?(?:class\s+[a-z]\s+)?(?:ordinary|common)\s+shares?",
                 re.I | re.S)


def _clean(text: str) -> str:
    t = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", t.replace("\xa0", " "))


def ads_ratio(text: str, ticker: str) -> float | None:
    t = _clean(text)
    for m in PAT.finditer(t):
        tail = t[m.end():m.end() + 160]
        if not re.search(r"(?<![A-Z0-9])" + re.escape(ticker) + r"(?![A-Z0-9])", tail):
            continue  # this ADS line is for another symbol (or the cover lists the ticker elsewhere)
        w = m.group(1).lower().replace(",", "")
        n = WORDS.get(w)
        if n is None:
            try:
                n = float(w)
            except ValueError:
                continue
        return float(n)
    return None


def adjust_cover(cover: pd.DataFrame, ratios: dict) -> pd.DataFrame:
    """ratios: {cik: {"ratio": N, "filed": date of the 10-K whose cover states N}}. A count filed on or after that 10-K
    is divided by N. An earlier count is divided only if it is within ±40% of the first count filed from that 10-K
    on (no share change in between); otherwise the ratio may not have applied then (Zai Lab: a 2021 count, before its
    2022 share subdivision), so it stays as filed."""
    out = cover.copy()
    for cik, info in ratios.items():
        n, since = float(info["ratio"]), pd.Timestamp(info["filed"])
        rows = out["cik"].astype(int) == int(cik)
        if not rows.any() or n == 1.0:
            continue
        g = out[rows].sort_values("filed")
        after = g[g["filed"] >= since]
        ref = after["val"].iloc[0] if len(after) else None
        ok = (g["filed"] >= since) | (False if ref is None else (g["val"] / ref).between(1 / 1.4, 1.4))
        out.loc[ok[ok].index, "val"] = out.loc[ok[ok].index, "val"] / n
    return out


def load_ratios(path: Path = OUT) -> dict[int, float]:
    if not path.exists():
        return {}
    return {int(k): v for k, v in json.loads(path.read_text())["ratios"].items() if v.get("ratio") not in (None, 1.0)}


def fetch_ratios(companies: pd.DataFrame, ciks: list[int]) -> dict:
    from sec_client import SecClient
    cl = SecClient()
    comp = companies.set_index("cik")
    found, checked = {}, 0
    for cik in ciks:
        row = comp.loc[cik]
        k10 = next((f for f in row["filings"] if f[0] == "10-K"), None)
        if not k10 or not row["tickers"]:
            continue
        _, fdate, accn, doc = k10
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn.replace('-', '')}/{doc}"
        cl._throttle()
        r = cl.session.get(url, timeout=60)
        checked += 1
        if r.status_code != 200:
            print("  HTTP", r.status_code, cik, url)
            continue
        head = r.text[:400_000]  # the cover page is at the top
        for t in row["tickers"]:
            n = ads_ratio(head, t)
            if n is not None:
                found[str(cik)] = {"ticker": t, "ratio": n, "form": "10-K", "filed": fdate, "url": url}
                break
        if "american depositary" in _clean(head[:200_000]).lower() and str(cik) not in found:
            found[str(cik)] = {"ticker": None, "ratio": None, "note": "ADS mentioned, no ratio matched for its tickers", "url": url}
    return {"retrieved": str(date.today()), "checked": checked, "source": "SEC EDGAR 10-K cover page", "ratios": found}


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "src"))
    US = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH "
             "OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY PR".split())
    comp = pd.read_pickle(ROOT / "data" / "cache" / "mm" / "companies.pkl")
    uni = pd.read_pickle(ROOT / "data" / "cache" / "mm" / "run_latest.pkl")
    uni = set(uni.loc[uni["in_universe"], "cik"].astype(int))
    cand = [int(c) for c in comp.loc[comp["cik"].isin(uni) & ~comp["state_inc"].isin(US), "cik"]]
    print("candidates (not incorporated in a US state):", len(cand))
    res = fetch_ratios(comp, cand)
    OUT.write_text(json.dumps(res, indent=1))
    print("checked", res["checked"], "→", {k: (v["ticker"], v["ratio"]) for k, v in res["ratios"].items()})
