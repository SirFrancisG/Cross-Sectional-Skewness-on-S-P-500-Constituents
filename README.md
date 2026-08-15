# Cross-Sectional Skewness on S&P 500 Constituents

A daily-rebalanced, long-only backtest of the "buy the highest realized skewness"
idea, run on a **point-in-time reconstruction** of the S&P 500 universe.

**Result: +0.07 Sharpe against an equal-weight benchmark over 16 years — inside the
noise band.** The strategy produces a higher CAGR, but does so by taking more
volatility. Full numbers and caveats below.

---

## The idea

Rank every index constituent by the skewness of its daily returns over a rolling
60-day window. Hold the 10 with the fattest right tail, equal-weighted, and re-rank
every day. The bet is that positive skewness is **persistent** — that a stock which
just produced a large upside jump is more likely to produce another.

This runs against the "lottery stock" literature (Bali–Cakici–Whitelaw 2011;
Boyer–Mitton–Vorkink 2010), which finds that high idiosyncratic skewness predicts
*lower* future returns, because investors overpay for lottery-like payoffs. Testing
which way it goes on this specific universe and horizon was the point.

---

## Why most public backtests of this idea are wrong

Two problems dominate everything else, and both inflate results in the same direction.

### 1. Survivorship bias

The obvious approach — take today's S&P 500 tickers and pull 16 years of history —
selects on survival. It silently excludes every company that went bankrupt, was
acquired at a discount, or was dropped from the index.

That is not a rounding error. Of the constituents as of 2010-01-01, **only about 293
are still in the index today** — roughly 40% of the universe disappeared over the
sample. The missing names include Kodak, Sears, RadioShack, JCPenney, Yahoo,
Monsanto, and a long tail of energy companies wiped out in 2015–2016.

**What this repo does:** the universe is a reconstruction of index membership as of
2010-01-01, built by taking the current constituent list and walking an index-changes
table backwards in time, reversing each addition and removal. Delisted names are
included and are selectable on any day they have sufficient valid data — a company
delisted in 2016 contributes until 2016 and then disappears, with no look-ahead.

**What it does not fix:** Yahoo Finance no longer carries price history for many
delisted tickers. Of 498 requested symbols, **123 (24.7%) return nothing at all**. The
universe is substantially less biased than a naive one, but not clean. See Limitations.

### 2. Skewness is pathologically sensitive to bad data

Skewness depends on the **cube** of deviations. A single corrupted price — an
unadjusted reverse split, or a recycled ticker where one symbol covers two different
companies across time — produces an astronomical skewness value that goes straight
to the top of the ranking.

This is not background noise. **A skewness-ranking strategy actively seeks out data
errors.** Early runs of this backtest reported a CAGR of 4,540,767% and an
equal-weight benchmark volatility of 3,182% annualized, driven by a handful of
recycled symbols whose series spliced a dead large cap onto an unrelated penny stock.

The filters block the *impossible* while preserving the *extreme*. A +45% single-day
move on a large cap is real and is exactly what the strategy is looking for; a +1,900%
move is not. Concretely: prices below \$1 are dropped, single-day moves beyond ±200%
are masked to NaN rather than clipped (clipping would leave an outlier at the boundary
that still dominates the third moment), and known recycled symbols are blacklisted.

**Built-in sanity check:** the equal-weight benchmark's annualized volatility must
land between 15% and 25%. The script prints a pass/fail line. If it fails, the data
is still corrupted and no other metric should be read.

---

## Methodology

| Component | Choice |
|---|---|
| Universe | 498 S&P 500 constituents as of 2010-01-01 (point-in-time); 123 return no data, 362 usable after blacklist |
| Period | 2010-03-19 → 2026-08-13 (4,178 trading days) |
| Signal | Rolling 60-day skewness of daily returns, minimum 50 valid observations |
| Selection | Top 10, equal-weighted |
| Hysteresis | Enter in top 10, exit only past rank 12 |
| Execution lag | 2 days between last signal observation and trade |
| Costs | 3 bps per side, applied to realized turnover |
| Weight drift | Modelled — positions are not silently re-equalized for free each day |
| Benchmarks | Equal-weight of the same universe (primary), SPY (secondary) |

The equal-weight benchmark matters more than SPY. It carries the *same* residual
survivorship bias as the strategy, so the difference between them isolates the
signal's contribution rather than the universe construction's.

The hysteresis exists because a strict top-10 rule churns on rank noise: a stock
oscillating between 10th and 11th place gets bought and sold repeatedly for no
informational reason. Widening the exit threshold to rank 12 cut annual turnover
from roughly 3,500% to 1,878%.

---

## Results

| | Total | CAGR | Vol | Sharpe | MaxDD |
|---|---|---|---|---|---|
| Strategy, gross | 1,536% | 18.58% | 19.88% | 0.96 | −39.06% |
| **Strategy, net of costs** | 1,392% | **17.91%** | 19.88% | **0.93** | −39.26% |
| Equal-weight universe | 890% | 15.00% | 18.20% | **0.86** | −40.53% |
| SPY buy & hold | 791% | 14.26% | 17.12% | **0.87** | −33.72% |

Sharpe ratios use rf = 0.

- Annual turnover: 1,878% of NAV (buys + sells)
- Annual cost drag at 3 bps/side: 0.56%
- Trading occurs on 28% of days
- **Excess CAGR vs equal-weight: +2.91%**
- **Excess Sharpe vs equal-weight: +0.07**

### Cost sensitivity

| Cost per side | Strategy CAGR | vs equal-weight |
|---|---|---|
| 0 bps | 18.58% | +3.58% |
| 1 bps | 18.35% | +3.36% |
| 3 bps | 17.91% | +2.91% |
| 5 bps | 17.47% | +2.47% |
| 10 bps | 16.37% | +1.37% |

The strategy survives realistic institutional costs. Turnover is high but the edge
does not evaporate until well past 10 bps per side.

---

## Honest reading of these numbers

**The CAGR advantage is mostly leverage, not alpha.** The strategy returns +2.91% more
per year than the equal-weight benchmark, but runs at 19.88% volatility against 18.20%
— about 9% more risk. Risk-adjusted, the advantage shrinks to +0.07 Sharpe.

**+0.07 is inside the noise band.** The standard error of a Sharpe estimate over 16
years is roughly 1/√16 ≈ 0.25 — four times the measured effect. This result is not
statistically distinguishable from zero, in either direction.

**The most that can be claimed** is that high-skewness selection did not *underperform*
on this universe over this period, which is itself mildly interesting given that the
lottery-stock literature predicts underperformance. It is not evidence of a tradeable
edge.

SPY, meanwhile, delivers Sharpe 0.87 with a shallower drawdown (−33.72% vs −39.26%) and
zero turnover. Neither the strategy nor the equal-weight universe clears that bar on a
risk-adjusted basis by any margin worth acting on.

---

### A note on where the tail events come from

After filtering, 182 single-day moves above +25% survive in the sample. The twelve
largest are dominated by a single name: **GameStop accounts for six of them**
(January 2021 and May 2024), with the remainder being Fluor in March 2020, PG&E's
January 2019 bankruptcy bounce, SuperValu's 2018 acquisition, Goodrich in 2010, and
Capri in 2023.

This matters for interpretation. A strategy that ranks on right-tail fatness will
mechanically concentrate in whatever produced the fattest tails, and in this sample
that is disproportionately one meme-stock episode. Whether the measured edge survives
excluding GameStop is a question this configuration does not answer.

---

## What this script does not test

These are the obvious robustness checks, and their absence is a real limitation of the
result above:

- **Sign reversal.** Ranking on the *lowest* skewness instead of the highest. If both
  tails outperform the benchmark, the signal is capturing volatility rather than
  asymmetry. The `ASCENDING` flag flips this, but the comparison is not run or
  reported here.
- **Volatility control.** Selecting the 10 most volatile names, ignoring skewness
  entirely. If that portfolio performs comparably, skewness adds nothing over a simple
  volatility tilt.
- **Subperiod decomposition.** A single full-sample number can average a strong early
  period with weak recent ones. Splitting into 2010–2015 / 2016–2021 / 2022–2026 is the
  minimum needed to distinguish a persistent edge from a decayed or spurious one, and
  is not done here.

Anyone building on this should run all three before drawing conclusions.

---

## Limitations

Read these before citing any number above.

- **Residual survivorship bias.** 123 of 498 reconstructed constituents (24.7%)
  return no data from Yahoo Finance. Delisting returns are absent entirely: a stock
  that goes to zero and one acquired at a premium both simply stop appearing in the
  data, with no terminal return recorded.
- **Incomplete membership reconstruction.** The index-changes source records roughly
  11–19 changes per year against an actual ~20–25. Reconstruction quality degrades
  going backwards and is unusable before ~2007.
- **The blacklist is in-sample.** Excluded symbols were identified by inspecting
  diagnostics on this same data. They are objectively corrupted series (recycled
  tickers covering two different companies), not names selected on performance — but
  the procedure is still a post-hoc decision made after seeing the sample.
- **Multiple testing.** Lookback, top-N, hysteresis thresholds, execution lag and
  filter parameters were all varied during development on this same sample. The
  reported configuration is not an out-of-sample result. Treat the point estimates as
  upper bounds.
- **No borrow costs, no slippage model, no market impact.** Costs are a flat per-side
  rate on notional traded.
- **Close-to-close execution** at the closing price two days after the last signal
  observation.
- **Statistical power.** See above: the headline +0.07 is smaller than the standard
  error of the estimate.

---

## Running it

```bash
pip install yfinance pandas numpy quantstats
python skew_backtest.py
```

The first run downloads ~500 tickers and caches prices to `prices_2010-01-01.pkl`;
subsequent runs start in seconds. Delete the cache file to re-download.

Expect a large number of download failures on the first run — those are the delisted
names, and their absence is the main remaining source of bias.

Output: a console report with the data diagnostics, the metrics table, the sanity
check, and the cost sensitivity grid, plus a `report_skewness.html` tearsheet
(quantstats) benchmarked against SPY.

---

## References

- Bali, Cakici & Whitelaw (2011), *Maxing Out: Stocks as Lotteries and the
  Cross-Section of Expected Returns*, Journal of Financial Economics
- Boyer, Mitton & Vorkink (2010), *Expected Idiosyncratic Skewness*,
  Review of Financial Studies
- Amaya, Christoffersen, Jacobs & Vasquez (2015), *Does Realized Skewness Predict the
  Cross-Section of Equity Returns?*, Journal of Financial Economics

---

## License

MIT. Research code, not investment advice. The result above is a reason to keep
testing, not a reason to trade.
