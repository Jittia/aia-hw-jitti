"""Day 5: prepare a reading pack per Layer 1 candidate for the AI catalyst review (Layer 2).

For each of the top N companies (config top_n), from SEC EDGAR only:
  - latest 10-Q or 10-K: the MD&A section (management's own explanation of what drove results)
  - latest 8-K with Item 2.02 (earnings release): exhibit 99.1 text
  - the Layer 1 numbers from SEC companyfacts (no licensed data)
Packs are trimmed so one agent can read ~20 companies.

Run:  python src/layer2_prep.py     Out: data/cache/layer2/packs/<TICKER>.md (gitignored, SEC public text)
"""
from __future__ import annotations

import html
import json
import re
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from score import load_config
from sec_client import DATA_CACHE, DATA_PRIVATE, SecClient, cik10, read_cache

PACKS = DATA_CACHE / "layer2" / "packs"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}"
MDA_CHARS, PR_CHARS, DRIVER_CHARS = 9000, 5000, 5000


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    raw = re.sub(r"(?is)<ix:header>.*?</ix:header>", " ", raw)  # inline-XBRL hidden facts
    raw = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|li|h\d)>", "\n", raw)
    txt = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    txt = re.sub(r"[ \t\xa0]+", " ", txt)
    return re.sub(r"\n\s*\n+", "\n\n", txt).strip()


def extract_mda(text: str) -> str:
    """The MD&A heading appears in the table of contents too; take the occurrence followed by the most text
    before the next Item heading."""
    heads = list(re.finditer(r"(?i)management['’]s\s+discussion\s+and\s+analysis", text))
    # Real headings read "Item 2. Management's ..." (10-Q) or "Item 7. ..." (10-K); in-text mentions do not.
    titled = [m for m in heads if re.search(r"(?i)item\s+[27]\s*[\.:]?\s*$", text[max(0, m.start() - 25):m.start()])]
    def longest(cands) -> str:
        best = ""
        for m in cands:
            s = m.end()  # search for the end right after the heading, so a TOC entry ends at the next TOC line
            end = re.search(r"(?i)\bitem\s+(3|7a|8)[\.\s:]|quantitative\s+and\s+qualitative\s+disclosures?\s+about\s+market\s+risk",
                            text[s:])
            seg = text[m.start(): s + end.start()] if end else text[m.start(): s + 60000]
            if len(seg) > len(best):
                best = seg
        return best

    best = longest(titled)
    best = best if len(best) >= 2000 else longest(heads)
    # Skip forward-looking-statement boilerplate so the character budget goes to the business discussion.
    body = re.search(r"(?m)^\s*(overview|executive overview|business overview|results of operations)\b", best, re.I)
    return best[body.start():] if body and body.start() < len(best) * 0.6 else best


def revenue_driver_paragraphs(text: str, limit: int = DRIVER_CHARS) -> str:
    """Paragraphs that say what moved revenue: mention revenue/sales AND a change word AND a cause word."""
    out, used = [], 0
    for p in re.split(r"\n\s*\n", text):
        p = p.strip()
        if (len(p) > 120 and re.search(r"(?i)\b(revenue|net sales|sales)\b", p)
                and re.search(r"(?i)\b(increase|decrease|grew|growth|declin)", p)
                and re.search(r"(?i)\b(due to|driven by|primarily|attributable|result of|reflect)", p)):
            out.append(p)
            used += len(p)
            if used >= limit:
                break
    return "\n\n".join(out)[:limit]


def latest(recent: dict, forms: set[str], item: str | None = None) -> dict | None:
    for i, form in enumerate(recent["form"]):
        if form in forms and (item is None or item in recent["items"][i]):
            return {k: recent[k][i] for k in ("form", "filingDate", "accessionNumber", "primaryDocument", "reportDate")}
    return None


def build_pack(sec: SecClient, row: pd.Series) -> str:
    cik = row["cik"]
    sub = read_cache(DATA_CACHE / "submissions" / f"CIK{cik10(cik)}.json.gz")
    recent = sub["filings"]["recent"]
    cik_int = int(cik)
    lines = [f"# {row['ticker']} — {row['company_name']}", "",
             "## Layer 1 numbers (SEC XBRL, TTM to quarter ending " + str(row["q0_end"]) + ")",
             f"- TTM revenue: ${row['rev_ttm'] / 1e6:,.1f}M · YoY {row['rev_growth']:+.1%} · "
             f"acceleration {row['rev_accel'] * 100 if pd.notna(row['rev_accel']) else float('nan'):+.0f} pp",
             f"- Revenue vs earlier peak TTM: {row['rev_vs_peak']:+.1%}" if pd.notna(row["rev_vs_peak"]) else "- Revenue vs peak: n/a",
             f"- Gross margin change: {row['gm_delta'] * 100:+.1f} pp" if pd.notna(row["gm_delta"]) else "- Gross margin change: n/a",
             f"- Operating margin now {row['om']:.1%}, change {row['om_delta'] * 100:+.1f} pp" if pd.notna(row["om_delta"]) else "- Operating margin: n/a",
             f"- Turnaround flag: {row['turnaround_type'] or 'none'}",
             f"- Diluted shares YoY: {row['share_growth']:+.1%}" if pd.notna(row["share_growth"]) else "- Diluted shares YoY: n/a",
             f"- Layer 1 rank: {int(row['rank']) if pd.notna(row['rank']) else 'not ranked (radar candidate)'}", ""]

    periodic = latest(recent, {"10-Q", "10-K"})
    if periodic:
        acc = periodic["accessionNumber"].replace("-", "")
        url = f"{ARCHIVE.format(cik=cik_int, acc=acc)}/{periodic['primaryDocument']}"
        resp = sec.session.get(url, timeout=60)
        full = extract_mda(html_to_text(resp.text)) if resp.ok else ""
        mda = full[:MDA_CHARS]
        lines += [f"## MD&A from {periodic['form']} for period {periodic['reportDate']} (filed {periodic['filingDate']})",
                  f"Source: {url}", "", mda or "(MD&A not found)", ""]
        # The revenue explanation usually sits in "Results of Operations", past the trimmed overview.
        drivers = revenue_driver_paragraphs(full[MDA_CHARS:])
        if drivers:
            lines += ["## Revenue drivers (later MD&A paragraphs explaining revenue changes, same filing)",
                      f"Source: {url}", "", drivers, ""]

    er = latest(recent, {"8-K"}, item="2.02")
    if er:
        acc = er["accessionNumber"].replace("-", "")
        base = ARCHIVE.format(cik=cik_int, acc=acc)
        idx = sec.get_json(f"{base}/index.json") or {}
        # Exhibit names vary (ex99-1, a991press..., exx991...): drop the 8-K cover and XBRL R pages, prefer "991".
        names = [f["name"] for f in idx.get("directory", {}).get("item", [])
                 if f["name"].lower().endswith((".htm", ".html")) and f["name"] != er["primaryDocument"]
                 and not re.fullmatch(r"R\d+\.htm", f["name"]) and "index" not in f["name"]]
        ex = (next((n for n in names if "991" in n.replace("-", "").replace("_", "")), None)
              or next((n for n in names if "99" in n), None))
        if ex:
            resp = sec.session.get(f"{base}/{ex}", timeout=60)
            pr = html_to_text(resp.text)[:PR_CHARS] if resp.ok else ""
            lines += [f"## Earnings release (8-K Item 2.02, filed {er['filingDate']})", f"Source: {base}/{ex}", "", pr, ""]
    return "\n".join(lines)


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", nargs="*", help="build packs for these tickers instead of the Layer 1 top N")
    args = ap.parse_args()
    cfg = load_config()
    df = pd.read_csv(DATA_PRIVATE / f"layer1_scores_{cfg['universe_date']}.csv", dtype={"cik": str})
    top = (df[df["ticker"].isin(args.tickers)] if args.tickers
           else df[df["rank"] <= cfg["top_n"]].sort_values("rank"))
    PACKS.mkdir(parents=True, exist_ok=True)
    sec = SecClient()

    def work(row) -> tuple[str, int]:
        sec._throttle()
        text = build_pack(sec, row)
        (PACKS / f"{row['ticker']}.md").write_text(text, encoding="utf-8")
        return row["ticker"], len(text)

    with ThreadPoolExecutor(max_workers=4) as pool:
        sizes = dict(pool.map(work, [r for _, r in top.iterrows()]))
    s = pd.Series(sizes)
    no_mda = [t for t in s.index if "(MD&A not found)" in (PACKS / f"{t}.md").read_text()]
    no_pr = [t for t in s.index if "Earnings release" not in (PACKS / f"{t}.md").read_text()]
    if not args.tickers:
        (DATA_CACHE / "layer2" / "manifest.json").write_text(json.dumps(top[["ticker", "cik", "rank"]].to_dict("records")))
    print(f"packs: {len(s)} · median chars {int(s.median()):,} · total {int(s.sum()):,}")
    print(f"MD&A not found: {no_mda}")
    print(f"no earnings release found: {no_pr}")


if __name__ == "__main__":
    main()
