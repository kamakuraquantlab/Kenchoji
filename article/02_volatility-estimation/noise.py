"""Is the high-frequency volatility real movement, or quote noise?

Microstructure noise leaves a signature: an up-tick followed by a down-tick,
which shows up as NEGATIVE first-order autocorrelation in high-frequency
returns. Real price movement has autocorrelation near zero.

Also measures how the quote behaves -- how often the midpoint moves at all, and
how far when it does -- because a narrow quote that flickers is a different
animal from a wide quote that sits still.

Reproduces: §5.2, §5.3. Writes output/noise.json.
"""
import argparse, datetime as dt, json, pathlib, statistics

import numpy as np

import komachi
from hase.dataset import load
from hase.layout import available_dates

ROOT = komachi.data_root()
MARKETS = [
    "BITBANK:BTC_SPOT", "BITBANK:ETH_SPOT", "BITBANK:XRP_SPOT",
    "COINCHECK:BTC_SPOT", "COINCHECK:ETH_SPOT", "COINCHECK:XRP_SPOT",
    "GMO:BTC_JPY", "GMO:ETH_JPY", "GMO:XRP_JPY",
]
# One window, matching analysis.py, so bitbank BTC does not straddle its
# 2026-02-05 fee change.
ap = argparse.ArgumentParser(description="Is the high-frequency movement noise?")
ap.add_argument("--start", default="2026-06-01")
ap.add_argument("--days", type=int, default=28)
args = ap.parse_args()
_d0 = dt.date.fromisoformat(args.start)
WINDOW = [(_d0 + dt.timedelta(days=i)).isoformat() for i in range(args.days)]
print(f"window {WINDOW[0]} .. {WINDOW[-1]}", flush=True)


# The one-second mid grid and the quoted spread both come from Hase now.
# `VolSpread` is that grid; it used to be rebuilt here, in `analysis.py`, and
# in `regimes.py`, three times from the same book.


out = {}
for market in MARKETS:
    have = set(available_dates(ROOT, market, "OrderBook"))
    ds = [d for d in WINDOW if d in have]
    if not ds:
        continue
    acs, moves, jumps, spr = [], [], [], []
    for d in ds:
        book = load(ROOT, "BookState", market, d)
        if len(book) < 500:
            continue
        g = load(ROOT, "VolSpread", market, d)["mid"].to_numpy()
        with np.errstate(invalid="ignore", divide="ignore"):
            r = np.diff(np.log(g)) * 1e4
        r = r[np.isfinite(r)]
        if len(r) < 10_000:
            continue
        # first-order autocorrelation of 1-second returns
        x, y = r[:-1], r[1:]
        if x.std() > 0 and y.std() > 0:
            acs.append(float(np.corrcoef(x, y)[0, 1]))
        moves.append(float((r != 0).mean() * 100))          # % of seconds the mid moved
        nz = np.abs(r[r != 0])
        if len(nz):
            jumps.append(float(np.median(nz)))              # typical move, bps
        spr.append(float(book["spread_bps"].median()))

    if not acs:
        print(f"{market:22} no usable days", flush=True); continue
    out[market] = {
        "days": len(acs),
        "ac1_1s_returns": round(statistics.median(acs), 4),
        "pct_seconds_mid_moved": round(statistics.median(moves), 1),
        "median_move_bps": round(statistics.median(jumps), 4),
        "median_spread_bps": round(statistics.median(spr), 4),
    }
    r = out[market]
    print(f"{market:22} AC(1) {r['ac1_1s_returns']:>8.4f}   moved {r['pct_seconds_mid_moved']:>5.1f}% of sec   "
          f"typical move {r['median_move_bps']:>8.4f}bps   spread {r['median_spread_bps']:>8.4f}bps", flush=True)

dest = pathlib.Path(__file__).parent / "output" / "noise.json"
dest.write_text(json.dumps(out, indent=2) + "\n")
print("\nwrote", dest)
