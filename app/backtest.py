from __future__ import annotations

import argparse
import json
from datetime import datetime

from app.services.signal_service import BuySignalService
from app.services.stock_service import AkshareStockService


def main() -> None:
    parser = argparse.ArgumentParser(description="A-share buy signal backtest")
    parser.add_argument("--symbols", default="", help="comma-separated stock symbols; empty means all A shares")
    parser.add_argument("--start", required=True, help="start date, e.g. 2026-01-01")
    parser.add_argument("--end", required=True, help="end date, e.g. 2026-06-30")
    parser.add_argument("--top", type=int, default=20, help="show top N recent backtest signals")
    args = parser.parse_args()

    start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end, "%Y-%m-%d").date()

    stock_service = AkshareStockService()
    signal_service = BuySignalService(stock_service)

    symbols = _parse_symbols(args.symbols)
    if not symbols:
        symbols = stock_service.list_a_share_symbols()

    results = signal_service.backtest_buy_signals(symbols, start_date, end_date)
    summary = signal_service.summarize_backtest(results)

    print("=== Backtest Summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print()
    print("=== Recent Signals ===")
    for item in results[: args.top]:
        forward_text = ", ".join(
            f"{horizon}d={_format_return(item.forward_returns.get(horizon))}" for horizon in sorted(item.forward_returns)
        )
        print(
            f"{item.signal.signal_date} {item.signal.symbol} {item.signal.name} "
            f"close={item.signal.latest_price:.2f} score={item.signal.score:.2f} {forward_text}"
        )


def _parse_symbols(raw: str) -> list[str]:
    return [item.strip() for item in raw.replace(";", ",").split(",") if item.strip()]


def _format_return(value: float | None) -> str:
    if value is None:
        return "-"
    prefix = "+" if value > 0 else ""
    return f"{prefix}{value:.2f}%"


if __name__ == "__main__":
    main()
