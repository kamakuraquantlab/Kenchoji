"""Render the three figures used in the article from its checked-in JSON.

No market data is read here. Run the measurement scripts first when the JSON
needs refreshing, then run ``python plots.py``.

Reproduces: §3, §5.1, §6. Writes output/signature_plot.png,
output/response_by_horizon.png, and output/bitbank_btc_spread_history.png.
"""
import json
import pathlib

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


HERE = pathlib.Path(__file__).parent
OUTPUT = HERE / "output"
EXCHANGES = ("BINANCE", "BITBANK", "COINCHECK", "GMO")
ASSETS = ("BTC", "ETH", "XRP")
COLORS = {
    "BINANCE": "#e69f00",
    "BITBANK": "#0072b2",
    "COINCHECK": "#009e73",
    "GMO": "#cc79a7",
}


def market_label(market):
    exchange, symbol = market.split(":")
    return exchange, symbol.split("_")[0]


def finish(fig, name):
    fig.savefig(OUTPUT / name, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def signature_plot():
    data = json.loads((OUTPUT / "vol.json").read_text())
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), sharey=True)
    for ax, asset in zip(axes, ASSETS):
        for market, row in data.items():
            if market.startswith("_"):
                continue
            exchange, found_asset = market_label(market)
            if found_asset != asset:
                continue
            values = row["rv_bps_mid_by_interval_sec"]
            x = sorted(int(k) for k in values)
            ax.plot(x, [values[str(k)] for k in x], marker="o", markersize=3,
                    linewidth=1.8, color=COLORS[exchange], label=exchange.title())
        ax.set_title(asset)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xticks([1, 10, 60, 300, 1800], ["1s", "10s", "1m", "5m", "30m"])
        ax.grid(True, which="both", alpha=0.22)
        ax.set_xlabel("Sampling interval")
    axes[0].set_ylabel("Realized volatility (bps/day)")
    axes[-1].legend(frameon=False, loc="upper right")
    fig.suptitle("Volatility signature by market")
    fig.tight_layout()
    finish(fig, "signature_plot.png")


def response_plot():
    data = json.loads((OUTPUT / "response.json").read_text())
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), sharex=True, sharey=True)
    for ax, asset in zip(axes, ASSETS):
        for market, row in data.items():
            exchange, found_asset = market_label(market)
            if found_asset != asset:
                continue
            values = row["by_horizon_sec"]
            x = sorted(int(k) for k in values)
            color = COLORS[exchange]
            ax.plot(x, [values[str(k)]["beta"] for k in x], color=color,
                    marker="o", markersize=3, linewidth=1.8)
            ax.plot(x, [values[str(k)]["r2"] for k in x], color=color,
                    marker="o", markersize=3, linewidth=1.5, linestyle="--")
        ax.set_title(asset)
        ax.set_xscale("log")
        ax.set_xticks([1, 5, 15, 60, 300], ["1s", "5s", "15s", "1m", "5m"])
        ax.set_ylim(-0.03, 1.03)
        ax.grid(True, which="both", alpha=0.22)
        ax.set_xlabel("Return horizon")
    axes[0].set_ylabel("Coefficient")
    exchange_handles = [Line2D([0], [0], color=COLORS[e], linewidth=2,
                               label=e.title()) for e in EXCHANGES[1:]]
    metric_handles = [Line2D([0], [0], color="#444444", linewidth=2,
                             label="beta"),
                      Line2D([0], [0], color="#444444", linewidth=2,
                             linestyle="--", label="R-squared")]
    fig.legend(handles=exchange_handles + metric_handles, frameon=False,
               loc="lower center", ncol=5, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle("Domestic response to Binance moves")
    fig.tight_layout(rect=(0, 0.09, 1, 1))
    finish(fig, "response_by_horizon.png")


def spread_history_plot():
    data = json.loads((OUTPUT / "spread_history.json").read_text())
    values = data["BITBANK:BTC_SPOT"]
    months = list(values)
    y = list(values.values())
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(months, y, color=COLORS["BITBANK"], marker="o", linewidth=2)
    change = months.index("2026-02")
    ax.axvline(change, color="#d55e00", linestyle="--", linewidth=1.5)
    ax.annotate("Fee change", xy=(change, y[change]), xytext=(change + 0.5, 0.035),
                color="#d55e00", arrowprops={"arrowstyle": "->", "color": "#d55e00"})
    ax.set_yscale("log")
    ax.set_ylabel("Median spread (bps, log scale)")
    ax.set_xlabel("Month")
    ax.set_title("bitbank BTC spread by month")
    ax.set_xticks(range(0, len(months), 2), months[::2], rotation=35, ha="right")
    ax.grid(True, which="both", alpha=0.22)
    fig.tight_layout()
    finish(fig, "bitbank_btc_spread_history.png")


if __name__ == "__main__":
    signature_plot()
    response_plot()
    spread_history_plot()
    print("wrote", OUTPUT / "signature_plot.png")
    print("wrote", OUTPUT / "response_by_horizon.png")
    print("wrote", OUTPUT / "bitbank_btc_spread_history.png")
