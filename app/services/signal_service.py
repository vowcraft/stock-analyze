from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from app.config import settings
from app.services.stock_service import AkshareStockService


@dataclass(frozen=True)
class BuySignal:
    symbol: str
    name: str
    signal_date: date
    latest_price: float
    change_pct: float
    turnover_rate: float
    volume_ratio: float
    amount: float
    breakout_price: float
    ma20: float
    ma60: float
    volume_multiple: float
    score: float
    strategy: str
    theme_type: str
    theme_name: str
    board_change_pct: float
    close_to_high_ratio: float
    close_in_range_ratio: float
    recent_3day_return_pct: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class BacktestSignalResult:
    signal: BuySignal
    forward_returns: dict[int, float | None]
    max_forward_return: float | None


class BuySignalService:
    def __init__(self, stock_service: AkshareStockService | None = None) -> None:
        self._stock_service = stock_service or AkshareStockService()

    def scan_market_buy_signals(self) -> list[BuySignal]:
        if settings.app_signal_strategy == "breakout":
            return self._scan_breakout_signals()
        return self._scan_leader_momentum_signals()

    def backtest_buy_signals(
        self,
        symbols: list[str] | tuple[str, ...],
        start_date: date,
        end_date: date,
    ) -> list[BacktestSignalResult]:
        normalized_symbols = [str(symbol).strip() for symbol in symbols if str(symbol).strip()]
        if not normalized_symbols:
            return []

        results: list[BacktestSignalResult] = []
        for symbol in normalized_symbols:
            results.extend(self._backtest_symbol(symbol, start_date, end_date))

        results.sort(key=lambda item: (item.signal.signal_date, item.signal.score), reverse=True)
        return results

    def summarize_backtest(self, results: list[BacktestSignalResult]) -> dict[str, object]:
        summary: dict[str, object] = {
            "signalCount": len(results),
            "avgReturns": {},
            "winRates": {},
            "maxForwardReturn": None,
            "symbols": len({item.signal.symbol for item in results}),
            "strategy": settings.app_signal_strategy,
        }
        if not results:
            return summary

        avg_returns: dict[int, float] = {}
        win_rates: dict[int, float] = {}
        best_return: float | None = None

        for horizon in settings.app_backtest_forward_days:
            values = [item.forward_returns.get(horizon) for item in results if item.forward_returns.get(horizon) is not None]
            if not values:
                continue
            avg_returns[horizon] = sum(values) / len(values)
            win_rates[horizon] = sum(1 for value in values if value > 0) / len(values)

        for item in results:
            value = item.max_forward_return
            if value is None:
                continue
            if best_return is None or value > best_return:
                best_return = value

        summary["avgReturns"] = avg_returns
        summary["winRates"] = win_rates
        summary["maxForwardReturn"] = best_return
        return summary

    def _scan_leader_momentum_signals(self) -> list[BuySignal]:
        snapshots = self._stock_service.get_market_realtime_snapshot(include_etf=False)
        if not snapshots:
            return []

        snapshot_map = _build_snapshot_map(snapshots)
        broken_symbols = {
            _normalize_symbol(item.get("代码"))
            for item in self._stock_service.get_broken_limit_up_pool(date.today())
            if _normalize_symbol(item.get("代码"))
        }

        pool_signals = self._collect_priority_pool_signals(snapshot_map, broken_symbols)
        board_signals = self._collect_board_signals(snapshot_map, broken_symbols)
        merged = self._merge_signals(pool_signals + board_signals)
        if merged:
            merged.sort(key=lambda item: item.score, reverse=True)
            return merged[: settings.app_signal_top_n]

        return self._scan_breakout_signals(snapshot_map=snapshot_map)

    def _scan_breakout_signals(self, snapshot_map: dict[str, dict[str, object]] | None = None) -> list[BuySignal]:
        snapshot_map = snapshot_map or _build_snapshot_map(self._stock_service.get_market_realtime_snapshot(include_etf=False))
        candidates = self._build_breakout_candidates(snapshot_map)
        if not candidates:
            return []

        signals: list[BuySignal] = []
        for snapshot in candidates[: settings.app_signal_scan_limit]:
            signal = self._build_breakout_signal(snapshot)
            if signal is not None:
                signals.append(signal)

        signals.sort(key=lambda item: item.score, reverse=True)
        return signals[: settings.app_signal_top_n]

    def _collect_priority_pool_signals(
        self,
        snapshot_map: dict[str, dict[str, object]],
        broken_symbols: set[str],
    ) -> list[BuySignal]:
        signals: list[BuySignal] = []
        signals.extend(
            self._scan_special_pool(
                pool_name="strong_pool",
                theme_name="强势股池",
                records=self._stock_service.get_strong_pool(date.today()),
                snapshot_map=snapshot_map,
                broken_symbols=broken_symbols,
            )
        )
        signals.extend(
            self._scan_special_pool(
                pool_name="previous_limit_up",
                theme_name="昨日涨停池",
                records=self._stock_service.get_previous_limit_up_pool(date.today()),
                snapshot_map=snapshot_map,
                broken_symbols=broken_symbols,
            )
        )
        signals.extend(
            self._scan_special_pool(
                pool_name="limit_up_pool",
                theme_name="涨停池",
                records=self._stock_service.get_limit_up_pool(date.today()),
                snapshot_map=snapshot_map,
                broken_symbols=broken_symbols,
            )
        )
        return signals

    def _collect_board_signals(
        self,
        snapshot_map: dict[str, dict[str, object]],
        broken_symbols: set[str],
    ) -> list[BuySignal]:
        board_signals: list[BuySignal] = []
        board_signals.extend(
            self._scan_theme_members(
                board_type="industry",
                boards=self._rank_boards(self._stock_service.get_industry_boards(), settings.app_leader_top_industry_boards),
                member_fetcher=self._stock_service.get_industry_board_members,
                snapshot_map=snapshot_map,
                broken_symbols=broken_symbols,
            )
        )
        board_signals.extend(
            self._scan_theme_members(
                board_type="concept",
                boards=self._rank_boards(self._stock_service.get_concept_boards(), settings.app_leader_top_concept_boards),
                member_fetcher=self._stock_service.get_concept_board_members,
                snapshot_map=snapshot_map,
                broken_symbols=broken_symbols,
            )
        )
        return self._merge_signals(board_signals)

    def _merge_signals(self, signals: list[BuySignal]) -> list[BuySignal]:
        deduped: dict[str, BuySignal] = {}
        for signal in signals:
            existing = deduped.get(signal.symbol)
            if existing is None or signal.score > existing.score:
                deduped[signal.symbol] = signal
        return list(deduped.values())

    def _rank_boards(self, boards: list[dict[str, object]], top_n: int) -> list[dict[str, object]]:
        ranked: list[dict[str, object]] = []
        for board in boards:
            name = _as_text(_first_present_value(board, "板块名称", "名称"))
            change_pct = _to_float(_first_present_value(board, "涨跌幅", "涨跌幅(%)"))
            if not name or change_pct is None:
                continue
            if change_pct < settings.app_leader_min_board_change_pct:
                continue
            board_copy = dict(board)
            board_copy["_board_name"] = name
            board_copy["_board_change_pct"] = change_pct
            ranked.append(board_copy)

        ranked.sort(
            key=lambda item: (
                _to_float(item.get("_board_change_pct")) or 0.0,
                _to_float(_first_present_value(item, "总市值", "成交额", "上涨家数")) or 0.0,
            ),
            reverse=True,
        )
        return ranked[:top_n]

    def _scan_theme_members(
        self,
        *,
        board_type: str,
        boards: list[dict[str, object]],
        member_fetcher,
        snapshot_map: dict[str, dict[str, object]],
        broken_symbols: set[str],
    ) -> list[BuySignal]:
        signals: list[BuySignal] = []
        for board in boards:
            board_name = _as_text(board.get("_board_name"))
            board_change_pct = _to_float(board.get("_board_change_pct")) or 0.0
            members = member_fetcher(board_name)
            candidates = self._rank_theme_candidates(members, snapshot_map, broken_symbols)
            count = 0
            for snapshot in candidates:
                signal = self._build_leader_signal(
                    snapshot=snapshot,
                    theme_type=board_type,
                    theme_name=board_name,
                    board_change_pct=board_change_pct,
                )
                if signal is None:
                    continue
                signals.append(signal)
                count += 1
                if count >= settings.app_leader_max_signals_per_theme:
                    break
        return signals

    def _rank_theme_candidates(
        self,
        members: list[dict[str, object]],
        snapshot_map: dict[str, dict[str, object]],
        broken_symbols: set[str],
    ) -> list[dict[str, object]]:
        candidates: list[dict[str, object]] = []
        for member in members:
            symbol = _normalize_symbol(_first_present_value(member, "代码", "证券代码"))
            if not symbol:
                continue
            if symbol in broken_symbols:
                continue
            snapshot = snapshot_map.get(symbol)
            if snapshot is None:
                continue
            if not _is_realtime_candidate(snapshot):
                continue

            candidates.append(snapshot)

        candidates.sort(
            key=lambda item: (
                _to_float(item.get("涨跌幅")) or 0.0,
                _to_float(item.get("成交额")) or 0.0,
                _to_float(item.get("换手率")) or 0.0,
                _to_float(item.get("量比")) or 0.0,
            ),
            reverse=True,
        )
        return candidates

    def _scan_special_pool(
        self,
        *,
        pool_name: str,
        theme_name: str,
        records: list[dict[str, object]],
        snapshot_map: dict[str, dict[str, object]],
        broken_symbols: set[str],
    ) -> list[BuySignal]:
        if not records:
            return []

        ranked_records = sorted(
            records,
            key=lambda item: (
                _to_float(_first_present_value(item, "涨跌幅", "涨跌幅(%)")) or 0.0,
                _to_float(_first_present_value(item, "成交额", "成交额(百万)")) or 0.0,
                _to_float(_first_present_value(item, "换手率")) or 0.0,
            ),
            reverse=True,
        )

        results: list[BuySignal] = []
        for record in ranked_records:
            symbol = _normalize_symbol(_first_present_value(record, "代码", "证券代码"))
            if not symbol or symbol in broken_symbols:
                continue
            snapshot = snapshot_map.get(symbol)
            if snapshot is None or not _is_realtime_candidate(snapshot):
                continue
            signal = self._build_leader_signal(
                snapshot=snapshot,
                theme_type="pool",
                theme_name=theme_name,
                board_change_pct=0.0,
            )
            if signal is None:
                continue

            bonus_score = 6.0 if pool_name == "strong_pool" else 4.0 if pool_name == "previous_limit_up" else 3.0
            results.append(
                BuySignal(
                    symbol=signal.symbol,
                    name=signal.name,
                    signal_date=signal.signal_date,
                    latest_price=signal.latest_price,
                    change_pct=signal.change_pct,
                    turnover_rate=signal.turnover_rate,
                    volume_ratio=signal.volume_ratio,
                    amount=signal.amount,
                    breakout_price=signal.breakout_price,
                    ma20=signal.ma20,
                    ma60=signal.ma60,
                    volume_multiple=signal.volume_multiple,
                    score=signal.score + bonus_score,
                    strategy=signal.strategy,
                    theme_type="pool",
                    theme_name=theme_name,
                    board_change_pct=0.0,
                    close_to_high_ratio=signal.close_to_high_ratio,
                    close_in_range_ratio=signal.close_in_range_ratio,
                    recent_3day_return_pct=signal.recent_3day_return_pct,
                    reasons=(f"{theme_name}优先级加权",) + signal.reasons,
                )
            )
            if len(results) >= settings.app_leader_max_signals_per_pool:
                break
        return results

    def _build_leader_signal(
        self,
        *,
        snapshot: dict[str, object],
        theme_type: str,
        theme_name: str,
        board_change_pct: float,
    ) -> BuySignal | None:
        signal = self._build_signal_from_snapshot(snapshot, strategy="leader_momentum")
        if signal is None:
            return None

        if signal.change_pct < settings.app_leader_min_change_pct or signal.change_pct > settings.app_leader_max_change_pct:
            return None
        if signal.turnover_rate < settings.app_leader_min_turnover_rate:
            return None
        if signal.volume_ratio < settings.app_leader_min_volume_ratio:
            return None
        if signal.volume_multiple < settings.app_leader_min_volume_multiple:
            return None
        if signal.amount < settings.app_leader_min_amount:
            return None
        if signal.latest_price < settings.app_leader_min_price:
            return None
        if signal.close_to_high_ratio < settings.app_leader_min_close_to_high_ratio:
            return None
        if signal.close_in_range_ratio < settings.app_leader_min_close_in_range_ratio:
            return None
        if signal.recent_3day_return_pct < settings.app_leader_min_3day_return_pct:
            return None

        speed = _to_float(snapshot.get("涨速"))
        if speed is not None and speed < settings.app_leader_min_speed:
            return None

        leader_score = _score_leader_signal(
            change_pct=signal.change_pct,
            turnover_rate=signal.turnover_rate,
            volume_ratio=signal.volume_ratio,
            volume_multiple=signal.volume_multiple,
            board_change_pct=board_change_pct,
            close_to_high_ratio=signal.close_to_high_ratio,
            close_in_range_ratio=signal.close_in_range_ratio,
            recent_3day_return_pct=signal.recent_3day_return_pct,
            speed=speed or settings.app_leader_min_speed,
        )
        reasons = (
            f"{theme_type}主线 {theme_name} {board_change_pct:.2f}%",
            f"近{settings.app_signal_breakout_lookback_days}日突破 {signal.breakout_price:.2f}",
            f"量价强势 量比{signal.volume_ratio:.2f} 放量{signal.volume_multiple:.2f}倍",
            f"收近高位 {signal.close_to_high_ratio:.3f}",
            f"3日动量 {signal.recent_3day_return_pct:.2f}%",
        )
        return BuySignal(
            symbol=signal.symbol,
            name=signal.name,
            signal_date=signal.signal_date,
            latest_price=signal.latest_price,
            change_pct=signal.change_pct,
            turnover_rate=signal.turnover_rate,
            volume_ratio=signal.volume_ratio,
            amount=signal.amount,
            breakout_price=signal.breakout_price,
            ma20=signal.ma20,
            ma60=signal.ma60,
            volume_multiple=signal.volume_multiple,
            score=leader_score,
            strategy="leader_momentum",
            theme_type=theme_type,
            theme_name=theme_name,
            board_change_pct=board_change_pct,
            close_to_high_ratio=signal.close_to_high_ratio,
            close_in_range_ratio=signal.close_in_range_ratio,
            recent_3day_return_pct=signal.recent_3day_return_pct,
            reasons=reasons,
        )

    def _build_breakout_candidates(self, snapshot_map: dict[str, dict[str, object]]) -> list[dict[str, object]]:
        candidates: list[dict[str, object]] = []
        for snapshot in snapshot_map.values():
            if not _is_realtime_candidate(snapshot):
                continue
            latest_price = _to_float(snapshot.get("最新价"))
            change_pct = _to_float(snapshot.get("涨跌幅"))
            amount = _to_float(snapshot.get("成交额"))
            turnover_rate = _to_float(snapshot.get("换手率"))
            volume_ratio = _to_float(snapshot.get("量比"))

            if latest_price is None or latest_price < settings.app_signal_min_price:
                continue
            if change_pct is None or change_pct < settings.app_signal_min_change_pct:
                continue
            if change_pct > settings.app_signal_max_change_pct:
                continue
            if amount is None or amount < settings.app_signal_min_amount:
                continue
            if turnover_rate is None or turnover_rate < settings.app_signal_min_turnover_rate:
                continue
            if volume_ratio is None or volume_ratio < settings.app_signal_min_volume_ratio:
                continue
            candidates.append(snapshot)

        candidates.sort(
            key=lambda item: (
                _to_float(item.get("量比")) or 0.0,
                _to_float(item.get("换手率")) or 0.0,
                _to_float(item.get("涨跌幅")) or 0.0,
            ),
            reverse=True,
        )
        return candidates

    def _build_breakout_signal(self, snapshot: dict[str, object]) -> BuySignal | None:
        signal = self._build_signal_from_snapshot(snapshot, strategy="breakout")
        if signal is None:
            return None
        if signal.latest_price <= signal.breakout_price:
            return None
        if signal.latest_price <= signal.ma20 or signal.latest_price <= signal.ma60:
            return None
        if signal.volume_multiple < settings.app_signal_min_volume_multiple:
            return None
        score = _score_breakout_signal(
            change_pct=signal.change_pct,
            turnover_rate=signal.turnover_rate,
            volume_ratio=signal.volume_ratio,
            volume_multiple=signal.volume_multiple,
            breakout_distance=(signal.latest_price - signal.breakout_price) / signal.breakout_price if signal.breakout_price else 0.0,
            ma20_distance=(signal.latest_price - signal.ma20) / signal.ma20 if signal.ma20 else 0.0,
            ma60_distance=(signal.latest_price - signal.ma60) / signal.ma60 if signal.ma60 else 0.0,
        )
        return BuySignal(
            symbol=signal.symbol,
            name=signal.name,
            signal_date=signal.signal_date,
            latest_price=signal.latest_price,
            change_pct=signal.change_pct,
            turnover_rate=signal.turnover_rate,
            volume_ratio=signal.volume_ratio,
            amount=signal.amount,
            breakout_price=signal.breakout_price,
            ma20=signal.ma20,
            ma60=signal.ma60,
            volume_multiple=signal.volume_multiple,
            score=score,
            strategy="breakout",
            theme_type="market",
            theme_name="全市场",
            board_change_pct=0.0,
            close_to_high_ratio=signal.close_to_high_ratio,
            close_in_range_ratio=signal.close_in_range_ratio,
            recent_3day_return_pct=signal.recent_3day_return_pct,
            reasons=(
                f"突破{settings.app_signal_breakout_lookback_days}日高点 {signal.breakout_price:.2f}",
                f"站上MA20/MA60 {signal.ma20:.2f}/{signal.ma60:.2f}",
                f"放量 {signal.volume_multiple:.2f}倍",
                f"换手 {signal.turnover_rate:.2f}%",
                f"量比 {signal.volume_ratio:.2f}",
            ),
        )

    def _build_signal_from_snapshot(self, snapshot: dict[str, object], strategy: str) -> BuySignal | None:
        symbol = _normalize_symbol(snapshot.get("代码"))
        name = _as_text(snapshot.get("名称")) or self._stock_service.get_stock_name(symbol)
        latest_price = _to_float(snapshot.get("最新价"))
        change_pct = _to_float(snapshot.get("涨跌幅"))
        turnover_rate = _to_float(snapshot.get("换手率")) or 0.0
        volume_ratio = _to_float(snapshot.get("量比")) or 0.0
        amount = _to_float(snapshot.get("成交额")) or 0.0
        high_price = _to_float(_first_present_value(snapshot, "最高", "最高价"))
        low_price = _to_float(_first_present_value(snapshot, "最低", "最低价"))
        speed = _to_float(snapshot.get("涨速"))

        if not symbol or latest_price is None or change_pct is None:
            return None

        history = self._stock_service.get_daily_history(
            symbol,
            start_date=_shift_days(settings.app_signal_history_days + 30),
            end_date=date.today(),
            adjust=settings.app_signal_adjust,
        )
        frame = self._stock_service.build_history_frame(history)
        if frame.empty or len(frame) < max(60, settings.app_signal_breakout_lookback_days + 5):
            return None

        feature_row = _prepare_history_features(frame)
        if feature_row is None:
            return None

        breakout_price = _to_float(feature_row.get("breakout_high"))
        ma20 = _to_float(feature_row.get("ma20"))
        ma60 = _to_float(feature_row.get("ma60"))
        volume_multiple = _to_float(feature_row.get("volume_multiple"))
        recent_3day_return_pct = _to_float(feature_row.get("ret_3"))
        if None in {breakout_price, ma20, ma60, volume_multiple, recent_3day_return_pct}:
            return None

        if high_price is None:
            high_price = max(latest_price, _to_float(feature_row.get("high")) or latest_price)
        if low_price is None:
            low_price = min(latest_price, _to_float(feature_row.get("low")) or latest_price)

        close_to_high_ratio = latest_price / high_price if high_price and high_price > 0 else 0.0
        day_range = high_price - low_price if high_price is not None and low_price is not None else 0.0
        close_in_range_ratio = (latest_price - low_price) / day_range if day_range > 0 else 0.0

        signal_day = pd.Timestamp(feature_row["日期"]).date()
        return BuySignal(
            symbol=symbol,
            name=name,
            signal_date=signal_day,
            latest_price=latest_price,
            change_pct=change_pct,
            turnover_rate=turnover_rate,
            volume_ratio=volume_ratio,
            amount=amount,
            breakout_price=breakout_price,
            ma20=ma20,
            ma60=ma60,
            volume_multiple=volume_multiple,
            score=0.0,
            strategy=strategy,
            theme_type="market",
            theme_name="全市场",
            board_change_pct=0.0,
            close_to_high_ratio=close_to_high_ratio,
            close_in_range_ratio=close_in_range_ratio,
            recent_3day_return_pct=recent_3day_return_pct,
            reasons=(f"涨速 {speed:.2f}" if speed is not None else "",),
        )

    def _backtest_symbol(self, symbol: str, start_date: date, end_date: date) -> list[BacktestSignalResult]:
        history = self._stock_service.get_daily_history(
            symbol,
            start_date=_shift_days_from(start_date, 120),
            end_date=end_date,
            adjust=settings.app_signal_adjust,
        )
        frame = self._stock_service.build_history_frame(history)
        if frame.empty or len(frame) < max(90, settings.app_signal_breakout_lookback_days + 10):
            return []

        frame = _prepare_history_features_frame(frame)
        if frame.empty:
            return []

        stock_name = self._stock_service.get_stock_name(symbol)
        signals: list[BacktestSignalResult] = []
        last_signal_index = -10_000
        for index, row in frame.iterrows():
            signal_date = pd.Timestamp(row["日期"]).date()
            if signal_date < start_date or signal_date > end_date:
                continue
            if index - last_signal_index < settings.app_backtest_signal_cooldown_days:
                continue

            if settings.app_signal_strategy == "breakout":
                signal = _build_backtest_breakout_signal(symbol, stock_name, row)
            else:
                signal = _build_backtest_leader_signal(symbol, stock_name, row)
            if signal is None:
                continue

            last_signal_index = index
            forward_returns = _calc_forward_returns(frame, index, float(row["收盘"]))
            realized_returns = [value for value in forward_returns.values() if value is not None]
            signals.append(
                BacktestSignalResult(
                    signal=signal,
                    forward_returns=forward_returns,
                    max_forward_return=max(realized_returns) if realized_returns else None,
                )
            )
        return signals


def _build_backtest_breakout_signal(symbol: str, stock_name: str, row: pd.Series) -> BuySignal | None:
    if not _match_breakout_row(row):
        return None
    return BuySignal(
        symbol=symbol,
        name=stock_name,
        signal_date=pd.Timestamp(row["日期"]).date(),
        latest_price=float(row["收盘"]),
        change_pct=float(row["涨跌幅"]),
        turnover_rate=float(row["换手率"]) if pd.notna(row["换手率"]) else 0.0,
        volume_ratio=settings.app_signal_min_volume_ratio,
        amount=float(row["成交额"]) if pd.notna(row["成交额"]) else 0.0,
        breakout_price=float(row["breakout_high"]),
        ma20=float(row["ma20"]),
        ma60=float(row["ma60"]),
        volume_multiple=float(row["volume_multiple"]),
        score=_score_breakout_signal(
            change_pct=float(row["涨跌幅"]),
            turnover_rate=float(row["换手率"]) if pd.notna(row["换手率"]) else settings.app_signal_min_turnover_rate,
            volume_ratio=settings.app_signal_min_volume_ratio,
            volume_multiple=float(row["volume_multiple"]),
            breakout_distance=float(row["breakout_distance"]),
            ma20_distance=float(row["ma20_distance"]),
            ma60_distance=float(row["ma60_distance"]),
        ),
        strategy="breakout",
        theme_type="market",
        theme_name="全市场",
        board_change_pct=0.0,
        close_to_high_ratio=float(row["close_to_high_ratio"]),
        close_in_range_ratio=float(row["close_in_range_ratio"]),
        recent_3day_return_pct=float(row["ret_3"]),
        reasons=("突破型回测样本",),
    )


def _build_backtest_leader_signal(symbol: str, stock_name: str, row: pd.Series) -> BuySignal | None:
    if not _match_leader_row(row):
        return None
    score = _score_leader_signal(
        change_pct=float(row["涨跌幅"]),
        turnover_rate=float(row["换手率"]) if pd.notna(row["换手率"]) else settings.app_leader_min_turnover_rate,
        volume_ratio=settings.app_leader_min_volume_ratio,
        volume_multiple=float(row["volume_multiple"]),
        board_change_pct=0.0,
        close_to_high_ratio=float(row["close_to_high_ratio"]),
        close_in_range_ratio=float(row["close_in_range_ratio"]),
        recent_3day_return_pct=float(row["ret_3"]),
        speed=settings.app_leader_min_speed,
    )
    return BuySignal(
        symbol=symbol,
        name=stock_name,
        signal_date=pd.Timestamp(row["日期"]).date(),
        latest_price=float(row["收盘"]),
        change_pct=float(row["涨跌幅"]),
        turnover_rate=float(row["换手率"]) if pd.notna(row["换手率"]) else 0.0,
        volume_ratio=settings.app_leader_min_volume_ratio,
        amount=float(row["成交额"]) if pd.notna(row["成交额"]) else 0.0,
        breakout_price=float(row["breakout_high"]),
        ma20=float(row["ma20"]),
        ma60=float(row["ma60"]),
        volume_multiple=float(row["volume_multiple"]),
        score=score,
        strategy="leader_momentum",
        theme_type="market",
        theme_name="历史回测",
        board_change_pct=0.0,
        close_to_high_ratio=float(row["close_to_high_ratio"]),
        close_in_range_ratio=float(row["close_in_range_ratio"]),
        recent_3day_return_pct=float(row["ret_3"]),
        reasons=("超短龙头动量回测样本",),
    )


def _prepare_history_features(frame: pd.DataFrame) -> pd.Series | None:
    enriched = _prepare_history_features_frame(frame)
    if enriched.empty:
        return None
    return enriched.iloc[-1]


def _prepare_history_features_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame

    enriched = frame.copy()
    enriched["close"] = pd.to_numeric(enriched["收盘"], errors="coerce")
    enriched["open"] = pd.to_numeric(enriched["开盘"], errors="coerce")
    enriched["high"] = pd.to_numeric(enriched["最高"], errors="coerce")
    enriched["low"] = pd.to_numeric(enriched["最低"], errors="coerce")
    enriched["volume"] = pd.to_numeric(enriched["成交量"], errors="coerce")
    enriched["amount"] = pd.to_numeric(enriched["成交额"], errors="coerce")
    enriched["ma20"] = enriched["close"].rolling(20).mean()
    enriched["ma60"] = enriched["close"].rolling(60).mean()
    enriched["vol5"] = enriched["volume"].rolling(5).mean()
    enriched["breakout_high"] = (
        enriched["high"].shift(1).rolling(settings.app_signal_breakout_lookback_days).max()
    )
    enriched["volume_multiple"] = enriched["volume"] / enriched["vol5"]
    enriched["breakout_distance"] = (enriched["close"] - enriched["breakout_high"]) / enriched["breakout_high"]
    enriched["ma20_distance"] = (enriched["close"] - enriched["ma20"]) / enriched["ma20"]
    enriched["ma60_distance"] = (enriched["close"] - enriched["ma60"]) / enriched["ma60"]
    enriched["ret_3"] = enriched["close"].pct_change(3) * 100.0
    enriched["close_to_high_ratio"] = enriched["close"] / enriched["high"]
    intraday_range = enriched["high"] - enriched["low"]
    enriched["close_in_range_ratio"] = (enriched["close"] - enriched["low"]) / intraday_range.replace(0, pd.NA)

    return enriched.dropna(
        subset=[
            "日期",
            "close",
            "ma20",
            "ma60",
            "vol5",
            "breakout_high",
            "volume_multiple",
            "breakout_distance",
            "ma20_distance",
            "ma60_distance",
            "ret_3",
            "close_to_high_ratio",
            "close_in_range_ratio",
        ]
    ).reset_index(drop=True)


def _build_snapshot_map(records: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for record in records:
        symbol = _normalize_symbol(record.get("代码"))
        if symbol:
            result[symbol] = record
    return result


def _is_realtime_candidate(snapshot: dict[str, object]) -> bool:
    symbol = _normalize_symbol(snapshot.get("代码"))
    name = _as_text(snapshot.get("名称"))
    if not symbol or not name:
        return False
    if settings.app_signal_exclude_st and "ST" in name.upper():
        return False
    if symbol.startswith(("4", "8")):
        return False
    return True


def _match_breakout_row(row: pd.Series) -> bool:
    close_price = _to_float(row.get("收盘"))
    change_pct = _to_float(row.get("涨跌幅"))
    turnover_rate = _to_float(row.get("换手率"))
    amount = _to_float(row.get("成交额"))
    breakout_high = _to_float(row.get("breakout_high"))
    ma20 = _to_float(row.get("ma20"))
    ma60 = _to_float(row.get("ma60"))
    volume_multiple = _to_float(row.get("volume_multiple"))

    if None in {close_price, change_pct, breakout_high, ma20, ma60, volume_multiple}:
        return False
    if close_price < settings.app_signal_min_price:
        return False
    if change_pct < settings.app_signal_min_change_pct or change_pct > settings.app_signal_max_change_pct:
        return False
    if close_price <= breakout_high or close_price <= ma20 or close_price <= ma60:
        return False
    if volume_multiple < settings.app_signal_min_volume_multiple:
        return False
    if amount is not None and amount < settings.app_signal_min_amount:
        return False
    if turnover_rate is not None and turnover_rate < settings.app_signal_min_turnover_rate:
        return False
    return True


def _match_leader_row(row: pd.Series) -> bool:
    close_price = _to_float(row.get("收盘"))
    change_pct = _to_float(row.get("涨跌幅"))
    turnover_rate = _to_float(row.get("换手率"))
    amount = _to_float(row.get("成交额"))
    volume_multiple = _to_float(row.get("volume_multiple"))
    breakout_high = _to_float(row.get("breakout_high"))
    ma20 = _to_float(row.get("ma20"))
    ma60 = _to_float(row.get("ma60"))
    close_to_high_ratio = _to_float(row.get("close_to_high_ratio"))
    close_in_range_ratio = _to_float(row.get("close_in_range_ratio"))
    ret_3 = _to_float(row.get("ret_3"))

    if None in {
        close_price,
        change_pct,
        amount,
        volume_multiple,
        breakout_high,
        ma20,
        ma60,
        close_to_high_ratio,
        close_in_range_ratio,
        ret_3,
    }:
        return False
    if close_price < settings.app_leader_min_price:
        return False
    if change_pct < settings.app_leader_min_change_pct or change_pct > settings.app_leader_max_change_pct:
        return False
    if turnover_rate is not None and turnover_rate < settings.app_leader_min_turnover_rate:
        return False
    if amount < settings.app_leader_min_amount:
        return False
    if close_price <= breakout_high or close_price <= ma20 or close_price <= ma60:
        return False
    if volume_multiple < settings.app_leader_min_volume_multiple:
        return False
    if close_to_high_ratio < settings.app_leader_min_close_to_high_ratio:
        return False
    if close_in_range_ratio < settings.app_leader_min_close_in_range_ratio:
        return False
    if ret_3 < settings.app_leader_min_3day_return_pct:
        return False
    return True


def _calc_forward_returns(frame: pd.DataFrame, index: int, base_price: float) -> dict[int, float | None]:
    returns: dict[int, float | None] = {}
    for horizon in settings.app_backtest_forward_days:
        target_index = index + horizon
        if target_index >= len(frame):
            returns[horizon] = None
            continue
        future_close = _to_float(frame.iloc[target_index]["收盘"])
        if future_close is None or base_price <= 0:
            returns[horizon] = None
            continue
        returns[horizon] = (future_close - base_price) / base_price * 100.0
    return returns


def _score_breakout_signal(
    *,
    change_pct: float,
    turnover_rate: float,
    volume_ratio: float,
    volume_multiple: float,
    breakout_distance: float,
    ma20_distance: float,
    ma60_distance: float,
) -> float:
    return round(
        change_pct * 1.6
        + turnover_rate * 0.8
        + volume_ratio * 2.0
        + volume_multiple * 2.4
        + breakout_distance * 100.0 * 1.8
        + ma20_distance * 100.0 * 0.6
        + ma60_distance * 100.0 * 0.6,
        2,
    )


def _score_leader_signal(
    *,
    change_pct: float,
    turnover_rate: float,
    volume_ratio: float,
    volume_multiple: float,
    board_change_pct: float,
    close_to_high_ratio: float,
    close_in_range_ratio: float,
    recent_3day_return_pct: float,
    speed: float,
) -> float:
    return round(
        change_pct * 1.8
        + turnover_rate * 0.9
        + volume_ratio * 2.0
        + volume_multiple * 2.0
        + board_change_pct * 2.2
        + close_to_high_ratio * 10.0
        + close_in_range_ratio * 8.0
        + recent_3day_return_pct * 0.7
        + speed * 3.0,
        2,
    )


def _shift_days(days: int) -> date:
    return date.today() - pd.Timedelta(days=days)


def _shift_days_from(value: date, days: int) -> date:
    return value - pd.Timedelta(days=days)


def _first_present_value(record: dict[str, object], *keys: str) -> object | None:
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        if isinstance(value, str) and value.strip() == "":
            continue
        return value
    return None


def _normalize_symbol(value: object) -> str:
    text = _as_text(value).strip()
    if not text:
        return ""
    if "." in text:
        text = text.split(".")[0]
    return text.zfill(6) if text.isdigit() else text


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
