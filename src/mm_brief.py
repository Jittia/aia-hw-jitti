"""Company brief for the Deep-Dive and the pitch deck, from SEC EDGAR only (spec 2026-11-04-dashboard-pivot §5.2).

item1_description(html)        first paragraphs of Item 1 "Business" of a 10-K (skips the table of contents)
founded_phrase(text, year)     founding / incorporation year only when the filing states it, with the phrase
website(text)                  the company's website as stated in the 10-K ("our website address is …")
build(...)                     all universe companies → output/data/brief_data.js (window.MM_BRIEF)
Run: .venv/bin/python src/mm_brief.py   (≈ 1,900 SEC requests at ≤ 10/s; raw text cached in data/cache/mm/briefs/)
"""
from __future__ import annotations

import gzip
import html as htmllib
import json
import re
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache" / "mm" / "briefs"
OUT = ROOT / "output" / "data" / "brief_data.js"

ITEM1 = re.compile(r"item\s*1\s*\.?\s*[-–—:]?\s*business\b", re.I)
ITEM1A = re.compile(r"item\s*1\s*[.(]?\s*a\b\)?", re.I)  # Item 1A, Item 1.A., Item 1(a)
ITEMN = re.compile(r"\bitem\s*\d+\s*[.(]?\s*[a-c]?\)?\s*[.:]", re.I)
HEADS = re.compile(r"^(?:(?:part\s+i\s+)?(?:overview|general|our company|company overview|business overview|introduction|"
                   r"the company|our business|company background|background)[\s:.\-–—]+)+", re.I)
BOILER = re.compile(r"unless the context|references to|the terms [“\"']?we|as used in this|forward-looking|this annual report on form|"
                    r"inherently uncertain|could differ materially|risks and uncertainties|unless otherwise|translated into u\.?s\.? dollars|this report includes|"
                    r"[”\"] means|[”\"] refers? to|trademark|®|™|these factors",
                    re.I)


def clean(text: str) -> str:
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    t = re.sub(r"<ix:header>.*?</ix:header>", " ", t, flags=re.S | re.I)
    t = htmllib.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s+", " ", re.sub(r"[\u200b\u200c\u200d\ufeff]", " ", t.replace("\xa0", " "))).strip()


ABBR = re.compile(r"(?:\b(?:Inc|Corp|Co|Ltd|Plc|plc|LLC|L\.P|N\.V|S\.A|U\.S|No|Nos|St|Mr|Ms|Dr|Jr|vs|approx|e\.g|i\.e)|\bItem\s+\d+[A-Ca-c]?)\.$")


def _sentences(t: str) -> list[str]:
    parts, out = [p.strip() for p in re.split(r"(?<=[.!?])\s+(?=[A-Z“\"(])", t) if p.strip()], []
    for p in parts:
        if out and ABBR.search(out[-1]):  # "Walmart Inc." is not the end of a sentence
            out[-1] += " " + p
        else:
            out.append(p)
    return out


def item1_description(text: str, max_chars: int = 1100) -> str | None:
    t = clean(text)
    for m in ITEM1.finditer(t):
        if re.search(r"(?:[“\"'‘]|\bsee|\bin|\bto)\s*(?:part\s+(?:1|i)\s*[,.:–—-]?\s*)?$", t[max(0, m.start() - 24):m.start()], re.I):
            continue  # a quoted cross-reference ("see “Item 1. Business – …”"), not the heading
        end = ITEM1A.search(t, m.end())
        seg = t[m.end(): end.start() if end else m.end() + 20000].strip()
        if len(seg) < 400 or len(ITEMN.findall(seg[:800])) >= 3:  # a table of contents ("Item 1. Business 4 Item 1A …")
            continue
        seg = re.sub(r"^[.:\-–—\s]+", "", HEADS.sub("", re.sub(r"^\d{1,3}\s+(?=[A-Z][a-z])", "", seg)))
        first = re.search(r"[A-Za-z0-9]", seg[:5])
        if not first or not (first.group(0).isupper() or first.group(0).isdigit()):
            continue  # starts mid-sentence: not the opening of the section
        out = []
        for s in _sentences(seg):
            if len(s) < 25 or BOILER.search(s) or not s.endswith((".", "!", "?")):
                if out:
                    break  # stop at the first heading or boilerplate after prose has started
                continue
            if len(" ".join(out + [s])) > max_chars:
                break
            out.append(s)
        if out:
            return " ".join(out)
    return None


FOUNDED = re.compile(r"[^.]{0,80}\b(?:founded|established|began operations|commenced operations|incorporated|organized)\b"
                     r"[^.]{0,60}?\bin\s+(1[89]\d\d|20\d\d)\b[^.]{0,40}\.?", re.I)


def founded_phrase(text: str, filing_year: int) -> dict | None:
    for m in FOUNDED.finditer(clean(text)):
        y = int(m.group(1))
        if 1800 <= y <= filing_year:
            return {"year": y, "phrase": m.group(0).strip()[:200]}
    return None


SITE = re.compile(r"(?:our|its|the company['’]s)\s+(?:corporate\s+|internet\s+|investor\s+relations\s+)?web\s?site"
                  r"(?:\s+address)?(?:\s+is|\s+at|,)?\s+(?:located\s+at\s+)?(?:https?://)?"
                  r"((?:www\.)?[a-z0-9][a-z0-9\-]*(?:\.[a-z0-9\-]+)+)", re.I)


def website(text: str) -> str | None:
    for m in SITE.finditer(clean(text)):
        host = m.group(1).rstrip(".").lower()
        if "sec.gov" not in host and "." in host:
            return host
    return None


FYE = {"01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "May", "06": "Jun", "07": "Jul", "08": "Aug",
       "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec"}


def _submission(zf: zipfile.ZipFile, cik: int) -> dict:
    try:
        return json.loads(zf.read(f"CIK{cik:010d}.json"))
    except KeyError:
        return {}


def build(companies, ciks: list[int]) -> dict:
    from sec_client import SecClient
    cl, comp = SecClient(), companies.set_index("cik")
    CACHE.mkdir(parents=True, exist_ok=True)
    zf = zipfile.ZipFile(ROOT / "data" / "cache" / "bulk" / "submissions.zip")
    out = {}
    for i, cik in enumerate(ciks):
        row = comp.loc[cik]
        k10 = next((f for f in row["filings"] if f[0] == "10-K"), None)
        sub = _submission(zf, cik)
        addr = (sub.get("addresses") or {}).get("business") or {}
        fye = sub.get("fiscalYearEnd") or ""
        rec = {"hq": ", ".join(x for x in (addr.get("city"), addr.get("stateOrCountryDescription") or addr.get("stateOrCountry") or addr.get("country")) if x),
               "inc": sub.get("stateOfIncorporationDescription") or sub.get("stateOfIncorporation") or "",
               "fye": f"{FYE.get(fye[:2], '')} {int(fye[2:])}" if len(fye) == 4 and fye.isdigit() else "",
               "desc": None, "founded": None, "website": None}
        if k10:
            _, fdate, accn, doc = k10
            url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn.replace('-', '')}/{doc}"
            rec.update({"url": url, "filed": fdate})
            f = CACHE / f"{cik}_{accn}.txt.gz"
            if f.exists():
                text = gzip.decompress(f.read_bytes()).decode()
            else:
                cl._throttle()
                r = cl.session.get(url, timeout=90)
                text = clean(r.text)[:400_000] if r.status_code == 200 else ""
                if text:
                    f.write_bytes(gzip.compress(text.encode()))
            if text:
                rec["desc"] = item1_description(text)
                rec["founded"] = founded_phrase(text[:200_000], int(fdate[:4]))
                rec["website"] = website(text)
        out[str(cik)] = rec
        if (i + 1) % 200 == 0:
            print(f"  {i + 1}/{len(ciks)}", flush=True)
    return {"meta": {"retrieved": str(date.today()), "source": "SEC EDGAR: latest 10-K (Item 1 Business) and submissions"}, "co": out}


if __name__ == "__main__":
    import pandas as pd
    sys.path.insert(0, str(ROOT / "src"))
    comp = pd.read_pickle(ROOT / "data" / "cache" / "mm" / "companies.pkl")
    run = pd.read_pickle(ROOT / "data" / "cache" / "mm" / "run_latest.pkl")
    ciks = sorted(int(c) for c in run.loc[run["in_universe"], "cik"])
    res = build(comp, ciks)
    OUT.write_text("window.MM_BRIEF = " + json.dumps(res, separators=(",", ":")) + ";\n", encoding="utf-8")
    co = res["co"].values()
    n = len(res["co"])
    print(f"companies {n}: description {sum(bool(c['desc']) for c in co)}, founded {sum(bool(c['founded']) for c in co)}, "
          f"website {sum(bool(c['website']) for c in co)}; {OUT.stat().st_size // 1024} KB")
