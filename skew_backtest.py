"""
Cross-sectional skewness on a frozen S&P 500 cohort.

Long-only, equal-weight backtest over 2010-2026. The signal is re-ranked EVERY
DAY, but the portfolio is only rebalanced when the selected set changes (see
REBALANCE_ONLY_ON_CHANGE) -- so this is daily signal evaluation with conditional
rebalancing, not daily rebalancing.

UNIVERSE: a FROZEN COHORT of the S&P 500 constituents as of 2010-01-01,
reconstructed point-in-time. This is NOT a dynamic day-by-day index membership:
companies that joined the index after 2010 are absent throughout, and companies
that left remain selectable until their data ends. The reconstruction removes
look-ahead in the choice of the starting cohort; it does not track the index.

THESIS
------
Hold the TOP_N stocks with the fattest right tail over the last LOOKBACK days,
betting that positive realized skewness is persistent.

THIS SCRIPT RUNS THREE LEGS IN A SINGLE PASS
--------------------------------------------
  1. HIGH SKEW  the thesis: buy the fattest right tail
  2. LOW SKEW   control: the lottery-stock literature (Bali-Cakici-Whitelaw,
                Boyer-Mitton-Vorkink) predicts this leg should do BETTER,
                because investors overpay for lottery-like payoffs
  3. HIGH VOL   the decisive control: buy the 10 most volatile names, ignoring
                skewness entirely

HOW TO READ THE OUTPUT
  - only leg 1 beats equal-weight        -> the skewness signal is real
  - legs 1 AND 2 both beat equal-weight  -> you are capturing volatility, not
                                            asymmetry: both ends of the ranking
                                            are simply volatile names
  - leg 3 matches or beats leg 1         -> skewness adds nothing over a plain
                                            volatility tilt

AND IT DECOMPOSES BY SUBPERIOD
  A genuine edge shows up across all subperiods, possibly with varying strength.
  An artefact of selection concentrates in one.

DATA HYGIENE
------------
Skewness depends on the CUBE of deviations, making it the most outlier-sensitive
statistic in common use. A single corrupted price (an unadjusted reverse split, a
recycled ticker) produces an astronomical value that goes straight to the top of
the ranking. Without the filters below, this strategy does not merely tolerate bad
data -- it actively seeks it out.

The filters block the IMPOSSIBLE while preserving the EXTREME. A +45% single-day
move on a large cap is a real event and is exactly what the strategy hunts for;
a +1900% move never happened and nobody collected it.

SANITY CHECK: after filtering, the equal-weight universe volatility must land
between 15% and 25%. Above that, corrupted data remains and no metric is readable.
"""

import warnings
import logging

warnings.filterwarnings("ignore")
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)

# --- quantstats / pandas < 2.2 compatibility (the 'ME', 'QE', 'YE' aliases) ---
import pandas as pd
import pandas.core.resample as _rs

if tuple(int(x) for x in pd.__version__.split(".")[:2]) < (2, 2):
    _ALIAS = {"ME": "M", "QE": "Q", "YE": "A", "BME": "BM", "SME": "SM"}
    _orig_to_offset = _rs.to_offset

    def _patched_to_offset(freq, *a, **k):
        if isinstance(freq, str):
            freq = _ALIAS.get(freq, freq)
        return _orig_to_offset(freq, *a, **k)

    _rs.to_offset = _patched_to_offset
# -----------------------------------------------------------------------------

import webbrowser
from pathlib import Path

import numpy as np
import yfinance as yf
import quantstats as qs


# ── Parameters ───────────────────────────────────────────────────────────────
START    = "2010-01-01"
END      = None      # None = through the latest available date
LOOKBACK = 60        # signal window, in trading days
MIN_OBS  = 50        # minimum valid observations required inside the window
TOP_N    = 10
FEE      = 0.0003    # 3 bps per side
EXEC_LAG = 2         # days between the last signal observation and the trade

# Hysteresis: enter if ranked within ENTRY_N, exit only past EXIT_N.
# EXIT_N == ENTRY_N disables it (strict top-N rule).
# A strict rule churns on rank noise: a name oscillating between 10th and 11th
# place gets bought and sold repeatedly for no informational reason.
ENTRY_N, EXIT_N = 10, 12

REBALANCE_ONLY_ON_CHANGE = True   # don't re-equalize weights when the basket is
                                  # unchanged; let them drift instead

REPORT_ON = "HIGH SKEW"           # which leg goes into the HTML tearsheet

SUBPERIODS = [("2010", "2015"), ("2016", "2021"), ("2022", "2026")]

# Single-name exclusion, for the "how much rides on one event?" test.
# Set to ["GME"] to check whether the edge is just the January 2021 squeeze.
EXCLUDE_EXTRA = []

# --- Filters: block the impossible, preserve the extreme ---
MIN_PRICE = 1.00     # below $1, percentage returns are tick noise
MAX_DAILY = 2.00     # +-200% in one day is a data error, not a market move
MAX_BAD   = None     # None = never drop a whole ticker, only mask individual
                     # impossible values. Set an integer to re-enable dropping.

# Recycled tickers: the same symbol covers two different companies over time,
# so the series splices a dead large cap onto an unrelated successor.
BLACKLIST = ["TIE", "BMC", "CPWR", "MEE", "SLE", "EP", "PTV", "STI", "MI",
             "POM", "TE", "PBI", "LUMN"]

USE_CACHE = True     # cache prices to disk; later runs start in seconds


# S&P 500 constituents as of 2010-01-01, reconstructed point-in-time by walking
# the index-changes table backwards from the current membership list.
# Delisted names are included on purpose -- excluding them is survivorship bias.
UNIVERSE = [
    "A", "AA", "AAPL", "ABT", "ACE", "ADBE", "ADI", "ADM", "ADP",
    "ADSK", "AEE", "AEP", "AES", "AET", "AFL", "AGN", "AIG", "AIV",
    "AIZ", "AKAM", "ALL", "ALTR", "AMAT", "AMD", "AMGN", "AMP", "AMT",
    "AMZN", "AN", "ANDV", "ANF", "AON", "APA", "APC", "APD", "APH",
    "APOL", "APTV", "ARG", "ATI", "AVB", "AVP", "AVY", "AXP", "AYE",
    "AZO", "BA", "BAC", "BALL", "BAX", "BBBY", "BBWI", "BBY", "BCR",
    "BDX", "BEAM", "BEN", "BF-B", "BHI", "BIG", "BIIB", "BJS", "BKNG",
    "BMC", "BMY", "BNY", "BRCM", "BRK-B", "BSX", "BTU", "BXP", "C",
    "CA", "CAG", "CAH", "CAM", "CAT", "CBRE", "CCE", "CCL", "CEG",
    "CELG", "CEPH", "CF", "CFN", "CHK", "CHRW", "CI", "CINF", "CL",
    "CLF", "CLX", "CMA", "CMCSA", "CME", "CMI", "CMS", "CNP", "CNX",
    "COF", "COL", "COP", "COR", "COST", "CPAY", "CPB", "CPRI", "CPWR",
    "CRM", "CSC", "CSCO", "CSX", "CTAS", "CTRA", "CTSH", "CTXS", "CVH",
    "CVS", "CVX", "D", "DAY", "DE", "DELL", "DF", "DFS", "DGX",
    "DHI", "DHR", "DIS", "DISCA", "DNB", "DNR", "DO", "DOC", "DOV",
    "DPS", "DRI", "DTE", "DTV", "DUK", "DV", "DVA", "DVN", "EA",
    "EBAY", "ECL", "ED", "EFX", "EG", "EIX", "EK", "EL", "ELV",
    "EMC", "EMN", "EMR", "EOG", "EP", "EQR", "ES", "ESRX", "ETFC",
    "ETN", "ETR", "EXC", "EXPD", "EXPE", "F", "FAST", "FCX",
    "FDO", "FDX", "FE", "FHN", "FII", "FIS", "FISV", "FITB", "FLIR",
    "FLR", "FLS", "FMC", "FRX", "FSLR", "FTI", "FTR", "GD", "GE",
    "GEN", "GENZ", "GHC", "GILD", "GIS", "GL", "GLW", "GME", "GNW",
    "GOOG", "GPC", "GPS", "GR", "GS", "GT", "GWW", "HAL", "HAR",
    "HAS", "HBAN", "HCBK", "HD", "HES", "HIG", "HNZ", "HOG", "HON",
    "HOT", "HPQ", "HRB", "HRL", "HSP", "HST", "HSY", "HUM", "IBM",
    "ICE", "IFF", "IGT", "INTC", "INTU", "IP", "IPG", "IQV", "IRM",
    "ISRG", "ITT", "ITW", "IVZ", "J", "JBL", "JCI", "JCP", "JDSU",
    "JEF", "JNJ", "JNPR", "JNS", "JOY", "JPM", "JWN", "K", "KEY",
    "KFT", "KG", "KIM", "KLAC", "KMB", "KO", "KR", "KSS", "L",
    "LEG", "LEN", "LH", "LHX", "LIFE", "LIN", "LLL", "LLTC", "LLY",
    "LM", "LMT", "LNC", "LO", "LOW", "LSI", "LUMN", "LUV", "LXK",
    "M", "MA", "MAR", "MAS", "MAT", "MCD", "MCHP", "MCK", "MCO",
    "MDP", "MDT", "MEE", "MET", "MFE", "MHS", "MI", "MIL", "MJN",
    "MKC", "MMM", "MO", "MOLX", "MON", "MRK", "MRO", "MRSH", "MS",
    "MSFT", "MSI", "MTB", "MU", "MUR", "MWW", "NBL", "NBR", "NDAQ",
    "NE", "NEE", "NEM", "NI", "NKE", "NOC", "NOV", "NOVL", "NRG",
    "NSC", "NSM", "NTAP", "NTRS", "NUE", "NVDA", "NVLS", "NWL", "NYT",
    "NYX", "ODP", "OI", "OKE", "OMC", "ORCL", "ORLY", "OXY", "PAYX",
    "PBCT", "PBI", "PCAR", "PCG", "PCL", "PCP", "PDCO", "PEG", "PEP",
    "PFE", "PFG", "PG", "PGN", "PGR", "PH", "PHM", "PLD", "PLL",
    "PM", "PNC", "PNW", "POM", "PPG", "PPL", "PRU", "PSA",
    "PTV", "PWR", "PXD", "QCOM", "R", "RAI", "RDC", "RF", "RHI",
    "RHT", "RL", "ROK", "ROP", "ROST", "RRC", "RRD", "RSG", "RSH",
    "RTN", "RTX", "RVTY", "RX", "S", "SAI", "SBUX", "SCG", "SCHW",
    "SE", "SEE", "SHLD", "SHW", "SIAL", "SII", "SJM", "SLB", "SLE",
    "SLM", "SNA", "SNI", "SO", "SPG", "SPGI", "SPLS", "SRCL", "SRE",
    "STI", "STJ", "STR", "STT", "STZ", "SUN", "SVU", "SW", "SWK",
    "SWN", "SWY", "SYK", "SYY", "T", "TAP", "TDC", "TE", "TEG",
    "TFC", "TGNA", "TGT", "THC", "TIE", "TIF", "TJX", "TLAB", "TMO",
    "TPR", "TROW", "TRV", "TSN", "TSS", "TT", "TWC", "TWX", "TXN",
    "TXT", "UAA", "UNH", "UNM", "UNP", "UPS", "URBN", "USB", "V",
    "VAR", "VFC", "VIAB", "VLO", "VMC", "VNO", "VRSN", "VTR", "VTRS",
    "VZ", "WAT", "WBA", "WDC", "WEC", "WELL", "WFC", "WFM", "WFR",
    "WHR", "WIN", "WM", "WMB", "WMT", "WTW", "WU", "WY", "WYN",
    "WYNN", "X", "XEL", "XL", "XLNX", "XOM", "XRAY", "XRX", "XTO",
    "YHOO", "YUM", "ZBH", "ZION",
]
UNIVERSE = list(dict.fromkeys(UNIVERSE))


# ── 1. Download ──────────────────────────────────────────────────────────────
print(f"Tickers requested: {len(UNIVERSE)}")

CACHE = Path(f"prices_{START}.pkl")          # pickle: no extra dependency
if USE_CACHE and CACHE.exists():
    prices = pd.read_pickle(CACHE)
    print(f"Prices read from cache: {CACHE}  (delete it to re-download)")
else:
    print("Downloading...")
    raw = yf.download(UNIVERSE + ["SPY"], start=START, end=END,
                      auto_adjust=True, progress=True, group_by="column")
    prices = raw["Close"].sort_index()
    if USE_CACHE:
        prices.to_pickle(CACHE)

if "SPY" not in prices.columns:
    raise RuntimeError("SPY not downloaded: cannot build the benchmark.")

# Drop only fully empty columns. No filter on the share of missing values --
# that would be look-ahead: using the future to decide what was investable
# in the past.
empty  = prices.columns[prices.notna().sum() == 0]
prices = prices.drop(columns=empty)
print(f"Tickers with no data: {len(empty)}   |   with data: {prices.shape[1] - 1}")

spy_px = prices["SPY"]
px     = prices.drop(columns=["SPY"])

kill = [t for t in list(BLACKLIST) + list(EXCLUDE_EXTRA) if t in px.columns]
if kill:
    print(f"Removed via blacklist/exclusions ({len(kill)}): {sorted(kill)}")
    px = px.drop(columns=kill)


# ── 2. Returns and filters ───────────────────────────────────────────────────
px      = px.where(px >= MIN_PRICE)
returns = px.pct_change(fill_method=None)       # gaps stay NaN instead of being
spy_ret = spy_px.pct_change(fill_method=None)   # forward-filled into a fake jump

bad = returns.abs() > MAX_DAILY
if MAX_BAD is not None:
    d = list(bad.sum()[bad.sum() > MAX_BAD].index)
    if d:
        print(f"Dropped for persistent bad data ({len(d)}): {sorted(d)}")
        returns, px = returns.drop(columns=d), px.drop(columns=d)

# mask, not clip: clipping would leave an outlier sitting at the boundary,
# and that outlier would still dominate the third moment.
returns = returns.mask(bad)

# Surviving tail events -- this is what the strategy actually feeds on.
big = returns.stack()
big = big[big > 0.25].sort_values(ascending=False)
print(f"\nMoves above +25% surviving the filters: {len(big)}.  The 10 largest:")
for (d, tk), val in big.head(10).items():
    print(f"    {tk:<7} {d.date()}   {val*100:>+7.1f}%")
print(f"Final tickers: {returns.shape[1]}   |   days: {len(returns)}")


# ── 3. Signals ───────────────────────────────────────────────────────────────
skew = returns.rolling(LOOKBACK, min_periods=MIN_OBS).skew().where(px.notna())
vol  = returns.rolling(LOOKBACK, min_periods=MIN_OBS).std().where(px.notna())

SIGNALS = {
    "HIGH SKEW": skew.rank(axis=1, ascending=False, method="first"),
    "LOW SKEW":  skew.rank(axis=1, ascending=True,  method="first"),
    "HIGH VOL":  vol.rank(axis=1,  ascending=False, method="first"),
}


# ── 4. Backtest engine ───────────────────────────────────────────────────────
def build_weights(rank):
    """Equal-weight target on the top ENTRY_N names, with hysteresis to EXIT_N."""
    if EXIT_N > ENTRY_N:
        ra   = rank.fillna(np.inf).to_numpy()
        sel  = np.zeros(ra.shape, dtype=bool)
        hold = np.zeros(ra.shape[1], dtype=bool)
        for t in range(ra.shape[0]):
            hold = hold & (ra[t] <= EXIT_N)      # keep until it slips past EXIT_N
            need = ENTRY_N - hold.sum()
            if need > 0:                         # refill the freed slots
                cand = np.where(~hold & np.isfinite(ra[t]))[0]
                if len(cand):
                    hold[cand[np.argsort(ra[t][cand])[:need]]] = True
            sel[t] = hold
        picked = pd.DataFrame(sel, index=rank.index, columns=rank.columns)
    else:
        picked = (rank <= ENTRY_N) & rank.notna()

    w = picked.astype(float)
    w = w.div(w.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    return w.shift(EXEC_LAG).fillna(0.0)


def simulate(rank):
    """Return (gross returns, net returns, turnover, forced-exit count).

    A position is never carried on a name that has no valid return for the day.
    Without this guard, returns.fillna(0.0) would silently treat a delisted or
    data-gapped holding as flat cash -- a systematic bias in the favourable
    direction, since the terminal loss is never taken. Masking the weights
    instead means the zero-fill can never touch an open position, and the
    set-change test below forces a liquidation on the same bar.

    Caveat that no amount of code can fix here: the exit is priced at the last
    observed close. True delisting returns are not in the data source, so a
    bankruptcy and a takeover at a premium still look identical.
    """
    W = build_weights(rank).to_numpy()
    R = returns.fillna(0.0).to_numpy()
    V = returns.notna().to_numpy()      # a tradeable return exists
    n_days, n_assets = R.shape

    gross  = np.zeros(n_days)
    cost   = np.zeros(n_days)
    turn   = np.zeros(n_days)
    held   = np.zeros(n_assets)     # weights actually held, after drift
    first  = None
    forced = 0                      # name-days dropped for missing returns

    for t in range(n_days):
        w_t = W[t] * V[t]           # cannot hold what does not trade today
        dropped = int(((W[t] > 0) & ~V[t]).sum())
        if dropped:
            forced += dropped
        s_t = w_t.sum()
        if s_t > 0:
            w_t = w_t / s_t         # renormalize across the survivors

        if w_t.sum() <= 0:
            if held.sum() > 0:                   # liquidate everything
                turn[t] = np.abs(held).sum()
                cost[t] = FEE * turn[t]
                held    = np.zeros(n_assets)
            continue
        if first is None:
            first = t

        same = (REBALANCE_ONLY_ON_CHANGE and held.sum() > 0
                and np.array_equal(w_t > 0, held > 0))
        w = held.copy() if same else w_t         # basket unchanged -> no trade

        turn[t]  = np.abs(w - held).sum()        # sold + bought
        cost[t]  = FEE * turn[t]
        gross[t] = float(w @ R[t])

        grown = w * (1.0 + R[t])                 # let weights drift with returns
        s     = grown.sum()
        held  = grown / s if s > 0 else np.zeros(n_assets)

    if first is None:
        raise RuntimeError("No day invested: check LOOKBACK / MIN_OBS.")

    ix = returns.index[first:]
    return (pd.Series(gross[first:], index=ix),
            pd.Series(gross[first:] - cost[first:], index=ix),
            pd.Series(turn[first:], index=ix),
            forced)


def stats(r):
    r = r.dropna()
    if len(r) < 2:
        return dict(cagr=np.nan, vol=np.nan, sharpe=np.nan, dd=np.nan, tot=np.nan)
    eq  = (1 + r).cumprod()
    yrs = (r.index[-1] - r.index[0]).days / 365.25
    v   = r.std() * np.sqrt(252)
    return dict(tot=eq.iloc[-1] - 1,
                cagr=eq.iloc[-1] ** (1 / yrs) - 1,
                vol=v,
                sharpe=(r.mean() * 252) / v if v > 0 else np.nan,   # rf = 0
                dd=((eq - eq.cummax()) / eq.cummax()).min())


# ── 5. Run the three legs ────────────────────────────────────────────────────
print("\nSimulating the three legs...")
results = {}
for name, rk in SIGNALS.items():
    g, n, tv, forced = simulate(rk)
    results[name] = dict(gross=g, net=n, turn=tv, forced=forced)
    note = f"  ({forced} name-days force-exited for missing returns)" if forced else ""
    print(f"  {name} done{note}")

idx = results[REPORT_ON]["net"].index

# Equal-weight of the same universe carries the SAME residual survivorship bias
# as the strategies, so the gap between them isolates the signal's contribution
# rather than the universe construction's. Read this before SPY.
eqw = returns.mean(axis=1).reindex(idx).fillna(0.0); eqw.name = "Equal-Weight"
spy = spy_ret.reindex(idx).fillna(0.0);              spy.name = "SPY"

years   = (idx[-1] - idx[0]).days / 365.25
s_eqw   = stats(eqw)
sh_base = s_eqw["sharpe"]


# ── 6. Main table ────────────────────────────────────────────────────────────
print("\n" + "=" * 104)
print(f"  {idx[0].date()} -> {idx[-1].date()}  |  lookback {LOOKBACK}d  |  "
      f"hysteresis {ENTRY_N}/{EXIT_N}  |  lag {EXEC_LAG}d  |  fee {FEE*1e4:.0f} bps")
if EXCLUDE_EXTRA:
    print(f"  EXCLUDED FROM UNIVERSE: {EXCLUDE_EXTRA}")
print("=" * 104)
print(f"  {'Strategy':<22} {'CAGR':>8} {'Vol':>8} {'Sharpe':>8} {'MaxDD':>9} "
      f"{'Turnover':>10} {'dSharpe vs EW':>15}")
print("-" * 104)

for name in SIGNALS:
    r  = results[name]
    s  = stats(r["net"].reindex(idx))
    to = r["turn"].reindex(idx).sum() / years
    print(f"  {name:<22} {s['cagr']*100:>7.2f}% {s['vol']*100:>7.2f}% "
          f"{s['sharpe']:>8.2f} {s['dd']*100:>8.2f}% {to*100:>9,.0f}% "
          f"{s['sharpe']-sh_base:>+15.2f}")

print("-" * 104)
for r, name in ((eqw, "Equal-Weight Universe"), (spy, "SPY Buy & Hold")):
    s = stats(r)
    print(f"  {name:<22} {s['cagr']*100:>7.2f}% {s['vol']*100:>7.2f}% "
          f"{s['sharpe']:>8.2f} {s['dd']*100:>8.2f}% {'-':>10} {'-':>15}")

# --- Data quality gate ---
if 0.15 <= s_eqw["vol"] <= 0.25:
    print(f"\n  [OK]  Equal-weight vol {s_eqw['vol']*100:.1f}% -- data is clean.")
else:
    print(f"\n  [!!]  Equal-weight vol {s_eqw['vol']*100:.1f}% -- outside the "
          f"15-25% range.")
    print("        Corrupted data remains: add the culprits to BLACKLIST and rerun.")


# ── 7. Automatic verdict ─────────────────────────────────────────────────────
d_hi  = stats(results["HIGH SKEW"]["net"].reindex(idx))["sharpe"] - sh_base
d_lo  = stats(results["LOW SKEW"]["net"].reindex(idx))["sharpe"]  - sh_base
d_vol = stats(results["HIGH VOL"]["net"].reindex(idx))["sharpe"]  - sh_base

print("\n" + "-" * 104)
print("  VERDICT")
print("-" * 104)
if d_hi > 0 and d_lo <= 0 and d_hi > d_vol:
    print("  Only the HIGH SKEW leg beats equal-weight, and it beats the")
    print("  volatility control too: the skewness signal appears to be real.")
elif d_lo > d_hi:
    print("  LOW SKEW beats HIGH SKEW: consistent with the lottery-stock")
    print("  literature, where high idiosyncratic skewness predicts LOWER")
    print("  future returns. The signal is there, but the bet is backwards.")
elif d_hi > 0 and d_lo > 0:
    print("  BOTH extremes beat equal-weight: you are capturing volatility,")
    print("  not skewness. Compare against the HIGH VOL leg.")
elif d_vol >= d_hi:
    print("  The HIGH VOL control matches or beats HIGH SKEW: skewness adds")
    print("  nothing over a plain volatility tilt.")
else:
    print("  No leg beats equal-weight convincingly.")

print(f"\n  Statistical note: over {years:.0f} years the standard error of a Sharpe")
print(f"  estimate is roughly {1/np.sqrt(years):.2f}. A gap smaller than that is not")
print("  distinguishable from chance, whatever its sign.")


# ── 8. Subperiods ────────────────────────────────────────────────────────────
print("\n" + "=" * 104)
print("  SUBPERIODS -- a genuine edge shows up everywhere; an artefact concentrates")
print("=" * 104)
print(f"  {'Period':<14}" + "".join(f"{n:>22}" for n in SIGNALS)
      + f"{'Equal-Weight':>18}")
print("-" * 104)

for a, b in SUBPERIODS:
    m_eqw = eqw.loc[f"{a}-01-01":f"{b}-12-31"]
    if len(m_eqw) < 60:
        continue
    line = f"  {a}-{b:<9}"
    for name in SIGNALS:
        sub = results[name]["net"].reindex(idx).loc[f"{a}-01-01":f"{b}-12-31"]
        s   = stats(sub)
        line += f"{s['cagr']*100:>11.2f}% Sh{s['sharpe']:>6.2f}"
    se = stats(m_eqw)
    line += f"{se['cagr']*100:>9.2f}% Sh{se['sharpe']:>5.2f}"
    print(line)
print("=" * 104)


# ── 9. HTML tearsheet for the selected leg ───────────────────────────────────
main = results[REPORT_ON]["net"].reindex(idx)
main.name = f"{REPORT_ON} Top-{TOP_N}"

out = Path.cwd() / "report_skewness.html"
qs.reports.html(
    main, benchmark=spy,
    title=f"{REPORT_ON} Top-{TOP_N} vs SPY (net {FEE*1e4:.0f} bps/side)",
    output=str(out), open_report=False,
)
webbrowser.open(out.resolve().as_uri())
print(f"\nReport ({REPORT_ON}): {out}")
