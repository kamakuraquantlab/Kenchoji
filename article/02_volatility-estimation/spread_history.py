"""Has the spread been stable over the archive?

Article 1 quotes one median spread per market. That is only meaningful if the
spread is stationary. This checks, monthly, and it is not: bitbank's BTC quote
changes character partway through the record.

Reproduces: §6. Writes output/spread_history.json.
"""
import collections, json, pathlib, statistics

import komachi
from hase.dataset import load
from hase.layout import available_dates

ROOT = komachi.data_root()
MARKETS = ["BITBANK:BTC_SPOT", "BITBANK:ETH_SPOT", "BITBANK:XRP_SPOT",
           "COINCHECK:BTC_SPOT", "GMO:BTC_JPY"]
MIN_SNAPSHOTS = 50

out = {}
for market in MARKETS:
    per_month = collections.defaultdict(list)
    # Every third day is plenty for a monthly median. The within-day sampling
    # this used to do as well is gone: it was there because recomputing the
    # spread from the raw book was slow, and Hase has already done it.
    for d in available_dates(ROOT, market, "OrderBook")[::3]:
        book = load(ROOT, "BookState", market, d)
        if len(book) < MIN_SNAPSHOTS:
            continue
        per_month[d[:7]].append(float(book["spread_bps"].median()))
    out[market] = {m: round(statistics.median(v), 4) for m, v in sorted(per_month.items())}
    print(market)
    print("   " + "  ".join(f"{m[2:]}:{v:.4f}" for m, v in sorted(out[market].items())), flush=True)

dest = pathlib.Path(__file__).parent / "output" / "spread_history.json"
dest.write_text(json.dumps(out, indent=2) + "\n")
print("\nwrote", dest)
