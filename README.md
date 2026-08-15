# Cross-Sectional Skewness on S&P 500 Constituents

A long-only backtest of the "buy the highest realized skewness" idea, run on a
**frozen 2010 S&P 500 constituent cohort reconstructed point-in-time**. The signal is
re-ranked daily; the portfolio rebalances only when the selected set changes.

**Result: evidence of a cross-sectional skewness effect, but no robust evidence of
tradeable alpha.** Over the full 2010–2026 sample the long leg beats an equal-weight
benchmark by +0.07 Sharpe — smaller than the standard error of the estimate. Two
sanity checks are consistent with skewness rather than a volatility proxy driving the
spread, though neither is a formal attribution test. And splitting the sample puts the
entire advantage in 2010–2015: since 2016 the strategy has underperformed the
benchmark on a risk-adjusted basis.

---

## The idea

Rank every name in the cohort by the skewness of its daily returns over a rolling
60-day window. Hold the 10 with the fattest right tail, equal-weighted, and re-rank
every day. The portfolio only trades when the selected set changes — the ranking is
daily, the rebalancing is conditional. The bet is that positive skewness is **persistent** — that a stock which
just produced a large upside jump is more likely to produce another.

The motivation is the arithmetic of compounding. Wealth compounds multiplicatively, so
a single exceptional year permanently rescales everything after it: twenty years at
10% gives 6.7×, but nineteen years at 10% plus one year at 100% gives 12.2×. If
extreme upside is concentrated in a handful of episodes, catching even a few of them
should dominate.

The catch — and this is what the backtest is really testing — is that the +100% year
does not arrive for free. Exposure to the right tail means holding volatile names in
all the other years too. Redo the same arithmetic with the base rate depressed: if
chasing tails costs more than about 3.4 percentage points a year on the other
nineteen, the exceptional year no longer compensates. The question is not whether
tails matter. It is whether they are worth what they cost.

There is an existing academic literature pointing the other way: high idiosyncratic
skewness has been found to predict *lower* future returns, on the theory that
investors overpay for lottery-like payoffs. Those studies use different horizons,
universes, and in some cases intraday data, so none of them settles the question for
the setup here — but they are worth knowing about, and are listed under Further
reading.

---

## Two data problems that dominate this backtest

Before any result is meaningful, two issues have to be dealt with. Both inflate
returns in the same direction, and the second one nearly destroyed an early version of
this project.

### 1. Survivorship bias

The obvious approach — take today's S&P 500 tickers and pull 16 years of history —
selects on survival. It silently excludes every company that went bankrupt, was
acquired at a discount, or was dropped from the index.

That is not a rounding error. Of the constituents as of 2010-01-01, **only about 293
are still in the index today** — roughly 40% of the universe disappeared over the
sample. The missing names include Kodak, Sears, RadioShack, JCPenney, Yahoo,
Monsanto, and a long tail of energy companies wiped out in 2015–2016.

**What this repo does:** the universe is the set of index constituents as of
2010-01-01, reconstructed by taking the current membership list and walking an
index-changes table backwards in time, reversing each addition and removal. Delisted
names are kept and remain selectable on any day they have sufficient valid data — a
company delisted in 2016 contributes until 2016 and then disappears, with no
look-ahead.

**This is a frozen cohort, not a dynamic index.** The membership is fixed at
2010-01-01 and never updated: names added to the S&P 500 after that date are absent
for the whole sample, and names removed stay in the pool until their data runs out.
That is a deliberate simplification, and it means the backtest is not a simulation of
tracking the index. It is a simulation of ranking a fixed 2010 large-cap cohort.

**What it does not fix:** Yahoo Finance no longer carries price history for many
delisted tickers. Of 498 requested symbols, **123 (24.7%) return nothing at all**. The
universe is substantially less biased than a naive one, but not clean. See Limitations.

### 2. Skewness is pathologically sensitive to bad data

Skewness depends on the **cube** of deviations. A single corrupted price — an
unadjusted reverse split, or a recycled ticker where one symbol covers two different
companies across time — produces an astronomical skewness value that goes straight to
the top of the ranking.

This is not background noise. **A skewness-ranking strategy actively seeks out data
errors.** An early run of this backtest reported a CAGR of 4,540,767% and an
equal-weight benchmark volatility of 3,182% annualized, driven by a handful of
recycled symbols whose series spliced a dead large cap onto an unrelated penny stock.

The filters block the *impossible* while preserving the *extreme*. A +45% single-day
move on a large cap is real and is exactly what the strategy is looking for; a +1,900%
move is not. Concretely: prices below \$1 are dropped, single-day moves beyond ±200%
are masked to NaN rather than clipped (clipping would leave an outlier sitting at the
boundary, still dominating the third moment), and known recycled symbols are
blacklisted.

**Built-in sanity check:** the equal-weight benchmark's annualized volatility must
land between 15% and 25%. The script prints a pass/fail line. If it fails, the data is
still corrupted and no other metric should be read.

---

## Methodology

| Component | Choice |
|---|---|
| Universe | Frozen cohort of 497 S&P 500 constituents as of 2010-01-01, reconstructed point-in-time; ~123 return no data, ~362 usable after blacklist |
| Period | 2010-03-19 → 2026-08-13 (4,178 trading days) |
| Signal | Rolling 60-day skewness of daily returns, minimum 50 valid observations |
| Selection | Top 10, equal-weighted |
| Hysteresis | Enter in top 10, exit only past rank 12 |
| Execution lag | 2 days between last signal observation and trade |
| Costs | 3 bps per side, applied to realized turnover |
| Weight drift | Modelled — positions are not silently re-equalized for free each day |
| Rebalancing | Conditional: only when the selected set changes |
| Missing returns | A name with no valid return for the day cannot be held; the position is force-exited at the last observed close |
| Benchmarks | Equal-weight of the same universe (primary), SPY (secondary) |

The equal-weight benchmark matters more than SPY. It carries the *same* residual
survivorship bias as the strategy, so the difference between them isolates the
signal's contribution rather than the universe construction's.

The hysteresis exists because a strict top-10 rule churns on rank noise: a stock
oscillating between 10th and 11th place gets bought and sold repeatedly for no
informational reason. Widening the exit threshold to rank 12 cut annual turnover from
roughly 3,500% to 1,878%.

---

## Results

Every figure below comes from a single run of `skew_backtest.py`. All three legs are
evaluated on identical data in one pass, so the comparison is exact.

| Strategy | CAGR | Vol | Sharpe | MaxDD | Turnover | ΔSharpe vs EW |
|---|---|---|---|---|---|---|
| **High skewness** (thesis) | 17.90% | 19.88% | **0.93** | −39.26% | 1,878% | **+0.07** |
| Low skewness (check) | 9.32% | 20.32% | 0.54 | −50.49% | 1,931% | −0.32 |
| High volatility (check) | 23.52% | 40.34% | 0.72 | −67.37% | 1,198% | −0.14 |
| Equal-weight cohort | 15.00% | 18.20% | 0.86 | −40.53% | — | — |
| SPY buy & hold | 14.26% | 17.12% | 0.87 | −33.72% | — | — |

Sharpe ratios use rf = 0. Costs are 3 bps per side on realized turnover; the annual
drag on the thesis leg is 0.56%, and it trades on 28% of days.

### Cost sensitivity

| Cost per side | High-skew CAGR | vs equal-weight |
|---|---|---|
| 0 bps | 18.57% | +3.57% |
| 1 bps | 18.35% | +3.35% |
| 3 bps | 17.90% | +2.90% |
| 5 bps | 17.46% | +2.46% |
| 10 bps | 16.36% | +1.36% |

Turnover is high but the edge does not evaporate until well past 10 bps per side.

### Where the tail events actually come from

Nothing was filtered out for being too large — moves up to ±200% pass through
untouched, well above anything a real large cap does in a day. After filtering,
**182 single-day moves above +25% remain in the sample.**

What's striking is how concentrated they are. Of the twelve largest, **six are
GameStop** (the January 2021 squeeze, plus May 2024). The rest: Fluor in March 2020,
PG&E's January 2019 bankruptcy bounce, SuperValu's 2018 acquisition, Goodrich in 2010,
Capri in 2023.

That concentration is the thesis in miniature. Extreme upside is rare and lumpy — a
handful of episodes across sixteen years and 362 names. A strategy built to catch them
inevitably ends up holding whatever produced them.

Position sizing dampens this considerably. With ten equal-weighted names, GameStop's
+134.8% on 2021-01-27 contributed roughly **+13.5% at the portfolio level**, not
+134.8% — and its −60% a week later cost about −6%. That is why the maximum drawdown
is −39% rather than something catastrophic, but it is also why a single spectacular
event does not transform the track record.

---

## What the control legs tell us

**Both sanity checks come out in the expected direction.**

Ranking on the *lowest* skewness produces a materially worse portfolio — Sharpe 0.54
against 0.93, with a drawdown eleven points deeper. The spread between the two tails
is wide, and on this cohort it runs in the direction the thesis predicts rather than
the one the lottery-stock literature would suggest. If the ranking were merely sorting
on volatility, both extremes would look similar; they do not.

Ranking on raw volatility, ignoring skewness entirely, delivers the highest CAGR in
the table — 23.52% — but at 40% volatility and a −67% drawdown. Risk-adjusted it lands
below the equal-weight benchmark.

**What these do and do not establish.** They are sanity checks, not an attribution.
They rule out the crudest alternative explanation — that the sort is a disguised
volatility tilt — and they show the two tails behave differently. They do not
establish that skewness is the *driver*. Doing that properly requires cross-sectional
regressions with controls for size, value, momentum, beta and idiosyncratic
volatility, which this repo does not run. Read the spread as suggestive, not as
identification.

### Subperiods

| Period | High skew | Low skew | High vol | Equal-weight | ΔSharpe (high skew) |
|---|---|---|---|---|---|
| 2010–2015 | 21.24% / Sh 1.17 | 5.38% / Sh 0.39 | −2.82% / Sh 0.06 | 13.86% / Sh 0.84 | **+0.33** |
| 2016–2021 | 19.05% / Sh 0.90 | 14.31% / Sh 0.69 | 62.64% / Sh 1.27 | 18.62% / Sh 0.94 | **−0.04** |
| 2022–2026 | 12.49% / Sh 0.70 | 8.05% / Sh 0.49 | 16.84% / Sh 0.58 | 11.89% / Sh 0.76 | **−0.06** |

This is where the full-sample number falls apart. **The entire edge sits in
2010–2015.** Across both later subperiods the strategy underperforms the equal-weight
benchmark on a risk-adjusted basis. The headline +0.07 is an average of one strong
early stretch and two weak recent ones, and reported alone it hides the only thing
worth knowing.

The low-skewness leg, by contrast, underperforms consistently in all three
subperiods — making it the most stable finding in the whole exercise.

---

## Honest reading

**Something is there.** The gap between the high- and low-skewness legs is large and
consistent, and it survives the volatility check. Whether realized skewness is the
cause, or a proxy for something correlated with it, this design cannot say.

**It is not currently tradeable.** Over the last decade the long leg has not beaten a
naive equal-weight portfolio of the same universe. Whatever the effect was worth, it
was worth it before 2016.

**Even the full-sample figure is inside the noise band.** The standard error of a
Sharpe estimate over 16 years is roughly 1/√16 ≈ 0.25 — nearly four times the measured
+0.07. Taken alone, that number is not statistically distinguishable from zero.

**And the CAGR advantage is partly leverage.** The strategy returns +2.90% more per
year than the benchmark, but runs at 19.88% volatility against 18.20%. Roughly a third
of the excess return is compensation for extra risk rather than skill.

Three readings are consistent with the evidence, and this backtest cannot separate
them: the anomaly was real and decayed as it became known; it never existed and
2010–2015 is noise, in the stretch where data quality is also weakest; or it exists
but is too small to survive turnover of 1,878% a year.

The negative finding is the more robust one. Low-skewness stocks underperform in every
subperiod, which makes that leg the more defensible thing to build on — as an
exclusion filter, or as the short side of a spread.

---

## Repository contents

```
skew_backtest.py   Everything: universe, signal, cost model, three legs,
                   data diagnostics and subperiod decomposition
README.md          This file
LICENSE            MIT
```

One file, no dependencies between files. Copy it and run it.

---

## Limitations

Read these before citing any number above.

- **Residual survivorship bias.** 123 of 497 reconstructed constituents (24.7%) return
  no data from Yahoo Finance. Delisting returns are absent entirely: a stock that goes
  to zero and one acquired at a premium both simply stop appearing in the data, with
  no terminal return recorded.
- **Incomplete membership reconstruction.** The index-changes source records roughly
  11–19 changes per year against an actual ~20–25. Reconstruction quality degrades
  going backwards and is unusable before ~2007.
- **The reconstruction has at least one known defect.** An earlier version of the
  cohort wrongly included Meta/Facebook, which did not go public until May 2012 and
  joined the index in December 2013. It has been removed. The walk-back reverses index
  additions and removals but does not reverse ticker renames, and every rename is a
  place where a similar error could hide. Others may remain.
- **No delisting returns.** When a holding's data ends, the position is exited at the
  last observed close. A bankruptcy and a takeover at a premium are therefore
  indistinguishable, and the terminal loss on a failure is never taken. The script
  counts how often this guard fires: **1 name-day on the high-skew leg, 14 on
  low-skew, 68 on high-volatility** over 4,178 trading days. The exposure is
  negligible for the thesis leg and concentrated, as one would expect, in the leg
  that holds the most fragile names — but the guard exists because without it those
  positions would have been silently marked flat.
- **Sanity checks are not attribution.** The high/low skew spread and the volatility
  control rule out the crudest alternative explanation, but establishing skewness as
  the driver would require cross-sectional regressions with standard factor controls,
  which are not run here.
- **The blacklist is in-sample.** Excluded symbols were identified by inspecting
  diagnostics on this same data. They are objectively corrupted series (recycled
  tickers covering two different companies), not names selected on performance — but
  the procedure is still a post-hoc decision made after seeing the sample.
- **Multiple testing.** Lookback, top-N, hysteresis thresholds, execution lag and
  filter parameters were all varied during development on this same sample. The
  reported configuration is not an out-of-sample result. Treat the point estimates as
  upper bounds.
- **Subperiod boundaries are arbitrary.** The three splits were chosen for readability,
  not derived from a structural-break test.
- **No borrow costs, no slippage model, no market impact.** Costs are a flat per-side
  rate on notional traded. The long-short extension suggested above would need borrow
  costs modelled before it meant anything.
- **Close-to-close execution** at the closing price two days after the last signal
  observation.
- **Statistical power.** The standard error of a Sharpe estimate on this sample is
  roughly 0.25. Differences smaller than that are not distinguishable from chance,
  including the headline +0.07.

---

## Further reading

Academic work on skewness and lottery-like payoffs in the cross-section. These did not
guide the design of this backtest, but they cover neighbouring territory and reach
conclusions worth weighing against the results above. Each uses a different horizon
and construction, so none maps directly onto the setup here.

- Bali, Cakici & Whitelaw (2011), *Maxing Out: Stocks as Lotteries and the
  Cross-Section of Expected Returns*, Journal of Financial Economics — finds that
  stocks with the highest maximum daily return in a month underperform in the
  following month. The closest of the three to this setup.
- Boyer, Mitton & Vorkink (2010), *Expected Idiosyncratic Skewness*, Review of
  Financial Studies — models expected idiosyncratic skewness and finds it negatively
  related to subsequent returns.
- Amaya, Christoffersen, Jacobs & Vasquez (2015), *Does Realized Skewness Predict the
  Cross-Section of Equity Returns?*, Journal of Financial Economics — uses intraday
  data at a weekly horizon, so the least comparable of the three.

---

## Disclaimer

**This is not investment advice, financial advice, trading advice, or a recommendation
of any kind.**

This repository contains exploratory research code published for educational and
illustrative purposes only. Nothing in it constitutes an offer, solicitation, or
recommendation to buy or sell any security or financial instrument, nor a
recommendation to adopt any investment strategy. The author is not a licensed
financial advisor, broker-dealer, or investment professional, and no advisory
relationship is created by reading, using, or forking this repository.

Backtested results are hypothetical. They do not represent actual trading, no real
capital was ever at risk, and they are subject to survivorship bias, data errors,
in-sample parameter selection, and simplified cost and execution assumptions — all
documented in the Limitations section above, which should be read before drawing any
conclusion from the figures. **Hypothetical performance has inherent limitations and
is no indication of future results.** Past performance does not predict future returns.

The market data used here comes from a free third-party source, is provided without
warranty of accuracy or completeness, and is demonstrably incomplete for delisted
securities. The code may contain errors. Anyone using it does so entirely at their own
risk, and is solely responsible for any decisions taken and any losses incurred. The
author accepts no liability whatsoever for any direct, indirect, incidental, or
consequential loss arising from the use of this material.

Consult a qualified, licensed financial professional before making any investment
decision.

---

## License

Released under the MIT License — see [LICENSE](LICENSE).
