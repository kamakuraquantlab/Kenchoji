"""How much of a Binance move does each domestic book absorb, and how fast?

The RV ratio in analysis.py measures how BIG each market's moves are. It cannot
tell a market that tracks Binance closely from one that jumps around on its own,
because idiosyncratic noise raises RV just as real tracking does.

This measures absorption directly. Over a horizon h, regress the domestic log
return on the Binance log return for the same asset:

    r_jp(t, h) = alpha + beta * r_binance(t, h) + e

beta is the share of a Binance move that has reached the domestic book within h.
beta -> 1 means fully absorbed. A market that is slow to react shows a low beta
at short horizons and climbs toward 1 as h grows. R2 says how much of the
domestic move Binance explains at all.

This is the test for "traders here do not react quickly", which RV cannot
answer. Single fee regime by default, so bitbank BTC is not straddling its
February 2026 change.

Reproduces: §5.1. Writes output/response.json.
"""
import argparse, datetime as dt, json, pathlib, statistics

import numpy as np

import komachi
from hase.dataset import load
from hase.layout import available_dates

ROOT = komachi.data_root()
PAIRS = [
    ("BITBANK:ETH_SPOT", "BINANCE:ETH_USDT", "negative maker"),
    ("BITBANK:XRP_SPOT", "BINANCE:XRP_USDT", "negative maker"),
    ("BITBANK:BTC_SPOT", "BINANCE:BTC_USDT", "maker 0.00%, taker 0.10% since 2026-02"),
    ("COINCHECK:BTC_SPOT", "BINANCE:BTC_USDT", "zero fee"),
    ("COINCHECK:ETH_SPOT", "BINANCE:ETH_USDT", "zero fee"),
    ("COINCHECK:XRP_SPOT", "BINANCE:XRP_USDT", "zero fee"),
    ("GMO:BTC_JPY", "BINANCE:BTC_USDT", "zero fee, leverage"),
    ("GMO:ETH_JPY", "BINANCE:ETH_USDT", "zero fee, leverage"),
    ("GMO:XRP_JPY", "BINANCE:XRP_USDT", "zero fee, leverage"),
]
HORIZONS = [1, 5, 15, 60, 300]
MIN_SNAPSHOTS = 5_000


def grid(market, date):
    """The one-second mid grid for one market-day, or None if too thin.

    Both sides of the regression have to be on the same clock before they can
    be compared at all, which is what `VolSpread` is. Putting them there is the
    step this analysis used to do for itself.
    """
    if date not in available_dates(ROOT, market, "OrderBook"):
        return None
    if len(load(ROOT, "BookState", market, date)) < MIN_SNAPSHOTS:
        return None
    return load(ROOT, "VolSpread", market, date)["mid"].to_numpy()


ap = argparse.ArgumentParser(description="Absorption of Binance moves, by horizon.")
ap.add_argument("--start", default="2026-06-01")
ap.add_argument("--days", type=int, default=28)
args = ap.parse_args()
d0 = dt.date.fromisoformat(args.start)
DATES = [(d0 + dt.timedelta(days=i)).isoformat() for i in range(args.days)]
print(f"window {DATES[0]} .. {DATES[-1]}  ({len(DATES)} days)", flush=True)

result = {}
for jp, ref, fee in PAIRS:
    per_h = {h: {"beta": [], "r2": []} for h in HORIZONS}
    for d in DATES:
        A, B = grid(jp, d), grid(ref, d)
        if A is None or B is None:
            continue
        for h in HORIZONS:
            x = np.diff(np.log(B[::h]))       # Binance return
            y = np.diff(np.log(A[::h]))       # domestic return
            good = np.isfinite(x) & np.isfinite(y)
            x, y = x[good], y[good]
            if len(x) < 50 or x.std() == 0:
                continue
            beta = float(np.cov(x, y, ddof=1)[0, 1] / x.var(ddof=1))
            r = float(np.corrcoef(x, y)[0, 1])
            per_h[h]["beta"].append(beta)
            per_h[h]["r2"].append(r * r)
    if not per_h[60]["beta"]:
        print(f"{jp:22} no usable days", flush=True); continue
    result[jp] = {"reference": ref, "fee": fee, "days": len(per_h[60]["beta"]),
                  "by_horizon_sec": {}}
    for h in HORIZONS:
        if per_h[h]["beta"]:
            result[jp]["by_horizon_sec"][str(h)] = {
                "beta": round(statistics.median(per_h[h]["beta"]), 3),
                "r2": round(statistics.median(per_h[h]["r2"]), 3),
            }
    bh = result[jp]["by_horizon_sec"]
    print(f"{jp:22} {fee:24} " +
          "  ".join(f"{h}s b={bh[str(h)]['beta']:.2f} r2={bh[str(h)]['r2']:.2f}"
                    for h in HORIZONS if str(h) in bh), flush=True)

dest = pathlib.Path(__file__).parent / "output" / "response.json"
dest.write_text(json.dumps(result, indent=2) + "\n")
print("\nwrote", dest)
