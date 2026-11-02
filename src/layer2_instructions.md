---
title: Layer 2 catalyst review — instructions for reader agents
type: instruction
created: 2026-11-02
updated: 2026-11-02
tags: [layer2, catalyst, US]
sources: [SEC EDGAR filings (10-Q, 10-K, 8-K exhibit 99.1)]
status: verified
---

# Layer 2 catalyst review — instructions

You classify why a company's numbers inflected, using **only** the reading pack given to you
(`data/cache/layer2/packs/<TICKER>.md`). Each pack has: Layer 1 numbers from SEC XBRL, the MD&A of the latest
10-Q/10-K, and (often) the latest earnings press release (8-K exhibit 99.1). Each section has a `Source:` URL.

## Rules

1. **Pack text only.** Do not use outside knowledge, news, or memory of the company, even if you know it.
   If the pack does not explain the driver, say `insufficient`.
2. **Quote verbatim.** `evidence_quote` must be copied exactly from the pack, at most 30 words, and must
   support `driver`. `evidence_url` is the `Source:` URL of the section you quoted.
3. **Numbers first.** The catalyst must match the Layer 1 numbers (e.g. a "new S-curve" claim needs revenue
   growth that the pack attributes to the new product/segment). Management optimism alone is not evidence.
4. **Be strict.** Most companies are not 10x candidates. Rejecting is the expected outcome.

## catalyst_type (pick one)

| Type | Meaning | Structural? |
|---|---|---|
| `new_tam` | Growth from a large market that has newly opened up for the company (e.g. AI data-center demand, a new regulation creating demand) | yes |
| `new_s_curve` | A new product, segment or technology growing much faster than the core and already a material share of revenue | yes |
| `turnaround` | Self-help: new management, restructuring, exiting loss-making units, pricing/mix changes that lift margins, **not** a market cycle | yes |
| `new_market` | Expansion into new geographies, customer types or channels that drives the growth | yes |
| `acquisition` | Growth mostly from buying another company (inorganic) | no |
| `cyclical_recovery` | Commodity prices, industry cycle, recovery from a temporary disruption (fire, strike, weather, destocking ending) | no |
| `one_off` | Insurance proceeds, litigation, asset sales, milestone/licence payments, accounting effects | no |
| `insufficient` | The pack does not explain the driver | no |

## verdict

- `shortlist`: structural type, numbers consistent with it, confidence `high` or `medium`, no serious red flag.
- `watch`: structural type but early, unproven, or with a notable red flag.
- `reject`: non-structural type, or the evidence does not hold up.

## Output

Write a JSON array to the result file named in your task, one object per ticker, exactly these keys:

```json
{
  "ticker": "ABC",
  "catalyst_type": "new_s_curve",
  "driver": "Own words, max 25 words: what is driving the numbers.",
  "evidence_quote": "Verbatim from the pack, max 30 words.",
  "evidence_url": "https://www.sec.gov/Archives/...",
  "organic": true,
  "red_flags": ["short phrases, e.g. 'customer concentration 40%', 'going-concern doubt', 'growth from acquisition'"],
  "confidence": "high | medium | low",
  "verdict": "shortlist | watch | reject",
  "reason": "Max 30 words: why this verdict."
}
```

`organic` = false if the pack says a meaningful part of the growth came from acquisitions.
