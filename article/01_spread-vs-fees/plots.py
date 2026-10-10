"""Render the two article figures from the checked-in measurement JSON.

Run ``python plots.py`` after ``analysis.py`` and ``fee_change.py``.

Reproduces: §2, §3. Writes output/gmo_spread_distribution.png and
output/bitbank_fee_change_weekly.png.
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


def bitbank_weekly():
    """Weekly mean spread, BTC against XRP, November 2025 to June 2026.

    Weeks run Thursday to Wednesday so the market-wide sell-off of 02-05..02-11
    is one point. Hollow markers are weeks the archive holds fewer than five
    days of. The flat segments are the before and after windows' averages.
    """
    data = json.loads((OUTPUT / "fee_change.json").read_text())
    day = dt.date.fromisoformat
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    for market, color, label in (("BITBANK:BTC_SPOT", BTC, "BTC"),
                                 ("BITBANK:XRP_SPOT", XRP, "XRP (control, fee unchanged)")):
        rows = data["weekly"][market]
        mid = [day(w) + dt.timedelta(days=3) for w, _, _ in rows]
        vals = [v for _, _, v in rows]
        # A week the archive holds no day of breaks the line rather than being
        # bridged by it, so a straight segment never stands in for a missing week.
        line_x, line_y = [], []
        for i, (x, v) in enumerate(zip(mid, vals)):
            if i and (x - mid[i - 1]).days > 7:
                line_x.append(mid[i - 1] + dt.timedelta(days=7))
                line_y.append(float("nan"))
            line_x.append(x)
            line_y.append(v)
        ax.plot(line_x, line_y, color=color, linewidth=1.8, label=label, zorder=2)
        for x, (_, n, v) in zip(mid, rows):
            ax.plot(x, v, marker="o", markersize=4.5, color=color,
                    markerfacecolor=color if n >= 5 else "white", zorder=3)
        for name, w in data["windows"].items():
            lo, hi = name.split()[1].split("..")
            ax.plot([day(lo), day(hi)], [w[market]["spread_mean_bps"]] * 2, color=color,
                    linestyle=":", linewidth=1.4, alpha=0.8, zorder=1)
    change = dt.datetime(2026, 2, 2, 12)
    ax.axvline(change, color="#d55e00", linestyle="--", linewidth=1.5)
    ax.text(change, 0.97, "Fee change \n(2026-02-02) ", transform=ax.get_xaxis_transform(),
            color="#d55e00", ha="right", va="top")
    sell = day(data["selloff_week"]) + dt.timedelta(days=3)
    peak = next(v for w, _, v in data["weekly"]["BITBANK:BTC_SPOT"] if w == data["selloff_week"])
    ax.annotate("Global sell-off week\n(02-05..02-11)", xy=(sell, peak),
                xytext=(sell + dt.timedelta(days=14), peak + 0.25), color="#444444",
                arrowprops={"arrowstyle": "->", "color": "#444444"})
    ax.set_ylim(0, 2.3)
    ax.set_ylabel("Weekly mean spread (bps)")
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.grid(True, alpha=0.22)
    ax.legend(frameon=False, loc="lower left")
    ax.set_title("bitbank weekly mean spread around the BTC fee change")
    fig.tight_layout()
    finish(fig, "bitbank_fee_change_weekly.png")


if __name__ == "__main__":
    gmo_distribution()
    bitbank_weekly()
    print("wrote", OUTPUT / "gmo_spread_distribution.png")
    print("wrote", OUTPUT / "bitbank_fee_change_weekly.png")
