---
title: Event study — catalyst-of-change radar (Phase 1.5)
type: note
created: 2026-11-02
updated: 2026-11-02
tags: [event-study, US, radar]
sources: [SEC EDGAR XBRL companyfacts, SEC submissions index, SEC Insider Transactions Data Sets, Yahoo Finance via yfinance]
status: draft
---

# Event study: do catalyst-of-change signals lead to ≥5x?

Every event onset and every first entry into a stage, dated by its **SEC filing date**, is followed for **5 years** from the month-end after the filing. Tuning window: 2012-12-31 → 2017-12-31; **holdout**: after 2017-12-31 → 2021-10-31 (not used to choose anything).

- **Lift (5x)** = share of entries reaching ≥5x ÷ share of *all* priced companies reaching ≥5x from the same months. 1.0 = no better than random.
- Prices: Yahoo Finance adjusted close (retrieved 2026-11-02). Fundamentals and events: SEC EDGAR (filing dates).

> **Survivorship bias:** only companies listed on 2026-11-02 are included, so all hit rates are optimistic. Lifts compare groups drawn from the same survivors, so they are the fairer number.
> **Overlap:** a company can enter a stage several times; each entry counts.

## Findings

1. **Confirmed works out of sample:** holdout lift **1.68x** (8.7% reached ≥5x vs 5.1% for all companies); Emerging 1.43x. Spec target was ≥1.5x.
2. **Radar alone has no out-of-sample edge** (holdout 0.99x). The edge comes from the Emerging filters: beating the industry median, organic growth, limited dilution and 5x plausibility. Radar is a logbook, not a signal.
3. **Most robust single events:** gross-margin step-up (1.39x tune / 1.48x holdout) and turning profitable (1.33x / 1.67x). Revenue acceleration and contracted-revenue jumps faded in the holdout.
4. **8-K officer changes and material agreements carry no signal** (1.02x / 0.96x tune); insider cluster buys were flat in tuning (1.01x) though 1.37x in the holdout. None of them triggers Radar; they are context.
5. **Tuning to the best in-sample result overfits:** see the grid. Thresholds stay at values set before the study.

## Results

| Group | Window | Entries | Companies | ≥3x | ≥5x | ≥10x | Median | Halved | Lift (5x) |
|---|---|---|---|---|---|---|---|---|---|
| all company-quarters | tune | 25,256 | 1,422 | 16.2% | 5.2% | 1.1% | 1.57x | 10.8% | **1.03x** |
| all company-quarters | holdout | 27,686 | 1,755 | 15.0% | 5.3% | 1.2% | 1.38x | 14.9% | **1.04x** |
| event: contract_jump | tune | 806 | 419 | 23.7% | 8.9% | 1.6% | 1.64x | 14.6% | **1.79x** |
| event: contract_jump | holdout | 1,572 | 929 | 16.0% | 5.7% | 1.6% | 1.37x | 17.7% | **1.09x** |
| event: gm_step | tune | 700 | 480 | 16.7% | 7.3% | 1.9% | 1.47x | 14.7% | **1.39x** |
| event: gm_step | holdout | 734 | 588 | 18.3% | 7.5% | 2.0% | 1.33x | 19.3% | **1.48x** |
| event: insider_cluster | tune | 1,024 | 638 | 16.6% | 5.3% | 1.9% | 1.40x | 17.4% | **1.01x** |
| event: insider_cluster | holdout | 1,270 | 891 | 17.3% | 7.6% | 2.0% | 1.26x | 21.9% | **1.37x** |
| event: material_deal | tune | 5,446 | 1,471 | 14.9% | 4.9% | 1.2% | 1.46x | 14.3% | **0.96x** |
| event: material_deal | holdout | 5,476 | 1,892 | 13.1% | 5.1% | 1.4% | 1.23x | 20.8% | **1.02x** |
| event: officer_change | tune | 7,212 | 1,534 | 15.1% | 5.2% | 1.0% | 1.52x | 12.0% | **1.02x** |
| event: officer_change | holdout | 7,170 | 1,974 | 13.9% | 4.9% | 1.4% | 1.30x | 18.6% | **0.98x** |
| event: rev_accel | tune | 1,604 | 840 | 17.6% | 7.0% | 1.8% | 1.44x | 14.2% | **1.45x** |
| event: rev_accel | holdout | 2,603 | 1,472 | 13.6% | 5.2% | 1.2% | 1.23x | 19.5% | **1.05x** |
| event: turn_positive | tune | 717 | 479 | 15.8% | 6.8% | 0.8% | 1.53x | 11.6% | **1.33x** |
| event: turn_positive | holdout | 1,033 | 741 | 20.5% | 8.7% | 2.2% | 1.38x | 17.5% | **1.67x** |
| stage entry: radar | tune | 1,934 | 1,090 | 17.5% | 6.6% | 1.6% | 1.56x | 12.2% | **1.30x** |
| stage entry: radar | holdout | 2,618 | 1,595 | 13.9% | 5.0% | 1.0% | 1.30x | 16.9% | **0.99x** |
| stage entry: emerging | tune | 488 | 343 | 21.7% | 9.0% | 2.3% | 1.45x | 13.3% | **1.82x** |
| stage entry: emerging | holdout | 683 | 535 | 21.1% | 7.5% | 1.6% | 1.50x | 17.7% | **1.43x** |
| stage entry: confirmed | tune | 306 | 247 | 23.5% | 10.5% | 2.3% | 1.50x | 14.1% | **2.07x** |
| stage entry: confirmed | holdout | 425 | 368 | 20.9% | 8.7% | 2.8% | 1.36x | 18.4% | **1.68x** |
| stage entry: numeric_plus_insider | tune | 330 | 259 | 17.9% | 7.6% | 2.7% | 1.43x | 17.3% | **1.41x** |
| stage entry: numeric_plus_insider | holdout | 492 | 407 | 21.1% | 7.7% | 1.4% | 1.48x | 15.2% | **1.41x** |
| stage entry: emerging_plus_insider | tune | 47 | 42 | 27.7% | 17.0% | 4.3% | 1.44x | 19.1% | **3.44x** |
| stage entry: emerging_plus_insider | holdout | 65 | 60 | 32.3% | 9.2% | 0.0% | 1.95x | 12.3% | **1.57x** |

Stage thresholds used above (config.yaml): industry excess ≥ 10%, required revenue CAGR for 5x ≤ 60%, Confirmed = 2 quarters.

## Threshold grid (Emerging / Confirmed entries)

Chosen on the tuning window only; holdout shown next to it for honesty.

| Industry excess ≥ | Required CAGR ≤ | Stage | Tune n | Tune ≥5x | Tune lift | Holdout n | Holdout ≥5x | Holdout lift |
|---|---|---|---|---|---|---|---|---|
| 0% | 40% | confirmed | 522 | 6.5% | 1.35x | 730 | 9.2% | 1.77x |
| 0% | 40% | emerging | 752 | 7.0% | 1.44x | 1,122 | 7.1% | 1.38x |
| 0% | 60% | confirmed | 661 | 7.1% | 1.46x | 951 | 7.3% | 1.41x |
| 0% | 60% | emerging | 922 | 7.0% | 1.44x | 1,398 | 5.9% | 1.16x |
| 0% | 80% | confirmed | 708 | 7.1% | 1.46x | 1,061 | 6.9% | 1.36x |
| 0% | 80% | emerging | 993 | 6.8% | 1.40x | 1,538 | 5.8% | 1.13x |
| 0% | no limit | confirmed | 748 | 7.0% | 1.45x | 1,151 | 6.5% | 1.29x |
| 0% | no limit | emerging | 1,042 | 6.8% | 1.41x | 1,643 | 5.5% | 1.07x |
| 5% | 40% | confirmed | 336 | 6.8% | 1.38x | 457 | 11.4% | 2.15x |
| 5% | 40% | emerging | 529 | 7.0% | 1.39x | 727 | 8.9% | 1.72x |
| 5% | 60% | confirmed | 443 | 7.9% | 1.58x | 602 | 8.8% | 1.69x |
| 5% | 60% | emerging | 669 | 7.5% | 1.49x | 935 | 7.1% | 1.36x |
| 5% | 80% | confirmed | 481 | 7.7% | 1.54x | 687 | 8.2% | 1.59x |
| 5% | 80% | emerging | 728 | 7.3% | 1.47x | 1,045 | 6.9% | 1.34x |
| 5% | no limit | confirmed | 520 | 7.5% | 1.53x | 769 | 7.5% | 1.47x |
| 5% | no limit | emerging | 773 | 7.2% | 1.47x | 1,139 | 6.4% | 1.25x |
| 10% | 40% | confirmed | 222 | 9.9% | 2.00x | 317 | 11.7% | 2.20x |
| 10% | 40% | emerging | 368 | 8.4% | 1.71x | 530 | 10.0% | 1.89x |
| 10% | 60% | confirmed | 306 | 10.5% | 2.07x | 425 | 8.7% | 1.68x |
| 10% | 60% | emerging | 488 | 9.0% | 1.82x | 683 | 7.5% | 1.43x |
| 10% | 80% | confirmed | 343 | 9.9% | 1.97x | 499 | 8.2% | 1.61x |
| 10% | 80% | emerging | 535 | 8.8% | 1.77x | 788 | 7.5% | 1.44x |
| 10% | no limit | confirmed | 376 | 9.6% | 1.93x | 580 | 7.4% | 1.45x |
| 10% | no limit | emerging | 581 | 8.6% | 1.76x | 880 | 6.9% | 1.33x |
| 20% | 40% | confirmed | 116 | 9.5% | 1.92x | 167 | 12.6% | 2.35x |
| 20% | 40% | emerging | 219 | 9.1% | 1.88x | 302 | 11.6% | 2.17x |
| 20% | 60% | confirmed | 162 | 9.3% | 1.81x | 232 | 9.5% | 1.82x |
| 20% | 60% | emerging | 292 | 11.0% | 2.18x | 409 | 8.1% | 1.54x |
| 20% | 80% | confirmed | 187 | 8.6% | 1.71x | 284 | 8.8% | 1.72x |
| 20% | 80% | emerging | 331 | 10.6% | 2.13x | 484 | 8.1% | 1.54x |
| 20% | no limit | confirmed | 219 | 7.8% | 1.58x | 352 | 7.7% | 1.49x |
| 20% | no limit | emerging | 371 | 10.2% | 2.12x | 567 | 7.2% | 1.39x |
| 30% | 40% | confirmed | 75 | 8.0% | 1.65x | 96 | 9.4% | 1.75x |
| 30% | 40% | emerging | 146 | 12.3% | 2.51x | 169 | 9.5% | 1.78x |
| 30% | 60% | confirmed | 110 | 8.2% | 1.60x | 128 | 7.0% | 1.33x |
| 30% | 60% | emerging | 199 | 13.6% | 2.61x | 243 | 6.6% | 1.26x |
| 30% | 80% | confirmed | 128 | 7.8% | 1.53x | 163 | 6.7% | 1.30x |
| 30% | 80% | emerging | 234 | 12.0% | 2.36x | 287 | 7.0% | 1.34x |
| 30% | no limit | confirmed | 151 | 7.3% | 1.45x | 214 | 6.1% | 1.16x |
| 30% | no limit | emerging | 268 | 11.2% | 2.27x | 361 | 6.1% | 1.17x |
