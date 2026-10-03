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
    data = json.loads((OUTPUT / "fee_change.json").read_text())
    series = data["daily_spread_bps_2026-01-01_2026-03-31"]
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    for market, color, label in (("BITBANK:BTC_SPOT", BTC, "BTC"),
                                 ("BITBANK:XRP_SPOT", XRP, "XRP (control)")):
        rows = series[market]
        dates = [dt.date.fromisoformat(d) for d, _ in rows]
        ax.plot(dates, [v for _, v in rows], color=color, linewidth=1.8,
                marker="o", markersize=2.5, label=label)
    change = dt.date(2026, 2, 5)
    ax.axvline(change, color="#d55e00", linestyle="--", linewidth=1.5)
    ax.annotate("Fee change", xy=(change, 0.7), xytext=(dt.date(2026, 2, 10), 0.003),
                color="#d55e00", arrowprops={"arrowstyle": "->", "color": "#d55e00"})
    ax.set_yscale("log")
    ax.set_ylabel("Daily median spread (bps, log scale)")
    ax.set_xlabel("Date")
    ax.set_title("bitbank daily spread around the BTC fee change")
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.grid(True, which="both", alpha=0.22)
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    finish(fig, "bitbank_fee_change_daily.png")


if __name__ == "__main__":
    gmo_distribution()
    bitbank_daily()
    print("wrote", OUTPUT / "gmo_spread_distribution.png")
    print("wrote", OUTPUT / "bitbank_fee_change_daily.png")
