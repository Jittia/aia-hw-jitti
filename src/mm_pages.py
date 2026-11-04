"""Moat Momentum · Calculation check: the printed page of each SEC value
(spec docs/specs/2026-11-04-calculation-check-design.md §6).

SEC filings are Inline XBRL: every number carries its tag (`ix:nonFraction name="us-gaap:…"`) and a context with its
period. We split the main 10-K / 10-Q document at its page breaks, read each page's printed number ("84", "F-3"), and
find the page holding the tagged number with the right tag, period and value. A value we cannot place is "not
located" (None): never a guess.

split_pages(html) · contexts(html) · locate(pages, ctx, tag, value, start, end) · pages_for(cik, accn, wanted)
Run: .venv/bin/python src/mm_pages.py      reads output/data/audit/a*.js, fetches each filing once (SEC, ≤ 10
requests a second), writes data/cache/mm/pages/<accession>.json (results only, not the documents). Resumable.
"""
from __future__ import annotations

import html as htmllib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache" / "mm" / "pages"

BREAK = re.compile(r"<[^>]+(?:page-break-(?:after|before)\s*:\s*always|break-(?:before|after)\s*:\s*page)[^>]*>", re.I)
LABEL = re.compile(r"^(?:[A-Z]{1,2}-)?\d{1,3}$")
CTX = re.compile(r"<xbrli:context\b[^>]*\bid=\"([^\"]+)\"[^>]*>(.*?)</xbrli:context>", re.S | re.I)
FACT = re.compile(r"<ix:nonFraction\b([^>]*)>(.*?)</ix:nonFraction>", re.S | re.I)
HEADER = re.compile(r"<ix:header>.*?</ix:header>", re.S | re.I)
ATTR = re.compile(r"([\w:.-]+)\s*=\s*\"([^\"]*)\"")


def _text(fragment: str) -> str:
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", fragment, flags=re.S | re.I)
    t = re.sub(r"<ix:header>.*?</ix:header>", " ", t, flags=re.S | re.I)
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", t)).replace("\xa0", " ")).strip()


NUM = r"((?:[A-Z]{1,2}-)?\d{1,3})"
FOOTERS = [re.compile(r"[-–—]\s*" + NUM + r"\s*[-–—]\s*$"),            # "- 3 -", "-3-"
           re.compile(r"\bPage\s+" + NUM + r"\s*$", re.I),              # "Page 7"
           re.compile(r"\|\s*" + NUM + r"\s*$"),                         # "Acme Corp | 13"
           re.compile(r"(?:^|\s)" + NUM + r"\s*\|[^|]{1,80}$"),           # "12 | Acme Corp 2025 Form 10-K"
           re.compile(r"(?:^|[^\s$(])\s+" + NUM + r"\s*$|^" + NUM + r"\s*$")]  # a bare "84" or "F-3", not "$ 456"


def page_label(text: str) -> str:
    """The printed page number at the end of a page's text, or "" when there is none."""
    t = re.sub(r"[\u200b-\u200f\u202a-\u202e\u2060\ufeff]", "", text)
    t = re.sub(r"(?:\s*Table of Contents)+\s*$", "", t, flags=re.I).strip()[-160:]
    for rx in FOOTERS:
        m = rx.search(t)
        if m:
            return next(g for g in m.groups() if g)
    return ""


def trust_labels(labels: list[str]) -> list[str]:
    """Keep a plain page number only when it follows the document's numbering: its offset from the page position
    is the most common offset (±2). Lettered pages ("F-3") are kept."""
    offs = [int(l) - i for i, l in enumerate(labels) if l.isdigit()]
    if not offs:
        return labels
    mode = max(set(offs), key=offs.count)
    return [l if not l.isdigit() or abs(int(l) - i - mode) <= 2 else "" for i, l in enumerate(labels)]


def split_pages(html: str) -> list[tuple[str, str]]:
    """[(printed page label or "", page html)], split at CSS page breaks; label from the page's footer text."""
    chunks = BREAK.split(html)
    labels = trust_labels([page_label(_text(c)) for c in chunks])
    out = list(zip(labels, chunks))
    if out and not out[-1][0] and not _text(out[-1][1]):
        out.pop()  # an empty tail after the last page break
    return out


def contexts(html: str) -> dict[str, tuple[str | None, str]]:
    """context id → (start or None for a balance, end). Contexts with dimensions (a segment) are left out: the
    tool's values are company totals."""
    out = {}
    for cid, body in CTX.findall(html):
        if re.search(r"<xbrli:segment\b", body, re.I):
            continue
        inst = re.search(r"<xbrli:instant>\s*([\d-]+)\s*<", body, re.I)
        s = re.search(r"<xbrli:startDate>\s*([\d-]+)\s*<", body, re.I)
        e = re.search(r"<xbrli:endDate>\s*([\d-]+)\s*<", body, re.I)
        if inst:
            out[cid] = (None, inst.group(1))
        elif s and e:
            out[cid] = (s.group(1), e.group(1))
    return out


def _value(attrs: dict, inner: str) -> float | None:
    t = _text(inner).replace(",", "").replace(" ", "")
    if t in ("", "-", "—", "–") or "fixed-zero" in attrs.get("format", ""):
        v = 0.0
    else:
        try:
            v = float(t)
        except ValueError:
            return None
    v *= 10 ** int(attrs.get("scale", "0") or 0)
    return -v if attrs.get("sign") == "-" else v


def locate(pages: list[tuple[str, str]], ctx: dict, tag: str, value: float, start: str | None, end: str) -> str | None:
    """Where `tag` for (start, end) with `value` (within the shown rounding) is printed: the page's printed number;
    when that page has none, "cover page" for a cover-page share count on the first two pages, else "#N" (the Nth
    page of the filing's document). A page with a printed number wins over an unnumbered one. None = not found."""
    want, unnumbered = (start or None, end), None
    for i, (lab, page) in enumerate(pages):
        page = HEADER.sub(" ", page)  # facts in the hidden XBRL header are not printed on any page
        for a_txt, inner in FACT.findall(page):
            a = dict(ATTR.findall(a_txt))
            if a.get("name", "").split(":")[-1] != tag or ctx.get(a.get("contextRef")) != want:
                continue
            v = _value(a, inner)
            if v is None:
                continue
            tol = 0.5 * 10 ** int(a.get("scale", "0") or 0)
            if abs(v - value) <= max(tol, 0.5):
                if lab:
                    return lab
                if unnumbered is None:
                    unnumbered = "cover page" if tag.startswith("EntityCommonStock") and i <= 1 else f"#{i + 1}"
    return unnumbered


def main_document(cik: int, accn: str, client) -> str | None:
    """URL of the filing's main document (the first .htm of type 10-K / 10-Q in the filing index)."""
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn.replace('-', '')}/"
    client._throttle()
    r = client.session.get(base + accn + "-index.htm", timeout=60)
    if r.status_code != 200:  # a failed download is retried on the next run, never cached as "not located"
        raise RuntimeError(f"filing index {accn}: HTTP {r.status_code}")
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", r.text, re.S):
        href = re.search(r'href="([^"]+\.htm)"', row)
        if href and re.search(r">\s*10-[KQ][^<]*<", row):
            return "https://www.sec.gov" + href.group(1).replace("/ix?doc=", "")
    return None


def pages_for(cik: int, accn: str, wanted: list[tuple], client=None) -> dict:
    """{"tag|start|end": label or None} for wanted = [(tag, start, end, value)]; one document download."""
    from sec_client import SecClient
    client = client or SecClient()
    url = main_document(cik, accn, client)
    out = {"_url": url}
    html = ""
    if url:
        client._throttle()
        r = client.session.get(url, timeout=180)
        if r.status_code != 200:
            raise RuntimeError(f"document {accn}: HTTP {r.status_code}")
        html = r.text
    P, C = (split_pages(html), contexts(html)) if html else ([], {})
    for tag, start, end, val in wanted:
        out[f"{tag}|{start or ''}|{end}"] = locate(P, C, tag, val, start, end) if html else None
    return out


def needed_from_audit(out_dir: Path) -> dict[str, tuple[int, list[tuple]]]:
    """accession → (cik, [(tag, start, end, value)]) for every filed part in output/data/audit/a*.js."""
    from mm_audit import load_export
    data = load_export(out_dir)
    need: dict[str, tuple[int, set]] = {}
    for cik, c in data["co"].items():
        for by_pt in c["it"].values():
            for _val, comps in by_pt.values():
                for tag, _s, _u, _v, parts in comps:
                    for _kind, val, fi, start, end, _pg in parts:
                        if fi is None or val is None:
                            continue
                        accn = c["f"][fi][0]
                        need.setdefault(accn, (int(cik), set()))[1].add((tag, start, end, val))
        m = c.get("m") or {}
        if m.get("cover_accn") and m.get("cover_raw") is not None:  # cover-page share count (dei tag)
            need.setdefault(m["cover_accn"], (int(cik), set()))[1].add(
                ("EntityCommonStockSharesOutstanding", None, m["cover_end"], int(m["cover_raw"])))
    return {a: (cik, sorted(w, key=str)) for a, (cik, w) in need.items()}


def run(need: dict, cache: Path = CACHE, fetch=None, workers: int = 6, client=None) -> tuple[int, int]:
    """Fetch every accession not yet cached, `workers` at a time (the shared SEC client keeps the total at or under
    10 requests a second); returns (values located, values looked up) over the whole cache."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    fetch = fetch or pages_for
    if client is None:
        from sec_client import SecClient
        client = SecClient()
    cache.mkdir(parents=True, exist_ok=True)
    def cached(accn):
        try:
            return json.loads((cache / f"{accn}.json").read_text())
        except (OSError, ValueError):
            return None
    def complete(accn):  # readable and holding every value now needed (a later run may need new ones)
        res = cached(accn)
        return res is not None and all(f"{t}|{s or ''}|{e}" in res for t, s, e, _ in need[accn][1])
    todo = [a for a in need if not complete(a)]

    def one(accn):
        cik, wanted = need[accn]
        tmp = cache / f".{accn}.tmp"
        tmp.write_text(json.dumps(fetch(cik, accn, wanted, client)))
        tmp.replace(cache / f"{accn}.json")  # atomic: an interrupted run never leaves half a file

    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(one, a): a for a in todo}
        for i, f in enumerate(as_completed(futs)):
            if f.exception() is not None:  # one bad filing must not stop the run; it is retried next time
                print(f"  {futs[f]}: {type(f.exception()).__name__}", flush=True)
            if (i + 1) % 500 == 0:
                print(f"  {i + 1}/{len(todo)} filings", flush=True)
    found = total = 0
    for accn, (_cik, wanted) in need.items():
        res = cached(accn)
        if res is None:
            continue
        for tag, start, end, _v in wanted:
            total += 1
            found += res.get(f"{tag}|{start or ''}|{end}") is not None
    return found, total


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "src"))
    need = needed_from_audit(ROOT / "output" / "data" / "audit")
    print(f"filings: {len(need):,}, already cached: {sum((CACHE / f'{a}.json').exists() for a in need):,}", flush=True)
    found, total = run(need)
    print(f"located {found:,} of {total:,} values ({found / max(total, 1):.1%})", flush=True)
