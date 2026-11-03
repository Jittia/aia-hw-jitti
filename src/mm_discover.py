"""Moat Momentum v2.0 · find the signals on 2013–2019, then test once on 2020–2023
(spec docs/specs/2026-11-03-compounder-signal-design.md §5–6).

Run:  .venv/bin/python src/mm_discover.py train     → output/data/discovery.json (train section, kept signals)
      .venv/bin/python src/mm_discover.py test      → adds the test section; refuses if one already exists
      .venv/bin/python src/mm_discover.py relabel   → after the 2026-11-04 label fix: same rows, same kept signals,
                                                       winners recomputed; adds a `label_fix` section, keeps `test`
Rows (signals + winner label per screen) are cached in data/cache/mm/discovery_rows_<period>_<settings fp>.pkl.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from mm_outcomes import label
from mm_signals import SIGNALS, raw_signals, signals_at

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache" / "mm"
OUT = ROOT / "output" / "data" / "discovery.json"


def screens(settings: dict, period: str) -> list[str]:
    c = settings["compounder"]
    lo, hi = (c["train"][0], c["test"][1]) if period == "all" else c[period]
    return [f"{y}-{md}" for y in range(lo, hi + 1) for md in c["screen_days"]]


def rows_path(settings: dict, period: str) -> Path:
    """Cache tied to the settings: changed settings never reuse rows built with old ones."""
    return CACHE / f"discovery_rows_{period}_{_fingerprint(settings)[:8]}.pkl"


def build_rows(settings: dict, period: str) -> pd.DataFrame:
    path = rows_path(settings, period)
    if path.exists():
        return pd.read_pickle(path)
    from mm_quarterly import ttm_panel
    facts, companies = pd.read_pickle(CACHE / "facts.pkl"), pd.read_pickle(CACHE / "companies.pkl")
    tax, cash = settings["data"]["tax_rate"], settings["data"]["excess_cash_pct_revenue"]
    all_path = CACHE / "ttm_panel_all.pkl"
    panel_all = pd.read_pickle(all_path) if all_path.exists() else ttm_panel(facts, None, tax, cash)
    parts = []
    for s in screens(settings, period):
        x = signals_at(facts, companies, s, settings, live=False)
        lab = label(panel_all, x.dropna(subset=["end"]))
        x = x.merge(lab.drop(columns=["end"]), on="cik", how="left")
        x["year"] = int(s[:4])
        parts.append(x)
        w = x["winner"]
        print(f"  {s}: universe {len(x)}, with outcome {int(w.notna().sum())}, winners {int((w == True).sum())}", flush=True)  # noqa: E712
    rows = pd.concat(parts, ignore_index=True)
    rows.to_pickle(path)
    return rows


def _top(rows: pd.DataFrame, score: pd.Series, share: float) -> pd.Series:
    """True for the top `share` of each screen by `score` (missing scores never count as top)."""
    out = pd.Series(False, index=rows.index)
    for _, idx in rows.groupby("screen").groups.items():
        s = score.loc[idx].dropna()
        n = int(round(share * len(s)))
        if n:
            out.loc[s.nlargest(n).index] = True
    return out


def _yearly(rows: pd.DataFrame, top: pd.Series) -> dict:
    ok = rows["winner"].notna()
    out = {}
    for y, g in rows[ok].groupby("year"):
        t = top.loc[g.index]
        win = g["winner"].astype(bool)
        out[int(y)] = {"top_rate": float(win[t].mean()) if t.any() else float("nan"), "base_rate": float(win.mean()),
                       "n_top": int(t.sum()), "winners_top": int(win[t].sum()), "n": int(len(g)), "winners": int(win.sum())}
    return out


def keep_rule(rows: pd.DataFrame, settings: dict, signals: list[tuple[str, int]] | None = None) -> dict:
    c = settings["compounder"]
    kept, by_year = {}, {}
    for name, direction in signals or SIGNALS:
        best = None
        for d in ((1, -1) if direction == 0 else (direction,)):
            r = rows[f"r_{name}"] if d == 1 else 100 - rows[f"r_{name}"]
            yr = _yearly(rows, _top(rows, r, c["top_share"]))
            wins = sum(v["top_rate"] > v["base_rate"] for v in yr.values())
            if best is None or wins > best[1]:
                best = (d, wins, yr)
        d, wins, yr = best
        by_year[name] = yr
        if wins >= c["keep_years"]:
            kept[name] = d
    return {"kept": kept, "by_year": by_year}


def combine(rows: pd.DataFrame, kept: dict) -> pd.Series:
    """Compounder Signal 0–100: mean of the kept ranks (flipped for direction −1); needs at least half of them."""
    parts = pd.concat([rows[f"r_{n}"] if d == 1 else 100 - rows[f"r_{n}"] for n, d in kept.items()], axis=1)
    need = math.ceil(len(kept) / 2)
    return parts.mean(axis=1).where(parts.notna().sum(axis=1) >= need)


def _fingerprint(settings: dict) -> str:
    return hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()


def run_train(settings: dict, path: Path = OUT) -> dict:
    if path.exists() and "test" in json.loads(path.read_text()):
        raise SystemExit("discovery.json already holds the test result; re-training would erase it (spec §6).")
    rows = build_rows(settings, "train")
    res = keep_rule(rows, settings)
    cs = combine(rows, res["kept"]) if res["kept"] else pd.Series(np.nan, index=rows.index)
    report = {"created": datetime.now(timezone.utc).isoformat(timespec="seconds"), "settings_sha256": _fingerprint(settings),
              "signals": [n for n, _ in SIGNALS], "kept": res["kept"],
              "train": {"by_year": res["by_year"], "screens": screens(settings, "train"),
                        "combined_in_sample": _yearly(rows, _top(rows, cs, settings["compounder"]["top_share"]))}}
    path.write_text(json.dumps(report, indent=1, default=float), encoding="utf-8")
    return report


def run_test(settings: dict, path: Path = OUT, rows: pd.DataFrame | None = None) -> dict:
    report = json.loads(path.read_text())
    if "test" in report:
        raise SystemExit("discovery.json already has a test result; the test period is evaluated once (spec §6).")
    if report.get("settings_sha256") != _fingerprint(settings):
        raise SystemExit("settings changed since training; the test must use the settings the signals were chosen with.")
    c = settings["compounder"]
    rows = build_rows(settings, "test") if rows is None else rows
    cs = combine(rows, report["kept"])
    top = _top(rows, cs, c["top_share"])
    ok = rows["winner"].notna()
    win = rows.loc[ok, "winner"].astype(bool)
    top_rate, base = float(win[top[ok]].mean()), float(win.mean())
    picks = rows[top].assign(cs=cs[top])[["screen", "ticker", "name", "cs", "winner", "cagr3"]
                                         + (["rebound"] if "rebound" in rows else [])]
    excl = None
    if "rebound" in rows:
        # sensitivity fixed before the test was run (2026-11-03): drop companies recovering toward an earlier level
        keep = ~rows["rebound"].fillna(False).astype(bool)
        r2 = rows[keep]
        t2 = _top(r2, cs[keep], c["top_share"])
        ok2 = r2["winner"].notna()
        w2 = r2.loc[ok2, "winner"].astype(bool)
        tr2, b2 = float(w2[t2[ok2]].mean()), float(w2.mean())
        excl = {"top_rate": tr2, "base_rate": b2, "multiple": tr2 / b2 if b2 else None,
                "n_removed": int((~keep).sum()), "by_year": _yearly(r2, t2)}
    report["test"] = {"run": datetime.now(timezone.utc).isoformat(timespec="seconds"), "top_rate": top_rate, "base_rate": base,
                      "multiple": top_rate / base if base else None, "passed": bool(base and top_rate >= c["pass_multiple"] * base),
                      "no_outcome_share_top": float(rows.loc[top, "winner"].isna().mean()),
                      "by_year": _yearly(rows, top), "excl_rebound": excl, "picks": picks.round(3).to_dict("records")}
    path.write_text(json.dumps(report, indent=1, default=float), encoding="utf-8")
    return report


def _evaluate(rows: pd.DataFrame, kept: dict, share: float) -> dict:
    cs = combine(rows, kept)
    top = _top(rows, cs, share)
    ok = rows["winner"].notna()
    win = rows.loc[ok, "winner"].astype(bool)
    top_rate, base = float(win[top[ok]].mean()), float(win.mean())
    return {"top_rate": top_rate, "base_rate": base, "multiple": top_rate / base if base else None,
            "with_outcome": int(ok.sum()), "winners": int(win.sum()), "by_year": _yearly(rows, top)}


def relabel(settings: dict, path: Path = OUT) -> dict:
    """Label fix found in review (2026-11-04): a missing +4/+8 quarter made a company a loser instead of 'no outcome'.
    Signals and kept signals are NOT changed; only the winner column is recomputed. The original `test` stays."""
    report = json.loads(path.read_text())
    if "test" not in report:
        raise SystemExit("run train and test first")
    panel_all = pd.read_pickle(CACHE / "ttm_panel_all.pkl")
    fix = {"note": "winner recomputed with the fixed label; kept signals unchanged (chosen before the fix)"}
    for per in ("train", "test"):
        rp = rows_path(settings, per)
        rows = pd.read_pickle(rp)
        backup = rp.with_name(rp.stem + "_asrun.pkl")
        if not backup.exists():
            rows.to_pickle(backup)
        lab_cols = [c for c in rows.columns if c.startswith("c") and c[1:2].isdigit()] + ["cagr3", "winner"]
        parts = []
        for scr, g in rows.groupby("screen", sort=False):
            g = g.drop(columns=[c for c in lab_cols if c in g])
            have = g.dropna(subset=["end"])
            lab = label(panel_all, have).drop(columns=["end"])
            parts.append(g.merge(lab, on="cik", how="left"))
        rows = pd.concat(parts, ignore_index=True)
        rows.to_pickle(rp)
        ev = _evaluate(rows, report["kept"], settings["compounder"]["top_share"])
        if per == "train":
            ev["kept_if_retrained"] = keep_rule(rows, settings)["kept"]
        fix[per] = ev
    report["label_fix"] = fix
    path.write_text(json.dumps(report, indent=1, default=float), encoding="utf-8")
    return report


def main() -> None:
    settings = yaml.safe_load((ROOT / "settings.yaml").read_text())
    if len(sys.argv) < 2 or sys.argv[1] not in ("train", "test", "relabel"):
        raise SystemExit("usage: mm_discover.py train | test | relabel")
    cmd = sys.argv[1]
    if cmd == "train":
        r = run_train(settings)
        print("kept:", r["kept"])
        for n, yr in r["train"]["by_year"].items():
            print(f"  {n:20}", " ".join(f"{y}:{v['top_rate']:.3f}/{v['base_rate']:.3f}" for y, v in yr.items()))
    elif cmd == "relabel":
        f = relabel(settings)["label_fix"]
        for per in ("train", "test"):
            v = f[per]
            print(f"{per}: top 10% {v['top_rate']:.3%} vs base {v['base_rate']:.3%} = {v['multiple']:.2f}x "
                  f"(with outcome {v['with_outcome']:,}, winners {v['winners']})")
        print("kept if retrained:", f["train"]["kept_if_retrained"])
    elif cmd == "test":
        t = run_test(settings)["test"]
        print(f"test: top 10% winner rate {t['top_rate']:.3%} vs base {t['base_rate']:.3%} = {t['multiple']:.2f}x · passed {t['passed']}")


if __name__ == "__main__":
    main()
