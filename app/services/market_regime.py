from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

import pandas as pd

from app.config import settings
from app.services.stock_service import AkshareStockService


logger = logging.getLogger(__name__)


class Regime(str, Enum):
    RISK_ON = "risk_on"
    NEUTRAL = "neutral"
    RISK_OFF = "risk_off"

    def label_zh(self) -> str:
        return {
            Regime.RISK_ON: "激进",
            Regime.NEUTRAL: "中性",
            Regime.RISK_OFF: "防御",
        }.get(self, "中性")


@dataclass(frozen=True)
class RegimeSnapshot:
    regime: Regime
    index_symbol: str
    lookback_days: int
    return_pct: float
    classified_at: datetime

    @property
    def is_degraded(self) -> bool:
        return self.return_pct == 0.0 and self.regime == Regime.NEUTRAL


class MarketRegimeService:
    def __init__(
        self,
        stock_service: AkshareStockService | None = None,
        ttl_seconds: int = 300,
    ) -> None:
        self._stock_service = stock_service or AkshareStockService()
        self._ttl_seconds = ttl_seconds
        self._cache_snapshot: RegimeSnapshot | None = None
        self._cache_expires_at: float = 0.0

    def classify(self, now: datetime | None = None) -> RegimeSnapshot:
        if self._cache_snapshot is not None and time.time() < self._cache_expires_at:
            return self._cache_snapshot

        snapshot = self._compute_snapshot(now or datetime.now())
        self._cache_snapshot = snapshot
        self._cache_expires_at = time.time() + self._ttl_seconds
        return snapshot

    def invalidate_cache(self) -> None:
        self._cache_snapshot = None
        self._cache_expires_at = 0.0

    def classify_for_date(
        self,
        target_date: date,
        index_records: list[dict[str, object]] | None = None,
    ) -> RegimeSnapshot:
        """回测专用:逐日判定 regime。

        index_records 可由调用方预先拉好传入,避免在循环里反复 IO。
        """
        index_symbol = settings.app_regime_index_symbol
        lookback = settings.app_regime_lookback_days
        classified_at = datetime.combine(target_date, datetime.min.time())

        records = index_records
        if records is None:
            try:
                records = self._stock_service.get_index_history(index_symbol)
            except Exception as exc:  # noqa: BLE001
                logger.warning("regime classify_for_date failed to fetch index history: %s", exc)
                return _neutral_snapshot(index_symbol, lookback, classified_at)

        return_pct = _compute_return_pct_at(records, target_date, lookback)
        if return_pct is None:
            return _neutral_snapshot(index_symbol, lookback, classified_at)

        regime = _classify_by_return(
            return_pct=return_pct,
            on_threshold=settings.app_regime_risk_on_threshold,
            off_threshold=settings.app_regime_risk_off_threshold,
        )
        return RegimeSnapshot(
            regime=regime,
            index_symbol=index_symbol,
            lookback_days=lookback,
            return_pct=return_pct,
            classified_at=classified_at,
        )

    def _compute_snapshot(self, now: datetime) -> RegimeSnapshot:
        index_symbol = settings.app_regime_index_symbol
        lookback = settings.app_regime_lookback_days

        try:
            records = self._stock_service.get_index_history(index_symbol)
        except Exception as exc:  # noqa: BLE001
            logger.warning("regime classify failed to fetch index history: %s", exc)
            return _neutral_snapshot(index_symbol, lookback, now)

        return_pct = _compute_return_pct(records, lookback)
        if return_pct is None:
            logger.warning(
                "regime classify: insufficient index data (symbol=%s, lookback=%d)",
                index_symbol,
                lookback,
            )
            return _neutral_snapshot(index_symbol, lookback, now)

        regime = _classify_by_return(
            return_pct=return_pct,
            on_threshold=settings.app_regime_risk_on_threshold,
            off_threshold=settings.app_regime_risk_off_threshold,
        )
        return RegimeSnapshot(
            regime=regime,
            index_symbol=index_symbol,
            lookback_days=lookback,
            return_pct=return_pct,
            classified_at=now,
        )


def _neutral_snapshot(index_symbol: str, lookback: int, now: datetime) -> RegimeSnapshot:
    return RegimeSnapshot(
        regime=Regime.NEUTRAL,
        index_symbol=index_symbol,
        lookback_days=lookback,
        return_pct=0.0,
        classified_at=now,
    )


def _compute_return_pct(records: list[dict[str, object]], lookback_days: int) -> float | None:
    if not records:
        return None
    frame = pd.DataFrame(records)
    if frame.empty:
        return None

    date_column = "date" if "date" in frame.columns else ("日期" if "日期" in frame.columns else None)
    close_column = "close" if "close" in frame.columns else ("收盘" if "收盘" in frame.columns else None)
    if date_column is None or close_column is None:
        return None

    frame = frame.copy()
    frame[date_column] = pd.to_datetime(frame[date_column], errors="coerce")
    frame[close_column] = pd.to_numeric(frame[close_column], errors="coerce")
    frame = frame.dropna(subset=[date_column, close_column]).sort_values(date_column).reset_index(drop=True)
    if frame.empty or len(frame) < lookback_days + 1:
        return None

    tail = frame.tail(lookback_days + 1)
    base_close = float(tail.iloc[0][close_column])
    last_close = float(tail.iloc[-1][close_column])
    if base_close <= 0:
        return None
    return (last_close - base_close) / base_close * 100.0


def _compute_return_pct_at(
    records: list[dict[str, object]],
    target_date: date,
    lookback_days: int,
) -> float | None:
    """给定 records 和 target_date,计算 target_date 当日的 lookback_days 涨幅 (用于回测)。"""
    if not records:
        return None
    frame = pd.DataFrame(records)
    if frame.empty:
        return None

    date_column = "date" if "date" in frame.columns else ("日期" if "日期" in frame.columns else None)
    close_column = "close" if "close" in frame.columns else ("收盘" if "收盘" in frame.columns else None)
    if date_column is None or close_column is None:
        return None

    frame = frame.copy()
    frame[date_column] = pd.to_datetime(frame[date_column], errors="coerce")
    frame[close_column] = pd.to_numeric(frame[close_column], errors="coerce")
    frame = frame.dropna(subset=[date_column, close_column]).sort_values(date_column).reset_index(drop=True)
    if frame.empty:
        return None

    date_series = frame[date_column].dt.date
    eligible_index = frame.index[date_series <= target_date]
    if len(eligible_index) == 0:
        return None
    target_idx = int(eligible_index[-1])
    if target_idx < lookback_days:
        return None

    base_close = float(frame.iloc[target_idx - lookback_days][close_column])
    last_close = float(frame.iloc[target_idx][close_column])
    if base_close <= 0:
        return None
    return (last_close - base_close) / base_close * 100.0


def _classify_by_return(*, return_pct: float, on_threshold: float, off_threshold: float) -> Regime:
    if return_pct >= on_threshold:
        return Regime.RISK_ON
    if return_pct <= off_threshold:
        return Regime.RISK_OFF
    return Regime.NEUTRAL
