"""Render the two article figures from the checked-in measurement JSON.

Run ``python plots.py`` after ``analysis.py`` and ``fee_change.py``.

Reproduces: §2, §3. Writes output/gmo_spread_distribution.png and
output/bitbank_fee_change_daily.png.
"""
import datetime as dt
import json
import pathlib

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Patch


HERE = pathlib.Path(__file__).parent
OUTPUT = HERE / "output"
SPOT = "#0072b2"
LEVERAGE = "#d55e00"
BTC = "#0072b2"
XRP = "#009e73"


def finish(fig, name):
    fig.savefig(OUTPUT / name, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def gmo_distribution():
    groups = json.loads((OUTPUT / "groups_2026-06.json").read_text())["groups"]
    markets = {m: r for group in groups.values() for m, r in group.items()}
    assets = ("BTC", "ETH", "XRP")
    values = []
    positions = []
    colors = []
    for i, asset in enumerate(assets, start=1):
        for offset, suffix, color in ((-0.18, "SPOT", SPOT), (0.18, "JPY", LEVERAGE)):
            daily = markets[f"GMO:{asset}_{suffix}"]["daily_spread_bps"]
            values.append([v for _, v in daily])
            positions.append(i + offset)
            colors.append(color)

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    boxes = ax.boxplot(values, positions=positions, widths=0.28, patch_artist=True,
                       showfliers=False, medianprops={"color": "white", "linewidth": 2})
    for box, color in zip(boxes["boxes"], colors):
        box.set_facecolor(color)
        box.set_alpha(0.85)
    for i, (vals, pos, color) in enumerate(zip(values, positions, colors)):
        offsets = [((j % 7) - 3) * 0.009 for j in range(len(vals))]
        ax.scatter([pos + x for x in offsets], vals, color=color, s=12, alpha=0.48,
                   edgecolors="none")
    ax.set_xticks(range(1, 4), assets)
    ax.set_ylabel("Daily median spread (bps)")
    ax.set_title("GMO spot vs leverage: spread distributions")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(handles=[Patch(facecolor=SPOT, label="Spot (negative maker fee)"),
                       Patch(facecolor=LEVERAGE, label="Leverage (zero maker fee)")],
              frameon=False, loc="upper left")
    fig.tight_layout()
    finish(fig, "gmo_spread_distribution.png")


def bitbank_daily():
    """Daily median above, daily mean below, on the same dates.

    The books are bimodal (one tick wide most of the time, 2-6 bps the rest), so
    the median jumps by three orders of magnitude when the wide share passes one
    half while the mean, the average a taker pays, moves under twofold. Showing
    only the first is what made the change look a thousandfold.
    """
    data = json.loads((OUTPUT / "fee_change.json").read_text())
    series = data["daily_spread_bps_2026-01-01_2026-03-31"]
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(9.5, 7.2), sharex=True,
                                      gridspec_kw={"height_ratios": [1.15, 1]})
    # Each day is plotted at its noon, so the change at noon on 02-02 falls on
    # that day's point rather than between two days.
    day = lambda s: dt.datetime.fromisoformat(s)
    for market, color, label in (("BITBANK:BTC_SPOT", BTC, "BTC"),
                                 ("BITBANK:XRP_SPOT", XRP, "XRP (control)")):
        rows = series[market]
        dates = [day(r[0]) + dt.timedelta(hours=12) for r in rows]
        for ax, col in ((top, 1), (bottom, 2)):
            ax.plot(dates, [r[col] for r in rows], color=color, linewidth=1.8,
                    marker="o", markersize=2.5, label=label)
    change = dt.datetime(2026, 2, 2, 12)
    selloff = [day(d) for d in data["selloff_excluded"]]
    for ax in (top, bottom):
        for label in data["windows"]:
            lo, hi = label.split()[1].split("..")
            ax.axvspan(day(lo), day(lo[:5] + hi) + dt.timedelta(days=1),
                       color="#0072b2", alpha=0.06, linewidth=0)
        ax.axvspan(selloff[0], selloff[1] + dt.timedelta(days=1), color="#999999",
                   alpha=0.28, linewidth=0)
        ax.axvline(change, color="#d55e00", linestyle="--", linewidth=1.5)
        ax.grid(True, which="both", alpha=0.22)
    top.text(change, 1.02, "Fee change\n(02-02 12:00) ", transform=top.get_xaxis_transform(),
             color="#d55e00", ha="right", va="bottom")
    top.text(selloff[0], 1.02, " Market-wide\n sell-off", transform=top.get_xaxis_transform(),
             color="#666666", ha="left", va="bottom")
    top.set_yscale("log")
    top.set_ylabel("Daily median spread\n(bps, log scale)")
    top.legend(frameon=False, loc="upper left")
    bottom.set_ylim(bottom=0)
    bottom.set_ylabel("Daily mean spread\n(bps)")
    bottom.set_xlabel("Date")
    bottom.xaxis.set_major_locator(mdates.MonthLocator())
    bottom.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.suptitle("bitbank daily spread around the BTC fee change: median vs mean\n"
                 "(light bands: the before, after and March windows)")
    fig.tight_layout()
    finish(fig, "bitbank_fee_change_daily.png")


if __name__ == "__main__":
    gmo_distribution()
    bitbank_daily()
    print("wrote", OUTPUT / "gmo_spread_distribution.png")
    print("wrote", OUTPUT / "bitbank_fee_change_daily.png")
