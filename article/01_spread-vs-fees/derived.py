"""The ratios the draft quotes, computed from the two measurement files.

Rule 1 in article/README.md: no number in a draft that is not in output/. A
ratio typed into prose is exactly the kind that goes stale when the underlying
measurement is regenerated.

Reproduces: §1〜§4 の倍率. Writes output/derived.json.
"""

import json
import pathlib
import statistics

here = pathlib.Path(__file__).parent
g = json.loads((here / "output" / "groups_2026-06.json").read_text())["groups"]
f = json.loads((here / "output" / "fee_change.json").read_text())
flat = {m: r for grp in g.values() for m, r in grp.items()}

pairs = [
    ("BTC", "GMO:BTC_SPOT", "GMO:BTC_JPY"),
    ("ETH", "GMO:ETH_SPOT", "GMO:ETH_JPY"),
    ("XRP", "GMO:XRP_SPOT", "GMO:XRP_JPY"),
]
out = {
    "gmo_spot_vs_leverage": {},
    "group_medians_bps": {},
    "fee_change": {},
    "scale": {},
}

for a, sp, lv in pairs:
    s, l = flat[sp], flat[lv]
    out["gmo_spot_vs_leverage"][a] = {
        "spot_bps": s["spread_bps"],
        "leverage_bps": l["spread_bps"],
        "leverage_spread_wider_x": round(l["spread_bps"] / s["spread_bps"], 2),
        "leverage_trades_more_x": round(l["trades_per_day"] / s["trades_per_day"], 2),
    }
for name, grp in g.items():
    v = [r["spread_bps"] for r in grp.values()]
    out["group_medians_bps"][name] = {
        "median": round(statistics.median(v), 4),
        "min": min(v),
        "max": max(v),
        "n": len(v),
    }
neg = out["group_medians_bps"]["negative maker fee"]["median"]
zero = out["group_medians_bps"]["zero maker fee"]["median"]
out["group_medians_bps"]["zero_over_negative_x"] = round(zero / neg, 2)

W = f["windows"]
B = W["before 2026-01-19..02-01"]["BITBANK:BTC_SPOT"]
A = W["after  2026-02-09..02-22"]["BITBANK:BTC_SPOT"]
M = W["march  2026-03-01..03-31"]["BITBANK:BTC_SPOT"]
cB = W["before 2026-01-19..02-01"]["BITBANK:XRP_SPOT"]
cA = W["after  2026-02-09..02-22"]["BITBANK:XRP_SPOT"]
cM = W["march  2026-03-01..03-31"]["BITBANK:XRP_SPOT"]


def x(a, b, k, nd=2):
    return round(a[k] / b[k], nd)


# The mean and the wide share are what the spread as a whole did; the median
# flips between the book's two states and is quoted only beside them.
# "relative" divides BTC's change by XRP's over the same windows: the control.
out["fee_change"] = {
    "change": f["change"],
    "btc_mean_x_after": x(A, B, "spread_mean_bps"),
    "btc_mean_x_march": x(M, B, "spread_mean_bps"),
    "xrp_mean_x_after": x(cA, cB, "spread_mean_bps"),
    "xrp_mean_x_march": x(cM, cB, "spread_mean_bps"),
    "relative_mean_x_after": round(x(A, B, "spread_mean_bps", 6) / x(cA, cB, "spread_mean_bps", 6), 2),
    "relative_mean_x_march": round(x(M, B, "spread_mean_bps", 6) / x(cM, cB, "spread_mean_bps", 6), 2),
    "btc_median_x_march": round(M["spread_bps"] / B["spread_bps"]),
    "btc_depth_thinner_x_after": x(B, A, "top_of_book_jpy", 1),
    "btc_trades_x_after": x(A, B, "trades_per_day"),
    "btc_rv_x_after": x(A, B, "rv_bps"),
    "btc_rv_x_march": x(M, B, "rv_bps"),
}
daily = f["daily_spread_bps_2026-01-01_2026-03-31"]
out["fee_change"]["control_daily_max"] = max(
    ([d, med] for d, med, _, _ in daily["BITBANK:XRP_SPOT"]), key=lambda r: r[1]
)
out["fee_change"]["btc_daily_mean_max_march"] = max(
    mean for d, _, mean, _ in daily["BITBANK:BTC_SPOT"] if d >= "2026-03-01"
)
out["scale"] = {
    "binance_btc_over_gmo_leverage_trades_x": round(
        flat["BINANCE:BTC_USDT"]["trades_per_day"]
        / flat["GMO:BTC_JPY"]["trades_per_day"],
        1,
    ),
}

dest = here / "output" / "derived.json"
dest.write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(out, indent=2))
print("\nwrote", dest)
