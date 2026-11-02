"""Day 5: verify the reader agents' output and build the shortlist.

Checks every agent result mechanically before it can count:
  - all top-N tickers present, keys and allowed values valid
  - evidence_quote appears verbatim in that company's pack (whitespace/quote-mark normalised)
  - evidence_url is one of the pack's own `Source:` URLs
Watchlist = tier A (verdict "shortlist") + tier B (best "watch" names), verified evidence and structural
catalyst only, capped at MAX_SHORTLIST.

Run:  python src/layer2_merge.py
Out:  output/layer2_review.csv  (all reviewed companies, public: SEC-derived only)
      output/shortlist.csv      (the shortlist)
"""
from __future__ import annotations

import json
import re

import pandas as pd

from score import load_config
from sec_client import DATA_CACHE, DATA_PRIVATE, ROOT

RESULTS = DATA_CACHE / "layer2" / "results"
PACKS = DATA_CACHE / "layer2" / "packs"
OUT_REVIEW = ROOT / "output" / "layer2_review.csv"
OUT_SHORTLIST = ROOT / "output" / "shortlist.csv"
MAX_SHORTLIST = 20

TYPES = {"new_tam", "new_s_curve", "turnaround", "new_market", "acquisition", "cyclical_recovery", "one_off", "insufficient"}
STRUCTURAL = {"new_tam", "new_s_curve", "turnaround", "new_market"}
VERDICTS = {"shortlist", "watch", "reject"}
KEYS = ["ticker", "catalyst_type", "driver", "evidence_quote", "evidence_url", "organic", "red_flags",
        "confidence", "verdict", "reason"]


def norm(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("—", "-").replace("–", "-")
    return re.sub(r"\s+", " ", s).strip().lower()


def main() -> None:
    cfg = load_config()
    scores = pd.read_csv(DATA_PRIVATE / f"layer1_scores_{cfg['universe_date']}.csv", dtype={"cik": str})
    top = scores[scores["rank"] <= cfg["top_n"]]

    rows = []
    for f in sorted(RESULTS.glob("batch_*.json")):
        rows += json.loads(f.read_text(encoding="utf-8"))
    rev = pd.DataFrame(rows)
    problems = []
    missing = sorted(set(top["ticker"]) - set(rev["ticker"]))
    dupes = rev["ticker"][rev["ticker"].duplicated()].tolist()
    if missing or dupes:
        problems.append(f"missing {missing} duplicates {dupes}")
    rev = rev.drop_duplicates("ticker")
    # Re-reviews (after a pack was improved) replace the first review for those tickers.
    rechecked = []
    for f in sorted(RESULTS.glob("recheck_*.json")):
        redo = pd.DataFrame(json.loads(f.read_text(encoding="utf-8")))
        rechecked += redo["ticker"].tolist()
        rev = pd.concat([rev[~rev["ticker"].isin(redo["ticker"])], redo], ignore_index=True)
    # Companies reviewed earlier but no longer in the top N (e.g. pushed out by the acquisition penalty) are dropped.
    dropped = sorted(set(rev["ticker"]) - set(top["ticker"]))
    rev = rev[rev["ticker"].isin(top["ticker"])]

    checks = []
    for r in rev.itertuples():
        pack = (PACKS / f"{r.ticker}.md").read_text(encoding="utf-8")
        sources = set(re.findall(r"^Source: (\S+)", pack, re.M))
        quote_ok = bool(r.evidence_quote) and norm(r.evidence_quote) in norm(pack)
        url_ok = r.evidence_url in sources
        valid = (r.catalyst_type in TYPES and r.verdict in VERDICTS and r.confidence in {"high", "medium", "low"})
        words = len(str(r.evidence_quote).split())
        checks.append({"ticker": r.ticker, "quote_verified": quote_ok, "url_verified": url_ok,
                       "schema_ok": valid, "quote_words": words})
    rev = rev.merge(pd.DataFrame(checks), on="ticker")
    rev["evidence_verified"] = rev["quote_verified"] & rev["url_verified"] & rev["schema_ok"] & (rev["quote_words"] <= 30)
    rev["red_flags"] = rev["red_flags"].map(lambda x: "; ".join(x) if isinstance(x, list) else str(x))

    l1 = ["ticker", "rank", "q0_end", "rev_ttm", "rev_growth", "rev_accel", "gm_delta", "om_delta",
          "turnaround_type", "share_growth", "rev_vs_peak", "rev_url"]
    rev = rev.merge(top[l1].rename(columns={"rank": "layer1_rank"}), on="ticker", how="left").sort_values("layer1_rank")
    cols = ["layer1_rank", "ticker", "verdict", "catalyst_type", "confidence", "organic", "driver", "evidence_quote",
            "evidence_url", "red_flags", "reason", "evidence_verified", "q0_end", "rev_ttm", "rev_growth", "rev_accel",
            "gm_delta", "om_delta", "turnaround_type", "share_growth", "rev_vs_peak", "rev_url"]
    rev[cols].to_csv(OUT_REVIEW, index=False)

    # Two tiers (Jitti's choice, Day 5): A = confirmed shortlist; B = best "watch" names to fill up to MAX_SHORTLIST.
    ok = rev["evidence_verified"] & rev["catalyst_type"].isin(STRUCTURAL)
    tier_a = rev[ok & (rev["verdict"] == "shortlist")].assign(tier="A")
    conf_order = {"high": 0, "medium": 1, "low": 2}
    tier_b = (rev[ok & (rev["verdict"] == "watch")]
              .assign(tier="B", _c=lambda d: d["confidence"].map(conf_order))
              .sort_values(["_c", "layer1_rank"]).drop(columns="_c"))
    short = pd.concat([tier_a, tier_b]).head(MAX_SHORTLIST)
    eligible = tier_a
    short[["tier"] + cols].to_csv(OUT_SHORTLIST, index=False)

    print(f"reviewed: {len(rev)} · problems: {problems or 'none'} · re-reviewed: {rechecked or 'none'}")
    print("verdicts:", rev["verdict"].value_counts().to_dict())
    print("catalyst types:", rev["catalyst_type"].value_counts().to_dict())
    print(f"quote verified {int(rev['quote_verified'].sum())}/{len(rev)} · url verified {int(rev['url_verified'].sum())}/{len(rev)} · "
          f"quotes > 30 words: {int((rev['quote_words'] > 30).sum())}")
    bad = rev[~rev["evidence_verified"]]["ticker"].tolist()
    print(f"failed verification: {bad}")
    print(f"dropped from review (left top {cfg['top_n']}): {len(dropped)}")
    print(f"watchlist ({len(short)}): tier A {tier_a['ticker'].tolist()} · tier B {short[short.tier == 'B']['ticker'].tolist()}")


if __name__ == "__main__":
    main()
