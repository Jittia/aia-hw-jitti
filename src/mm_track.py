"""Moat Momentum · step 7 (brief §6D): freeze each official run's shortlist with a fingerprint.

freeze:  writes track_record/<as_of>.json with the shortlist, settings, methodology version and data date, plus
         a SHA-256 fingerprint of that content. Committed to git, so later edits would show in history and the
         fingerprint would no longer match.
verify:  recomputes every fingerprint.
page:    writes output/data/track_data.js for the Track Record tab (performance since each freeze is added once
         a month-end price exists after the freeze date).
Run:     .venv/bin/python src/mm_track.py freeze | verify | page
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "track_record"


def canonical(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def freeze() -> None:
    s = (ROOT / "output" / "data" / "site_data.js").read_text(encoding="utf-8")
    M = json.loads(s[len("window.MM = "):s.rindex(";")])
    settings = yaml.safe_load((ROOT / "settings.yaml").read_text())
    sl = sorted([c for c in M["companies"] if c["shortlist"]], key=lambda c: c["rank"])
    record = {
        "as_of": M["meta"]["as_of"], "methodology": settings["methodology_version"],
        "sec_data_retrieved": settings["data"]["sec_retrieved"], "settings": settings,
        "shortlist": [{"rank_in_universe": int(c["rank"]), "ticker": c["ticker"], "cik": c["cik"], "name": c["name"],
                       "moat_score": round(c["moat_score"], 2), "fiscal_year": c["fy"], "latest_10k": c["accn"]} for c in sl],
    }
    fp = hashlib.sha256(canonical(record)).hexdigest()
    DIR.mkdir(exist_ok=True)
    path = DIR / f"{record['as_of']}.json"
    if path.exists():
        raise SystemExit(f"{path.name} already frozen; a frozen record is never overwritten")
    path.write_text(json.dumps({"fingerprint_sha256": fp, "record": record}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"frozen {path.name}: {len(sl)} names, fingerprint {fp}")


def verify() -> None:
    for path in sorted(DIR.glob("*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        ok = hashlib.sha256(canonical(d["record"])).hexdigest() == d["fingerprint_sha256"]
        print(f"{path.name}: {'OK' if ok else 'FINGERPRINT MISMATCH'}")


def page() -> None:
    import html
    rows, lists = [], []
    for path in sorted(DIR.glob("*.json"), reverse=True):
        d = json.loads(path.read_text(encoding="utf-8"))
        r = d["record"]
        ok = hashlib.sha256(canonical(r)).hexdigest() == d["fingerprint_sha256"]
        check = "<span class='badge b-good dot'>Verified</span>" if ok else "<span class='badge b-risk dot'>Mismatch</span>"
        rows.append(f"<tr><td>{r['as_of']}</td><td>v{r['methodology']}</td><td class='r'>{len(r['shortlist'])}</td>"
                    f"<td><code style='font-size:11px;word-break:break-all'>{d['fingerprint_sha256']}</code></td>"
                    f"<td>{check}</td>"
                    f"<td class='small'>Pending: first month-end after {r['as_of']}</td></tr>")
        lists.append(f"<div class='card'><h3>{r['as_of']}</h3><p class='small'>" +
                     ", ".join(html.escape(x['ticker']) for x in r['shortlist']) + "</p></div>")
    body = f"""<h1>Track record</h1>
<p class="muted">Every official run freezes its shortlist, settings and data date in <code>track_record/</code> of the public GitHub repository, with a SHA-256 fingerprint of that content. Git history shows when each file was added; changing a frozen list afterwards would break its fingerprint. Performance is measured from the first month-end after each freeze, against the S&amp;P 500 total return.</p>
<div class="tbl"><table><thead><tr><th>Frozen</th><th>Method</th><th class="r">Names</th><th>Fingerprint (SHA-256)</th><th>Check</th><th>Performance since</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<h2>Frozen shortlists</h2><div class="grid g3">{''.join(lists)}</div>
<p class="small">The record starts on 2026-11-03, so no live results exist yet. Past results in the Proof tab are back-tests, not a live record.</p>"""
    import csv
    with open(ROOT / "output" / "sheet" / "track_record.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Frozen", "Methodology", "Fingerprint (SHA-256)", "Ticker", "Company", "Moat Score", "Rank in universe"])
        for path in sorted(DIR.glob("*.json"), reverse=True):
            d = json.loads(path.read_text(encoding="utf-8"))
            for x in d["record"]["shortlist"]:
                w.writerow([d["record"]["as_of"], d["record"]["methodology"], d["fingerprint_sha256"], x["ticker"], x["name"],
                            x["moat_score"], x["rank_in_universe"]])
    (ROOT / "output" / "data" / "track_data.js").write_text("window.MM_TRACK = " + json.dumps({"html": body}) + ";\n", encoding="utf-8")
    print("wrote output/data/track_data.js")


if __name__ == "__main__":
    {"freeze": freeze, "verify": verify, "page": page}[sys.argv[1] if len(sys.argv) > 1 else "verify"]()
