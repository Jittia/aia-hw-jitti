# Clean ROIC display cap (round 33, 2026-11-05)

Written before the change. Source: round 32 invested-capital study (`output/data/ic_study.json`): 28 companies show
clean ROIC above 100% and 10 above 200% (DUOL 1,588%, PLTR 866%, EXPE 813%), mostly because average invested
capital is close to zero. A guard that blanks ROIC failed its test (it also removed distributors), so this round only
changes how the number is shown.

## Rule

- When clean ROIC (Screener Group 1 Y, Group 4 X) is above **100%**, the page shows **"> 100%"** instead of the number.
  Hovering shows the exact value and why: "Clean ROIC is 1,588.2%: invested capital is small next to after-tax profit.
  Read it as 'very high', not as a precise number." (The amounts are in the Calculation check.)
- Display only. The stored data, every list, rank, median, percentile, sort order and the Moat Score stay exactly as
  they are. The Screener charts already pin outliers at the edge (2nd–98th percentile axes) and are not changed; the
  Deep-Dive mini charts (min–max axes) draw ROIC above the cap just above 100% and label that end "> 100%".
- A change in ROIC (Δ 4 quarters) larger than 100 points is shown as "n.m.".
- The Calculation check keeps the exact value (it is an audit). When ROIC is above 100% a note under the table says
  the same as the hover text.
- Other ratios (return on new capital, Group 2 Y) are not capped in this round.

## Pass rules (checked after the change)

1. Data unchanged: `output/data/site_data.js`, `results.csv`, `deep_data.js`, `audit/*.js` and `output/sheet/*.csv`
   are byte-identical before and after.
2. Every place the page prints clean ROIC as a number goes through one formatter (`froic`); a search finds no other.
3. Sorting the Screener and Watchlist tables by ROIC gives the same order as before (true values used).
4. All tests pass, including the honesty test (page and Python give the same measures).
5. In the browser: DUOL shows "> 100%" with the hover text in the Screener table, the Deep-Dive and the Watchlist;
   a company below 100% shows its exact number as before; no console errors.
