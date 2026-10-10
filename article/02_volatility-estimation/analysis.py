"""How much volatility is there at each sampling interval, and how does each
domestic market compare with Binance?

Realized volatility is the square root of the sum of squared returns, and it
depends on how often you sample. Quote noise that bounces back pushes it up as
the interval shrinks; a price that creeps toward its new level pulls it down.
The classic diagnostic is the volatility signature plot -- RV against sampling
interval. From 10 seconds up, every market here comes out smaller at the short
end, and every domestic market sits just below Binance.

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

Reproduces: §2, §3. Writes output/vol.json.
"""
import argparse, datetime as dt, json, math, pathlib, statistics

import numpy as np

import komachi
from hase.dataset import load
from hase.derive.vol_spread import second_grid
from hase.layout import available_dates
from hase.store import MissingDataError, load_trades
from rv import has_outage, pooled, rv_bps

ROOT = komachi.data_root()
MARKETS = [
    "BINANCE:BTC_USDT", "BINANCE:ETH_USDT", "BINANCE:XRP_USDT",
    "BITBANK:BTC_SPOT", "BITBANK:ETH_SPOT", "BITBANK:XRP_SPOT",
    "COINCHECK:BTC_SPOT", "COINCHECK:ETH_SPOT", "COINCHECK:XRP_SPOT",
    "GMO:BTC_SPOT", "GMO:ETH_SPOT", "GMO:XRP_SPOT",
    "GMO:BTC_JPY", "GMO:ETH_JPY", "GMO:XRP_JPY",
]
# RV is built from log returns, so it is unit-free and a JPY-quoted market is
# directly comparable with a USDT-quoted one. The reference for each asset:
REFERENCE = {"BTC": "BINANCE:BTC_USDT", "ETH": "BINANCE:ETH_USDT", "XRP": "BINANCE:XRP_USDT"}


def asset_of(market):
    return market.split(":")[1].split("_")[0]
INTERVALS = [10, 30, 60, 300, 600, 1800]   # seconds; below 10s the leader's own
                                           # 1s RV is distorted, so ratios mislead
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


# `second_grid` is Hase's. `rv_bps`, `pooled` and `has_outage` are local, in
# rv.py: every interval scaled to the same 24 hours, days combined by their
# variance, and days with a feed outage left out. See there for why.


daily = {}            # market -> date -> {interval: mid RV}
result = {}
for market in MARKETS:
    have = set(dates(market, "OrderBook"))
    sample = [d for d in WINDOW if d in have]
    if not sample:
        continue

    days, trd_rv, daily_close, dropped = {}, {k: [] for k in INTERVALS}, [], []
    for d in sample:
        # `sample` is drawn from what is downloaded, so the day exists; what
        # is still worth checking is whether it holds enough to measure.
        book = load(ROOT, "BookState", market, d)
        if len(book) < MIN_SNAPSHOTS:
            continue
        if has_outage(book):
            dropped.append(d)
            continue
        g = load(ROOT, "VolSpread", market, d)["mid"].to_numpy()
        row = {k: rv_bps(g, k) for k in INTERVALS}
        if any(v is None for v in row.values()):
            continue
        days[d] = row
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

    if not days:
        print(f"{market:22} no usable days", flush=True); continue
    daily[market] = days

    mid = {k: round(pooled([r[k] for r in days.values()]), 1) for k in INTERVALS}
    trd = {k: round(pooled(v), 1) for k, v in trd_rv.items() if v}
    # close-to-close across the sampled days, scaled to one day
    cc = None
    if len(daily_close) > 3:
        r = np.diff(np.log(np.array(daily_close)))
        cc = round(float(r.std(ddof=1) * 1e4), 1)

    result[market] = {
        "days": len(days),
        "days_dropped_for_outage": dropped,
        "rv_bps_mid_by_interval_sec": mid,
        "rv_bps_trade_by_interval_sec": trd,
        "daily_close_to_close_bps": cc,
        "ratio_10s_over_1800s": round(mid[10] / mid[1800], 2),
        "trade_over_mid_at_10s": round(trd[10] / mid[10], 2) if trd.get(10) else None,
    }
    r = result[market]
    print(f"{market:22} days {len(days):>2} mid RV " + "  ".join(f"{k}s {mid[k]:>6.1f}" for k in INTERVALS) +
          f"   10s/1800s {r['ratio_10s_over_1800s']}x   trade/mid@10s {r['trade_over_mid_at_10s']}"
          + (f"   dropped {','.join(x[5:] for x in dropped)}" if dropped else ""), flush=True)


def bootstrap_se(num, den, n_boot=2000, seed=0):
    """Standard error of pooled(num) / pooled(den), resampling whole days."""
    num, den = np.asarray(num), np.asarray(den)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(num), (n_boot, len(num)))
    ratios = np.sqrt((num[idx] ** 2).mean(1) / (den[idx] ** 2).mean(1))
    return float(ratios.std())


# Ratio to the Binance reference for the same asset, interval by interval, on
# the days both markets were measured. Pooled over those same days, so the
# day-to-day swing in volatility cancels and the ratio is tight; the bootstrap
# says how tight.
ratios = {}
for m in result:
    if m.startswith("BINANCE"):
        continue
    ref = REFERENCE.get(asset_of(m))
    if ref not in daily:
        continue
    common = sorted(set(daily[m]) & set(daily[ref]))
    ratios[m] = {"days": len(common)}
    for k in INTERVALS:
        a = [daily[m][d][k] for d in common]
        b = [daily[ref][d][k] for d in common]
        ratios[m][str(k)] = {"ratio": round(pooled(a) / pooled(b), 3),
                             "se": round(bootstrap_se(a, b), 3)}
result["_ratio_to_binance"] = ratios

# Each market against its own 30-minute RV, with the same bootstrap. The
# 30-minute RV holds 48 returns a day, so this one is far noisier.
for m, days in daily.items():
    vals = list(days.values())
    base = [r[1800] for r in vals]
    result[m]["ratio_to_1800s"] = {
        str(k): {"ratio": round(pooled([r[k] for r in vals]) / pooled(base), 3),
                 "se": round(bootstrap_se([r[k] for r in vals], base), 3)}
        for k in INTERVALS if k != 1800}

print("\n=== RV relative to the Binance market in the same asset (± bootstrap SE) ===")
print(f"{'market':22}" + "".join(f"{str(c)+'s':>13}" for c in INTERVALS))
for m, r in ratios.items():
    print(f"{m:22}" + "".join(f"{r[str(c)]['ratio']:>7.2f}±{r[str(c)]['se']*100:.1f}%" for c in INTERVALS), flush=True)

dest = pathlib.Path(__file__).parent / "output" / "vol.json"
dest.write_text(json.dumps(result, indent=2) + "\n")
print("\nwrote", dest)
