"""bitbank's BTC quote changed character in February 2026. Does the volatility
signature change with it?

Before: the spread sat on the one-yen tick. After: roughly 1 bp. Same market,
same code, every usable day on each side of the change: the 10-second RV sat
well below the 5-to-30-minute level before, and much closer to it after.

Reproduces: §5. Writes output/regimes.json.
"""
import json, pathlib, statistics

import numpy as np

import komachi
from hase.dataset import load
from hase.layout import available_dates
from rv import has_outage, pooled, rv_bps

ROOT = komachi.data_root()
MARKET = "BITBANK:BTC_SPOT"
REGIMES = {"tick-pinned 2025-07..2026-01": ("2025-07-01", "2026-01-31"),
           "wide 2026-03..2026-08": ("2026-03-01", "2026-08-31")}
INTERVALS = [10, 30, 60, 300, 600, 1800]

alld = available_dates(ROOT, MARKET, "OrderBook")
out = {}
for label, (lo, hi) in REGIMES.items():
    ds = [d for d in alld if lo <= d <= hi]
    rv = {k: [] for k in INTERVALS}
    acs, spr = [], []
    for d in ds:
        book = load(ROOT, "BookState", MARKET, d)
        if len(book) < 500 or has_outage(book):
            continue
        g = load(ROOT, "VolSpread", MARKET, d)["mid"].to_numpy()
        spr.append(float(book["spread_bps"].median()))
        for k in INTERVALS:
            v = rv_bps(g, k)
            if v is not None:
                rv[k].append(v)
        with np.errstate(invalid="ignore", divide="ignore"):
            r10 = np.diff(np.log(g[::10]))
        r10 = r10[np.isfinite(r10)]
        if len(r10) > 1_000 and r10[:-1].std() > 0:
            acs.append(float(np.corrcoef(r10[:-1], r10[1:])[0, 1]))
    m = {k: round(pooled(v), 1) for k, v in rv.items() if v}
    out[label] = {
        "days": len(acs),
        "median_spread_bps": round(statistics.median(spr), 4),
        "rv_bps_by_interval_sec": m,
        "ratio_10s_over_1800s": round(m[10] / m[1800], 2),
        "ac1_10s_returns": round(statistics.median(acs), 4),
    }
    r = out[label]
    print(f"{label:32} spread {r['median_spread_bps']:>8.4f}bps  " +
          "  ".join(f"{k}s {m[k]:>6.1f}" for k in INTERVALS) +
          f"  10s/1800s {r['ratio_10s_over_1800s']:>5.2f}x  AC(1) {r['ac1_10s_returns']:>8.4f}", flush=True)

dest = pathlib.Path(__file__).parent / "output" / "regimes.json"
dest.write_text(json.dumps(out, indent=2) + "\n")
print("\nwrote", dest)
