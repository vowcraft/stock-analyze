from __future__ import annotations

import time
from datetime import date, timedelta
from unittest.mock import MagicMock

from app.services.market_regime import (
    MarketRegimeService,
    Regime,
    _classify_by_return,
    _compute_return_pct,
    _compute_return_pct_at,
)


def _build_index_records(
    close_prices: list[float],
    start_date: date = date(2026, 1, 1),
) -> list[dict[str, object]]:
    """生成 akshare.stock_zh_index_daily 风格的测试 records (date/close 字段)。"""
    records: list[dict[str, object]] = []
    for i, close in enumerate(close_prices):
        d = start_date + timedelta(days=i)
        records.append(
            {
                "date": d.isoformat(),
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": 1_000_000,
            }
        )
    return records


class TestClassifyByReturn:
    """纯函数 _classify_by_return 的边界测试。"""

    def test_above_on_threshold_is_risk_on(self) -> None:
        assert _classify_by_return(return_pct=5.5, on_threshold=5.0, off_threshold=-3.0) == Regime.RISK_ON

    def test_exact_on_threshold_is_risk_on(self) -> None:
        assert _classify_by_return(return_pct=5.0, on_threshold=5.0, off_threshold=-3.0) == Regime.RISK_ON

    def test_below_off_threshold_is_risk_off(self) -> None:
        assert _classify_by_return(return_pct=-3.5, on_threshold=5.0, off_threshold=-3.0) == Regime.RISK_OFF

    def test_exact_off_threshold_is_risk_off(self) -> None:
        assert _classify_by_return(return_pct=-3.0, on_threshold=5.0, off_threshold=-3.0) == Regime.RISK_OFF

    def test_between_thresholds_is_neutral(self) -> None:
        assert _classify_by_return(return_pct=1.0, on_threshold=5.0, off_threshold=-3.0) == Regime.NEUTRAL
        assert _classify_by_return(return_pct=0.0, on_threshold=5.0, off_threshold=-3.0) == Regime.NEUTRAL
        assert _classify_by_return(return_pct=-2.9, on_threshold=5.0, off_threshold=-3.0) == Regime.NEUTRAL
        assert _classify_by_return(return_pct=4.99, on_threshold=5.0, off_threshold=-3.0) == Regime.NEUTRAL


class TestComputeReturnPct:
    def test_normal_20day_return(self) -> None:
        # 21 个点,首 100,末 105 → 20 日涨幅 +5%
        records = _build_index_records([100.0] + [100.0] * 19 + [105.0])
        pct = _compute_return_pct(records, lookback_days=20)
        assert pct is not None
        assert abs(pct - 5.0) < 1e-6

    def test_insufficient_data_returns_none(self) -> None:
        # 只有 20 个点,不够 21 (需要 lookback+1 行才能取首末)
        records = _build_index_records([100.0] * 20)
        assert _compute_return_pct(records, lookback_days=20) is None

    def test_empty_records_returns_none(self) -> None:
        assert _compute_return_pct([], lookback_days=20) is None

    def test_zero_base_close_returns_none(self) -> None:
        records = _build_index_records([0.0] + [100.0] * 20)
        assert _compute_return_pct(records, lookback_days=20) is None


class TestComputeReturnPctAt:
    def test_returns_correct_return_for_target_date(self) -> None:
        # 21 个点,首 100,末 110 → +10%
        records = _build_index_records([100.0] * 20 + [110.0])
        target = date(2026, 1, 21)
        pct = _compute_return_pct_at(records, target, lookback_days=20)
        assert pct is not None
        assert abs(pct - 10.0) < 1e-6

    def test_target_after_last_record_uses_last_available(self) -> None:
        # target 在 records 最后一日之后,应该用最后一日作为锚
        records = _build_index_records([100.0] * 20 + [110.0])
        target = date(2026, 2, 1)  # records 之后 11 天
        pct = _compute_return_pct_at(records, target, lookback_days=20)
        assert pct is not None
        assert abs(pct - 10.0) < 1e-6

    def test_target_before_any_data_returns_none(self) -> None:
        records = _build_index_records([100.0] * 20 + [110.0])
        target = date(2025, 12, 1)
        assert _compute_return_pct_at(records, target, lookback_days=20) is None


class TestMarketRegimeService:
    def _service_with(self, records: list[dict[str, object]]) -> tuple[MarketRegimeService, MagicMock]:
        stock_service = MagicMock()
        stock_service.get_index_history.return_value = records
        return MarketRegimeService(stock_service=stock_service, ttl_seconds=300), stock_service

    def test_risk_on(self) -> None:
        records = _build_index_records([100.0] * 20 + [106.0])  # +6%
        service, stock_service = self._service_with(records)

        snap = service.classify()

        assert snap.regime == Regime.RISK_ON
        assert abs(snap.return_pct - 6.0) < 1e-6
        assert snap.lookback_days == 20
        assert snap.index_symbol == "sh000300"
        stock_service.get_index_history.assert_called_once_with("sh000300")

    def test_risk_off(self) -> None:
        records = _build_index_records([100.0] * 20 + [96.0])  # -4%
        service, _ = self._service_with(records)

        snap = service.classify()

        assert snap.regime == Regime.RISK_OFF
        assert abs(snap.return_pct - (-4.0)) < 1e-6

    def test_neutral(self) -> None:
        records = _build_index_records([100.0] * 20 + [101.0])  # +1%
        service, _ = self._service_with(records)

        snap = service.classify()

        assert snap.regime == Regime.NEUTRAL
        assert abs(snap.return_pct - 1.0) < 1e-6

    def test_akshare_exception_falls_back_to_neutral(self) -> None:
        stock_service = MagicMock()
        stock_service.get_index_history.side_effect = RuntimeError("akshare timeout")
        service = MarketRegimeService(stock_service=stock_service, ttl_seconds=300)

        snap = service.classify()

        assert snap.regime == Regime.NEUTRAL
        assert snap.return_pct == 0.0
        assert snap.is_degraded

    def test_insufficient_data_falls_back_to_neutral(self) -> None:
        # 只有 15 个点 (< lookback+1=21)
        records = _build_index_records([100.0] * 15)
        service, _ = self._service_with(records)

        snap = service.classify()

        assert snap.regime == Regime.NEUTRAL
        assert snap.return_pct == 0.0
        assert snap.is_degraded

    def test_ttl_cache_returns_same_snapshot(self) -> None:
        records = _build_index_records([100.0] * 20 + [110.0])
        service, stock_service = self._service_with(records)

        snap1 = service.classify()
        snap2 = service.classify()

        assert snap1 is snap2  # 同一对象 (缓存命中)
        stock_service.get_index_history.assert_called_once()

    def test_invalidate_cache_recomputes(self) -> None:
        records = _build_index_records([100.0] * 20 + [110.0])
        service, stock_service = self._service_with(records)

        snap1 = service.classify()
        service.invalidate_cache()
        snap2 = service.classify()

        assert snap1 is not snap2
        assert stock_service.get_index_history.call_count == 2

    def test_expired_ttl_recomputes(self) -> None:
        records = _build_index_records([100.0] * 20 + [110.0])
        service, stock_service = self._service_with(records)

        service._cache_expires_at = time.time() - 1  # 强制过期
        snap = service.classify()

        assert snap.regime == Regime.RISK_ON
        assert stock_service.get_index_history.call_count == 1

    def test_classify_for_date_with_prefetched_records(self) -> None:
        records = _build_index_records([100.0] * 20 + [110.0])
        service, stock_service = self._service_with(records)

        snap = service.classify_for_date(date(2026, 1, 21), index_records=records)

        assert snap.regime == Regime.RISK_ON
        # stock_service 不应被额外调用,因为传入了 records
        stock_service.get_index_history.assert_not_called()

    def test_classify_for_date_fetches_when_records_missing(self) -> None:
        records = _build_index_records([100.0] * 20 + [110.0])
        service, stock_service = self._service_with(records)

        snap = service.classify_for_date(date(2026, 1, 21))

        assert snap.regime == Regime.RISK_ON
        stock_service.get_index_history.assert_called_once_with("sh000300")


class TestRegimeLabel:
    def test_label_zh(self) -> None:
        assert Regime.RISK_ON.label_zh() == "激进"
        assert Regime.NEUTRAL.label_zh() == "中性"
        assert Regime.RISK_OFF.label_zh() == "防御"
