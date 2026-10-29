"""The two numbers the market sets, per market, over one fixed month.

    s  round-trip cost in bps: the 1,000,000 JPY book walk of article 1, plus
       the taker fee on both legs (an input, not a measurement)
    v  volatility scale for one-minute returns, in bps (not bps/minute):
       article 2's daily 1-minute RV divided by sqrt(1,440)

Measured with the same definitions as the two published articles, over all of
June 2026 rather than their first four weeks:

    s  each day's median walked spread, then the median of the days
    v  each day's RV on the one-second mid grid, outage days dropped, then the
       root of the mean daily variance

The window is fixed. An earlier version sampled every Nth day of whatever the
archive held, so its figures moved whenever the archive grew.

Reproducing this:

    1. komachi download --market <MARKET> --start 2026-06-01 --end 2026-06-30
       (the six zero-taker-fee markets below)
    2. python3 measure.py

Reproduces: §1, §3.1. Writes output/inputs.json.
"""
import argparse, datetime as dt, json, math, pathlib, statistics

import numpy as np

import komachi
from hase.dataset import load
from hase.derive.market_price import dropped as dropped_count
from hase.derive.grid import quote_grid
from hase.layout import available_dates

ROOT = komachi.data_root()
SIZE_JPY = 1_000_000
MIN_SNAPSHOTS = 500     # article 1: a day thinner than this is not measured
MIN_FILLS = 20          # article 1: nor a round trip the book rarely completes
MAX_GAP_SEC = 300       # article 2: a feed gap longer than this drops the day

# Taker fee per side, percent.  The study deliberately contains only markets
# whose fee is zero, so that S is the directly measured walked book cost.
TAKER_PCT = {
    "COINCHECK:BTC_SPOT": (0.0, "2026-10-10"),
    "COINCHECK:ETH_SPOT": (0.0, "2026-10-10"),
    "COINCHECK:XRP_SPOT": (0.0, "2026-10-10"),
    "GMO:BTC_JPY": (0.0, "2026-10-10"),
    "GMO:ETH_JPY": (0.0, "2026-10-10"),
    "GMO:XRP_JPY": (0.0, "2026-10-10"),
}
IN_SCOPE = ["COINCHECK:BTC_SPOT", "COINCHECK:ETH_SPOT", "COINCHECK:XRP_SPOT",
            "GMO:BTC_JPY", "GMO:ETH_JPY", "GMO:XRP_JPY"]


def has_outage(book):
    ts = np.sort(np.asarray(book["ts"], dtype="float64"))
    return len(ts) < 2 or float(np.diff(ts).max()) > MAX_GAP_SEC


def rv_bps(grid, step):
    """Article 2's RV: one day's one-second grid sampled every `step` seconds,
    scaled to the full 24 hours."""
    grid = np.asarray(grid)
    with np.errstate(invalid="ignore", divide="ignore"):
        r = np.diff(np.log(grid[::step]))
    r = r[np.isfinite(r)]
    if len(r) < 10:
        return None
    return float(np.sqrt((r ** 2).sum() * (len(grid) // step) / len(r)) * 1e4)


def mid_grid(market, d):
    """One-second mid for the day, or None if the day is thin or has an outage."""
    if d not in available_dates(ROOT, market, "OrderBook"):
        return None
    book = load(ROOT, "BookState", market, d)
    if len(book) < MIN_SNAPSHOTS or has_outage(book):
        return None
    return quote_grid(ROOT, market, d)["mid"].to_numpy()


ap = argparse.ArgumentParser(description="s and v per market, one fixed window.")
ap.add_argument("--start", default="2026-06-01")
ap.add_argument("--end", default="2026-06-30")
args = ap.parse_args()
d0, d1 = dt.date.fromisoformat(args.start), dt.date.fromisoformat(args.end)
DATES = [(d0 + dt.timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]
print(f"window {DATES[0]} .. {DATES[-1]}  ({len(DATES)} days)\n", flush=True)

out = {"window": [DATES[0], DATES[-1]], "size_jpy": SIZE_JPY,
       "in_scope": IN_SCOPE, "markets": {}}
for market, (fee, checked) in TAKER_PCT.items():
    cost, fills, rv60, rv300, dropped = [], [], [], [], []
    first = last = None
    for d in DATES:
        if d not in available_dates(ROOT, market, "OrderBook"):
            continue
        book = load(ROOT, "BookState", market, d)
        if len(book) < MIN_SNAPSHOTS:
            continue
        if first is None:
            first = float(book["mid"].iloc[0])
        last = float(book["mid"].iloc[-1])

        # Hase leaves out the snapshots the book cannot fill and the collector
        # artefacts, and counts every snapshot of the day in `dropped`.
        walked = load(ROOT, "MarketPrice", market, d, execution_notional=SIZE_JPY)
        snapshots = dropped_count(walked).get("snapshots", len(walked))
        fills.append(len(walked) / snapshots if snapshots else 0.0)
        if len(walked) >= MIN_FILLS:
            cost.append(float(walked["spread_bps"].median()))

        if has_outage(book):
            dropped.append(d)
            continue
        g = quote_grid(ROOT, market, d)["mid"].to_numpy()
        a, b = rv_bps(g, 60), rv_bps(g, 300)
        if a is None or b is None:
            continue
        rv60.append(a); rv300.append(b)

    board = statistics.median(cost)
    s = board + 2 * fee * 100
    pooled = lambda xs: math.sqrt(statistics.mean(x * x for x in xs))
    v = pooled(rv60) / math.sqrt(1440)
    out["markets"][market] = {
        "days_cost": len(cost),
        "days_vol": len(rv60),
        "days_dropped_for_outage": dropped,
        "board_roundtrip_bps": round(board, 3),
        "fillable_pct": round(statistics.mean(fills) * 100, 1),
        "taker_pct_per_side": fee,
        "taker_fee_checked": checked,
        "s_bps": round(s, 3),
        "rv_1min_bps_per_day": round(pooled(rv60), 1),
        "rv_5min_bps_per_day": round(pooled(rv300), 1),
        "v_bps_per_min": round(v, 3),
        "v_over_s": round(v / s, 3),
        "s_over_v_squared_min": round((s / v) ** 2, 1),
        "drift_bps": round(math.log(last / first) * 1e4),
    }
    r = out["markets"][market]
    print(f"{market:20} board {board:7.3f} fee {fee:4.2f}% s {s:7.3f}  v {v:5.2f}  "
          f"v/s {v/s:5.2f}  (s/v)^2 {r['s_over_v_squared_min']:6.1f}min  "
          f"drift {r['drift_bps']:+d}bps  days {len(cost)}/{len(rv60)}", flush=True)

dest = pathlib.Path(__file__).parent / "output" / "inputs.json"
dest.write_text(json.dumps(out, indent=2) + "\n")
print("\nwrote", dest)
