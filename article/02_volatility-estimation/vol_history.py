"""Does a market's volatility signature stay put over the archive?

The article measures one four-week window. That is only safe if the market
did not change character inside the record, and bitbank BTC did: its fee
structure changed in February 2026 and the quote widened with it. This tracks,
month by month, the 10-second and 30-minute RV of that market. Before the
change the 10-second estimate sits below the 30-minute one; after it, above.

Reproduces: §5. Writes output/vol_history.json.
"""
import collections, json, pathlib, statistics

import komachi
from hase.dataset import load
from hase.layout import available_dates
from rv import has_outage, pooled, rv_bps

ROOT = komachi.data_root()
MARKET = "BITBANK:BTC_SPOT"
INTERVALS = [10, 1800]
MIN_SNAPSHOTS = 500

per_month = collections.defaultdict(lambda: collections.defaultdict(list))
for d in available_dates(ROOT, MARKET, "OrderBook"):
    book = load(ROOT, "BookState", MARKET, d)
    if len(book) < MIN_SNAPSHOTS or has_outage(book):
        continue
    g = load(ROOT, "VolSpread", MARKET, d)["mid"].to_numpy()
    for k in INTERVALS:
        v = rv_bps(g, k)
        if v is not None:
            per_month[d[:7]][k].append(v)
    per_month[d[:7]]["spread"].append(float(book["spread_bps"].median()))

out = {}
for month, v in sorted(per_month.items()):
    if not all(v[k] for k in INTERVALS):
        continue
    rv = {str(k): round(pooled(v[k]), 1) for k in INTERVALS}
    out[month] = {"days": len(v[INTERVALS[0]]),
                  "rv_bps_by_interval_sec": rv,
                  "ratio_10s_over_1800s": round(rv["10"] / rv["1800"], 2),
                  "median_spread_bps": round(statistics.median(v["spread"]), 4)}
    r = out[month]
    print(f"{month}  days {r['days']:>2}  RV 10s {rv['10']:>6.1f}  1800s {rv['1800']:>6.1f}  "
          f"10s/1800s {r['ratio_10s_over_1800s']:.2f}  spread {r['median_spread_bps']:.4f}bps", flush=True)

dest = pathlib.Path(__file__).parent / "output" / "vol_history.json"
dest.write_text(json.dumps({MARKET: out}, indent=2) + "\n")
print("\nwrote", dest)
