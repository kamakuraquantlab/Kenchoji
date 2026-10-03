"""How much volatility is there, and how much of it is the spread?

Realized volatility is the square root of the sum of squared returns, and it
depends on how often you sample. Sample fast enough and every observation
carries the bid-ask bounce, which is not price movement: the estimator inflates
without bound as the interval shrinks. The classic diagnostic is the volatility
signature plot -- RV against sampling interval -- and its slope is set by the
spread, so this is article 1's finding showing up somewhere unexpected.

Three series per market:
  mid    the book midpoint, which has no bounce of its own
  trade  executed prices, which alternate between bid and ask
  daily  one midpoint per JST day, close-to-close, the OHLC-style estimate

Everything is reported in bps per day so the intervals are comparable.

Reproducing this:

    1. komachi download --market <MARKET> --start <START> --days <N>
    2. hase derive BookState   --market <MARKET> --start <START> --end <END>
       hase derive MarketPrice --market <MARKET> --start <START> --end <END> \
                              --execution-notional 1000000
    3. python analysis.py

Step 2 is a cache rather than a prerequisite: what it writes, this script would
otherwise derive in memory at about a quarter of a second per market-day.
Nothing here writes, so step 3 against the seller's warehouse reads what is
already there and cannot overwrite it.

Reproduces: §3, §4, §5. Writes output/vol.json.
"""
import argparse, datetime as dt, json, math, pathlib, statistics

import numpy as np

import komachi
from hase.dataset import load
from hase.derive.vol_spread import realized_vol_bps, second_grid
from hase.layout import available_dates
from hase.store import MissingDataError, load_trades

ROOT = komachi.data_root()
MARKETS = [
    "BINANCE:BTC_USDT", "BINANCE:ETH_USDT", "BINANCE:XRP_USDT",
    "BITBANK:BTC_SPOT", "BITBANK:ETH_SPOT", "BITBANK:XRP_SPOT",
    "COINCHECK:BTC_SPOT", "COINCHECK:ETH_SPOT", "COINCHECK:XRP_SPOT",
    "GMO:BTC_JPY", "GMO:ETH_JPY", "GMO:XRP_JPY",
]
# RV is built from log returns, so it is unit-free and a JPY-quoted market is
# directly comparable with a USDT-quoted one. The reference for each asset:
REFERENCE = {"BTC": "BINANCE:BTC_USDT", "ETH": "BINANCE:ETH_USDT", "XRP": "BINANCE:XRP_USDT"}


def asset_of(market):
    return market.split(":")[1].split("_")[0]
INTERVALS = [1, 2, 5, 10, 30, 60, 300, 600, 1800]   # seconds
MIN_SNAPSHOTS = 500      # a day with fewer quotes than this is not measured
MIN_SECONDS = 1_000      # nor one whose grid was filled from almost nothing.
                         # Counted before the fill: afterwards every second
                         # from the first observation onward is populated.

# A single window by default, not a sample spread across the archive. bitbank
# BTC changed fee structure on 2026-02-05 and its book changed with it, so an
# archive-wide sample of that market blends two different markets. Every figure
# here is one fee regime unless --start says otherwise.
ap = argparse.ArgumentParser(description="Realized volatility by sampling interval.")
ap.add_argument("--start", default="2026-06-01", help="first JST day")
ap.add_argument("--days", type=int, default=28, help="window length")
args = ap.parse_args()
_d0 = dt.date.fromisoformat(args.start)
WINDOW = [(_d0 + dt.timedelta(days=i)).isoformat() for i in range(args.days)]
print(f"window {WINDOW[0]} .. {WINDOW[-1]}  ({len(WINDOW)} days)", flush=True)


def dates(market, dataset):
    return available_dates(ROOT, market, dataset)


# `second_grid` and `realized_vol_bps` are Hase's. They were written out here
# three times over -- once in this file, once in `noise.py`, once in
# `regimes.py` -- and they are the same two functions each time.
rv_bps = realized_vol_bps


result = {}
for market in MARKETS:
    have = set(dates(market, "OrderBook"))
    sample = [d for d in WINDOW if d in have]
    if not sample:
        continue

    mid_rv = {k: [] for k in INTERVALS}
    trd_rv = {k: [] for k in INTERVALS}
    daily_close = []
    for d in sample:
        # `sample` is drawn from what is downloaded, so the day exists; what
        # is still worth checking is whether it holds enough to measure.
        if len(load(ROOT, "BookState", market, d)) < MIN_SNAPSHOTS:
            continue
        g = load(ROOT, "VolSpread", market, d)["mid"].to_numpy()
        for k in INTERVALS:
            v = rv_bps(g, k)
            if v is not None:
                mid_rv[k].append(v)
        last = g[np.isfinite(g)]
        if len(last):
            daily_close.append(float(last[-1]))

        try:
            tt = load_trades(ROOT, market, d)
        except MissingDataError:
            tt = None
        if tt is not None:
            gt = second_grid(tt["ts"].to_numpy(), tt["price"].to_numpy(),
                             min_seconds=MIN_SECONDS)
            if gt is not None:
                for k in INTERVALS:
                    v = rv_bps(gt, k)
                    if v is not None:
                        trd_rv[k].append(v)

    if not mid_rv[60]:
        print(f"{market:22} no usable days", flush=True); continue

    mid = {k: round(statistics.median(v), 1) for k, v in mid_rv.items() if v}
    trd = {k: round(statistics.median(v), 1) for k, v in trd_rv.items() if v}
    # close-to-close across the sampled days, scaled to one day
    cc = None
    if len(daily_close) > 3:
        r = np.diff(np.log(np.array(daily_close)))
        cc = round(float(r.std(ddof=1) * 1e4), 1)

    base = mid.get(1800)
    result[market] = {
        "days": len(mid_rv[60]),
        "rv_bps_mid_by_interval_sec": mid,
        "rv_bps_trade_by_interval_sec": trd,
        "daily_close_to_close_bps": cc,
        "inflation_1s_over_1800s": round(mid[1] / base, 2) if base and 1 in mid else None,
        "inflation_1s_over_300s": round(mid[1] / mid[300], 2) if 1 in mid and 300 in mid else None,
        "trade_over_mid_at_1s": round(trd[1] / mid[1], 2) if trd.get(1) and mid.get(1) else None,
    }
    r = result[market]
    print(f"{market:22} mid RV 1s {mid.get(1):>8.1f}  60s {mid.get(60):>7.1f}  "
          f"300s {mid.get(300):>7.1f}  1800s {mid.get(1800):>7.1f}   "
          f"inflate {r['inflation_1s_over_1800s']}x   trade/mid@1s {r['trade_over_mid_at_1s']}", flush=True)

# Ratio to the Binance reference for the same asset, interval by interval.
# If the JP markets track Binance, the ratio should approach 1 as the interval
# grows. Where it does not at short intervals, that is the market's own
# behaviour rather than the asset's.
ratios = {}
for m, r in result.items():
    if m.startswith("BINANCE"):
        continue
    ref = REFERENCE.get(asset_of(m))
    if ref not in result:
        continue
    rv, rvref = r["rv_bps_mid_by_interval_sec"], result[ref]["rv_bps_mid_by_interval_sec"]
    ratios[m] = {str(k): round(rv[k] / rvref[k], 3)
                 for k in sorted(set(rv) & set(rvref), key=int)}
result["_ratio_to_binance"] = ratios

print("\n=== RV relative to the Binance market in the same asset ===")
cols = [1, 5, 30, 60, 300, 1800]
print(f"{'market':22}" + "".join(f"{str(c)+'s':>9}" for c in cols))
for m, r in ratios.items():
    print(f"{m:22}" + "".join(f"{r.get(str(c), float('nan')):>9.2f}" for c in cols), flush=True)

dest = pathlib.Path(__file__).parent / "output" / "vol.json"
dest.write_text(json.dumps(result, indent=2) + "\n")
print("\nwrote", dest)
