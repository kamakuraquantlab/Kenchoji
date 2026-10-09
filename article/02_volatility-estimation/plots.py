"""Render the three figures used in the article from its checked-in JSON.

No market data is read here. Run the measurement scripts first when the JSON
needs refreshing, then run ``python plots.py``.

Reproduces: §3, §5.1, §6. Writes output/signature_plot.png,
output/response_by_horizon.png, and output/bitbank_btc_vol_history.png.
"""
import json
import pathlib

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


HERE = pathlib.Path(__file__).parent
OUTPUT = HERE / "output"
ASSETS = ("BTC", "ETH", "XRP")
# One entry per venue. GMO runs two books per asset, spot (`*_SPOT`) and
# leverage (`*_JPY`), with different fees, so they are separate venues here.
VENUES = {
    "BINANCE": ("Binance", "#e69f00"),
    "BITBANK": ("bitbank", "#0072b2"),
    "COINCHECK": ("Coincheck", "#009e73"),
    "GMO_SPOT": ("GMO spot", "#d55e00"),
    "GMO_LEV": ("GMO leverage", "#cc79a7"),
}
INTERVAL_TICKS = ([10, 30, 60, 300, 600, 1800], ["10s", "30s", "1m", "5m", "10m", "30m"])


def venue_of(market):
    exchange, symbol = market.split(":")
    asset, kind = symbol.split("_")
    if exchange == "GMO":
        exchange = "GMO_SPOT" if kind == "SPOT" else "GMO_LEV"
    return exchange, asset


def finish(fig, name):
    fig.savefig(OUTPUT / name, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def venue_legend(fig, venues, extra=()):
    handles = [Line2D([0], [0], color=VENUES[v][1], linewidth=2, label=VENUES[v][0])
               for v in venues] + list(extra)
    fig.legend(handles=handles, frameon=False, loc="lower center",
               ncol=len(handles), bbox_to_anchor=(0.5, -0.01))


def signature_plot():
    data = json.loads((OUTPUT / "vol.json").read_text())
    # Linear axes on purpose: from 10 seconds up the curves move by 5-20%, and
    # a log scale would flatten exactly the part worth seeing.
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.3))
    for ax, asset in zip(axes, ASSETS):
        for market, row in data.items():
            if market.startswith("_"):
                continue
            venue, found_asset = venue_of(market)
            if found_asset != asset:
                continue
            values = row["rv_bps_mid_by_interval_sec"]
            x = sorted(int(k) for k in values)
            ax.plot(x, [values[str(k)] for k in x], marker="o", markersize=3,
                    linewidth=2.4 if venue == "BINANCE" else 1.6,
                    color=VENUES[venue][1], zorder=3 if venue == "BINANCE" else 2)
        ax.set_title(asset)
        ax.set_xscale("log")
        ax.set_xticks(*INTERVAL_TICKS)
        ax.minorticks_off()
        ax.grid(True, alpha=0.25)
        ax.set_xlabel("Sampling interval")
    axes[0].set_ylabel("Realized volatility (bps/day)")
    venue_legend(fig, VENUES)
    fig.suptitle("Volatility signature by market")
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    finish(fig, "signature_plot.png")


def response_plot():
    data = json.loads((OUTPUT / "response.json").read_text())
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.3), sharex=True, sharey=True)
    for ax, asset in zip(axes, ASSETS):
        for market, row in data.items():
            venue, found_asset = venue_of(market)
            if found_asset != asset:
                continue
            values = row["by_horizon_sec"]
            x = sorted(int(k) for k in values)
            color = VENUES[venue][1]
            ax.plot(x, [values[str(k)]["beta"] for k in x], color=color,
                    marker="o", markersize=3, linewidth=1.8)
            ax.plot(x, [values[str(k)]["r2"] for k in x], color=color,
                    marker="o", markersize=3, linewidth=1.5, linestyle="--")
        ax.set_title(asset)
        ax.set_xscale("log")
        ax.set_xticks([10, 30, 60, 300, 600], ["10s", "30s", "1m", "5m", "10m"])
        ax.minorticks_off()
        ax.set_ylim(0.4, 1.0)
        ax.grid(True, alpha=0.25)
        ax.set_xlabel("Return horizon")
    axes[0].set_ylabel("Coefficient")
    metric_handles = [Line2D([0], [0], color="#444444", linewidth=2, label="beta"),
                      Line2D([0], [0], color="#444444", linewidth=2,
                             linestyle="--", label="R-squared")]
    venue_legend(fig, [v for v in VENUES if v != "BINANCE"], metric_handles)
    fig.suptitle("Domestic response to Binance moves")
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    finish(fig, "response_by_horizon.png")


def vol_history_plot():
    data = json.loads((OUTPUT / "vol_history.json").read_text())["BITBANK:BTC_SPOT"]
    months = list(data)
    rv10 = [data[m]["rv_bps_by_interval_sec"]["10"] for m in months]
    rv1800 = [data[m]["rv_bps_by_interval_sec"]["1800"] for m in months]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    x = range(len(months))
    ax.plot(x, rv1800, color="#0072b2", marker="o", linewidth=2, label="30-minute RV")
    ax.plot(x, rv10, color="#56b4e9", marker="o", linewidth=2, label="10-second RV")
    ax.fill_between(x, rv10, rv1800, color="#0072b2", alpha=0.10)
    change = months.index("2026-02")
    ax.axvline(change, color="#d55e00", linestyle="--", linewidth=1.5)
    ax.text(change + 0.15, 15, "Fee change", color="#d55e00", va="bottom")
    ax.set_ylim(0, max(rv1800) * 1.08)
    ax.set_ylabel("Realized volatility (bps/day)")
    ax.set_xlabel("Month")
    ax.set_title("bitbank BTC: 10-second vs 30-minute RV by month")
    ax.set_xticks(list(x)[::2], months[::2], rotation=35, ha="right")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    finish(fig, "bitbank_btc_vol_history.png")


if __name__ == "__main__":
    signature_plot()
    response_plot()
    vol_history_plot()
    for name in ("signature_plot", "response_by_horizon", "bitbank_btc_vol_history"):
        print("wrote", OUTPUT / f"{name}.png")
