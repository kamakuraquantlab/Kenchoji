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
before = W["before 2025-11-01..2026-02-01"]
after = W["after 2026-03-01..2026-06-30"]
btc, xrp = "BITBANK:BTC_SPOT", "BITBANK:XRP_SPOT"
bx = after[btc]["spread_mean_bps"] / before[btc]["spread_mean_bps"]
xx = after[xrp]["spread_mean_bps"] / before[xrp]["spread_mean_bps"]


def week_range(market, lo, hi, skip=()):
    """Lowest and highest weekly mean among weeks starting in [lo, hi]."""
    v = [m for w, _, m in f["weekly"][market] if lo <= w <= hi and w not in skip]
    return [round(min(v), 2), round(max(v), 2)]


# "relative" divides BTC's change by XRP's over the same windows: the control.
out["fee_change"] = {
    "change": f["change"],
    "btc_mean_x": round(bx, 2),
    "xrp_mean_x": round(xx, 2),
    "relative_mean_x": round(bx / xx, 2),
    "selloff_week": {m: next(v for w, _, v in f["weekly"][m] if w == f["selloff_week"])
                     for m in (btc, xrp)},
    "btc_weekly_range_before": week_range(btc, "2025-10-30", "2026-01-22"),
    "btc_weekly_range_march": week_range(btc, "2026-02-26", "2026-03-26"),
    "btc_weekly_range_apr_may": week_range(btc, "2026-04-01", "2026-05-31"),
    "btc_weekly_range_june": week_range(btc, "2026-06-01", "2026-06-30"),
    "xrp_weekly_range_all_but_selloff": week_range(xrp, "2025-10-30", "2026-06-30",
                                                   skip=(f["selloff_week"],)),
}
# The same comparison in bps: each market's change, and BTC's change less
# XRP's (the difference in differences), then the robustness variants' range.
fc = out["fee_change"]
fc["btc_mean_change_bps"] = round(after[btc]["spread_mean_bps"] - before[btc]["spread_mean_bps"], 2)
fc["xrp_mean_change_bps"] = round(after[xrp]["spread_mean_bps"] - before[xrp]["spread_mean_bps"], 2)
fc["difference_in_differences_bps"] = round(
    fc["btc_mean_change_bps"] - fc["xrp_mean_change_bps"], 2)
did = [r["difference_in_differences_bps"] for r in f["robustness"].values()]
fc["robustness_did_range_bps"] = [round(min(did), 2), round(max(did), 2)]
fc["row_gap_sec"] = sorted({w[m]["median_row_gap_sec"] for w in W.values() for m in (btc, xrp)})
fc["time_weighted_minus_plain_max_bps"] = round(max(
    abs(w[m]["spread_time_weighted_mean_bps"] - w[m]["spread_mean_bps"])
    for w in W.values() for m in (btc, xrp)), 2)
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
