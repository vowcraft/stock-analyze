from __future__ import annotations

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.services.market_regime import MarketRegimeService, RegimeSnapshot
from app.services.signal_service import BuySignal, BuySignalService
from app.services.stock_service import AkshareStockService
from app.services.wecom_service import WeComNotifier


logger = logging.getLogger(__name__)
_scheduler = BackgroundScheduler()
_stock_service = AkshareStockService()
_regime_service = MarketRegimeService(_stock_service)
_signal_service = BuySignalService(_stock_service, _regime_service)
_notifier = WeComNotifier()
_signal_sent_at: dict[str, datetime] = {}


def poll_once() -> None:
    now = datetime.now()
    try:
        if not _stock_service.is_trading_day(now.date()):
            logger.info("[%s] skip polling: today is not an A-share trading day", _now_text(now))
            return

        if not _stock_service.is_trading_time(now):
            logger.info("[%s] skip polling: outside A-share trading session", _now_text(now))
            return

        if settings.app_monitor_mode == "symbols":
            _poll_symbols_mode(now)
            return

        _poll_market_buy_mode(now)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[%s] scheduled fetch failed: %s", _now_text(now), exc)


def start_scheduler() -> None:
    if not settings.app_polling_enabled:
        logger.info("stock polling disabled by configuration")
        return
    if _scheduler.running:
        return

    _scheduler.add_job(
        poll_once,
        trigger="interval",
        seconds=settings.app_polling_interval_seconds,
        id="stock-polling",
        replace_existing=True,
        next_run_time=datetime.now(),
    )
    _scheduler.start()
    logger.info(
        "stock polling scheduler started, mode=%s, interval=%ss",
        settings.app_monitor_mode,
        settings.app_polling_interval_seconds,
    )


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("stock polling scheduler stopped")


def _poll_symbols_mode(now: datetime) -> None:
    symbols = settings.app_symbols
    snapshots = _stock_service.get_realtime_snapshots(symbols)
    if not snapshots:
        logger.info("[%s] no realtime snapshots returned for symbols=%s", _now_text(now), ",".join(symbols))
        return

    logger.info("[%s] fetched realtime snapshots for symbols=%s", _now_text(now), ",".join(symbols))
    _notifier.send_text(_build_symbol_message(symbols, snapshots, now))


def _poll_market_buy_mode(now: datetime) -> None:
    signals = _signal_service.scan_market_buy_signals()
    regime_text = _regime_text(_signal_service.last_regime_snapshot)
    if not signals:
        logger.info("[%s] no market buy signals [regime=%s]", _now_text(now), regime_text or "n/a")
        return

    fresh_signals = [signal for signal in signals if _should_send_signal(signal, now)]
    if not fresh_signals:
        logger.info("[%s] all market buy signals are in cooldown", _now_text(now))
        return

    _mark_signals_sent(fresh_signals, now)
    logger.info(
        "[%s] found %s fresh market buy signals [regime=%s]",
        _now_text(now),
        len(fresh_signals),
        regime_text or "n/a",
    )
    _notifier.send_text(
        _build_market_buy_message(fresh_signals, now, _signal_service.last_regime_snapshot)
    )


def _should_send_signal(signal: BuySignal, now: datetime) -> bool:
    last_sent_at = _signal_sent_at.get(signal.symbol)
    if last_sent_at is None:
        return True
    return now - last_sent_at >= timedelta(minutes=settings.app_signal_cooldown_minutes)


def _mark_signals_sent(signals: list[BuySignal], now: datetime) -> None:
    for signal in signals:
        _signal_sent_at[signal.symbol] = now


def _build_symbol_message(symbols: tuple[str, ...], snapshots: dict[str, dict[str, object]], now: datetime) -> str:
    lines = [f"股票监控 {_now_text(now)}"]

    for symbol in symbols:
        snapshot = snapshots.get(symbol)
        if snapshot is None:
            lines.append(f"{symbol}  未获取到实时数据")
            continue

        lines.append(_snapshot_line(symbol, snapshot))
    return "\n".join(lines)


def _build_market_buy_message(
    signals: list[BuySignal],
    now: datetime,
    regime_snapshot: RegimeSnapshot | None = None,
) -> str:
    lines = [f"A股超短信号 {_now_text(now)}"]
    regime_text = _regime_text(regime_snapshot)
    if regime_text:
        lines.append(f"环境:{regime_text}")
    lines.append(f"命中 {len(signals)} 只")
    for index, signal in enumerate(signals, start=1):
        theme_prefix = ""
        if signal.theme_name and signal.theme_name != "全市场":
            theme_prefix = f"[{signal.theme_type}:{signal.theme_name} {signal.board_change_pct:+.2f}%] "
        lines.append(
            (
                f"{index}. {theme_prefix}{signal.symbol} {signal.name} "
                f"现价{_format_number(signal.latest_price)} 涨{_format_percent(signal.change_pct)} "
                f"换{_format_percent(signal.turnover_rate)} 量比{_format_number(signal.volume_ratio)} "
                f"分数{_format_number(signal.score)}"
            )
        )
        if signal.strategy == "leader_momentum":
            lines.append(
                "   "
                f"突破{_format_number(signal.breakout_price)} "
                f"3日动量{_format_percent(signal.recent_3day_return_pct)} "
                f"收近高{_format_number(signal.close_to_high_ratio)} "
                f"放量{_format_number(signal.volume_multiple)}倍"
            )
        else:
            lines.append(
                f"   突破{_format_number(signal.breakout_price)}  "
                f"MA20/60 {_format_number(signal.ma20)}/{_format_number(signal.ma60)}  "
                f"放量{_format_number(signal.volume_multiple)}倍"
            )
    return "\n".join(lines)


def _snapshot_line(symbol: str, snapshot: dict[str, object]) -> str:
    stock_name = _as_text(snapshot.get("名称")) or _stock_service.get_stock_name(symbol)
    latest_price = _format_number(snapshot.get("最新价"))
    change_percent = _format_percent(snapshot.get("涨跌幅"))
    change_amount = _format_signed(snapshot.get("涨跌额"))
    open_price = _first_present(snapshot, "今开", "开盘价")
    high_price = _first_present(snapshot, "最高", "最高价")
    low_price = _first_present(snapshot, "最低", "最低价")
    turnover = _format_amount(snapshot.get("成交额"))
    volume_ratio = _format_number(snapshot.get("量比"))
    turnover_rate = _format_percent(snapshot.get("换手率"))

    details = [
        f"现价 {latest_price}",
        f"涨跌 {change_percent}",
        f"涨额 {change_amount}",
        f"开 {open_price}",
        f"高 {high_price}",
        f"低 {low_price}",
        f"额 {turnover}",
    ]
    if volume_ratio:
        details.append(f"量比 {volume_ratio}")
    if turnover_rate:
        details.append(f"换手 {turnover_rate}")

    return f"{symbol} {stock_name} | " + "  ".join(details)


def _first_present(snapshot: dict[str, object], *keys: str) -> str:
    for key in keys:
        value = snapshot.get(key)
        if value is not None and str(value).strip() != "":
            return _format_number(value)
    return "-"


def _format_number(value: object) -> str:
    number = _to_float(value)
    if number is None:
        return "-"
    return f"{number:.3f}".rstrip("0").rstrip(".")


def _format_percent(value: object) -> str:
    number = _to_float(value)
    if number is None:
        return "-"
    prefix = "+" if number > 0 else ""
    return f"{prefix}{number:.2f}%"


def _format_signed(value: object) -> str:
    number = _to_float(value)
    if number is None:
        return "-"
    prefix = "+" if number > 0 else ""
    return f"{prefix}{number:.3f}".rstrip("0").rstrip(".")


def _format_amount(value: object) -> str:
    number = _to_float(value)
    if number is None:
        return "-"
    absolute = abs(number)
    if absolute >= 100000000:
        return f"{number / 100000000:.2f}亿"
    if absolute >= 10000:
        return f"{number / 10000:.2f}万"
    return f"{number:.0f}"


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _now_text(now: datetime) -> str:
    return now.strftime("%Y-%m-%d %H:%M:%S")


def _regime_text(snapshot: RegimeSnapshot | None) -> str:
    if not settings.app_regime_enabled or snapshot is None:
        return ""
    return f"{snapshot.regime.label_zh()}({snapshot.regime.value} {snapshot.return_pct:+.2f}%)"
