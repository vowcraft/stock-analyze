from __future__ import annotations

import logging
from datetime import date, datetime
from threading import Lock

import akshare as ak
import pandas as pd


logger = logging.getLogger(__name__)


class AkshareStockService:
    def __init__(self) -> None:
        self._stock_name_cache: dict[str, str] = {}
        self._etf_name_cache: dict[str, str] = {}
        self._trade_dates: set[date] = set()
        self._cache_lock = Lock()

    def get_daily_history(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        adjust: str = "",
    ) -> list[dict[str, object]]:
        frame = self._fetch_daily_history_frame(symbol, start_date, end_date, adjust)
        if frame is None or frame.empty:
            return []
        return _normalize_frame(frame)

    def get_stock_name(self, symbol: str) -> str:
        if self.is_etf(symbol):
            return self.get_etf_name(symbol)

        cached_name = self._stock_name_cache.get(symbol)
        if cached_name:
            return cached_name

        with self._cache_lock:
            cached_name = self._stock_name_cache.get(symbol)
            if cached_name:
                return cached_name
            self._stock_name_cache = self._load_stock_name_cache()
            return self._stock_name_cache.get(symbol, symbol)

    def list_a_share_symbols(self) -> list[str]:
        if not self._stock_name_cache:
            with self._cache_lock:
                if not self._stock_name_cache:
                    self._stock_name_cache = self._load_stock_name_cache()
        return list(self._stock_name_cache.keys())

    def get_etf_name(self, symbol: str) -> str:
        cached_name = self._etf_name_cache.get(symbol)
        if cached_name:
            return cached_name

        with self._cache_lock:
            cached_name = self._etf_name_cache.get(symbol)
            if cached_name:
                return cached_name
            self._etf_name_cache = self._load_etf_name_cache()
            return self._etf_name_cache.get(symbol, symbol)

    def get_realtime_snapshot(self, symbol: str) -> dict[str, object] | None:
        return self.get_realtime_snapshots((symbol,)).get(symbol)

    def get_realtime_snapshots(self, symbols: tuple[str, ...] | list[str]) -> dict[str, dict[str, object]]:
        requested = tuple(dict.fromkeys(str(symbol).strip() for symbol in symbols if str(symbol).strip()))
        if not requested:
            return {}

        results: dict[str, dict[str, object]] = {}
        stock_symbols = [symbol for symbol in requested if not self.is_etf(symbol)]
        etf_symbols = [symbol for symbol in requested if self.is_etf(symbol)]

        if stock_symbols:
            results.update(self._filter_snapshot_frame(ak.stock_zh_a_spot_em(), stock_symbols))
        if etf_symbols:
            results.update(self._filter_snapshot_frame(ak.fund_etf_spot_em(), etf_symbols))

        return results

    def get_market_realtime_snapshot(self, include_etf: bool = False) -> list[dict[str, object]]:
        stock_frame = ak.stock_zh_a_spot_em()
        records = _normalize_frame(stock_frame) if stock_frame is not None and not stock_frame.empty else []
        if not include_etf:
            return records

        etf_frame = ak.fund_etf_spot_em()
        etf_records = _normalize_frame(etf_frame) if etf_frame is not None and not etf_frame.empty else []
        return records + etf_records

    def get_industry_boards(self) -> list[dict[str, object]]:
        frame_getter = getattr(ak, "stock_board_industry_name_em", None)
        if frame_getter is None:
            return []
        try:
            frame = frame_getter()
        except Exception as exc:  # noqa: BLE001
            logger.warning("load industry boards failed: %s", exc)
            return []
        if frame is None or frame.empty:
            return []
        return _normalize_frame(frame)

    def get_concept_boards(self) -> list[dict[str, object]]:
        frame_getter = getattr(ak, "stock_board_concept_name_em", None)
        if frame_getter is None:
            return []
        try:
            frame = frame_getter()
        except Exception as exc:  # noqa: BLE001
            logger.warning("load concept boards failed: %s", exc)
            return []
        if frame is None or frame.empty:
            return []
        return _normalize_frame(frame)

    def get_industry_board_members(self, board_name: str) -> list[dict[str, object]]:
        frame_getter = getattr(ak, "stock_board_industry_cons_em", None)
        if frame_getter is None:
            return []
        try:
            frame = frame_getter(symbol=board_name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("load industry board members failed, board=%s, error=%s", board_name, exc)
            return []
        if frame is None or frame.empty:
            return []
        return _normalize_frame(frame)

    def get_concept_board_members(self, board_name: str) -> list[dict[str, object]]:
        frame_getter = getattr(ak, "stock_board_concept_cons_em", None)
        if frame_getter is None:
            return []
        try:
            frame = frame_getter(symbol=board_name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("load concept board members failed, board=%s, error=%s", board_name, exc)
            return []
        if frame is None or frame.empty:
            return []
        return _normalize_frame(frame)

    def get_limit_up_pool(self, target_day: date) -> list[dict[str, object]]:
        return self._get_zt_pool("stock_zt_pool_em", target_day)

    def get_previous_limit_up_pool(self, target_day: date) -> list[dict[str, object]]:
        return self._get_zt_pool("stock_zt_pool_previous_em", target_day)

    def get_strong_pool(self, target_day: date) -> list[dict[str, object]]:
        return self._get_zt_pool("stock_zt_pool_strong_em", target_day)

    def get_broken_limit_up_pool(self, target_day: date) -> list[dict[str, object]]:
        return self._get_zt_pool("stock_zt_pool_dtgc_em", target_day)

    def is_trading_day(self, target_day: date) -> bool:
        trade_dates = self._trade_dates
        if target_day in trade_dates:
            return True

        with self._cache_lock:
            if target_day in self._trade_dates:
                return True
            self._trade_dates = self._load_trade_dates()
            return target_day in self._trade_dates

    @staticmethod
    def is_trading_time(now: datetime) -> bool:
        current = now.time()
        return (
            current >= datetime.strptime("09:30:00", "%H:%M:%S").time()
            and current < datetime.strptime("11:30:00", "%H:%M:%S").time()
        ) or (
            current >= datetime.strptime("13:00:00", "%H:%M:%S").time()
            and current < datetime.strptime("15:00:00", "%H:%M:%S").time()
        )

    @staticmethod
    def is_etf(symbol: str) -> bool:
        return symbol.startswith(("15", "51", "56", "58"))

    def _load_stock_name_cache(self) -> dict[str, str]:
        frame = ak.stock_info_a_code_name()
        if frame is None or frame.empty:
            return {}
        cache: dict[str, str] = {}
        for _, row in frame.iterrows():
            code = str(row.get("code", "")).strip()
            name = str(row.get("name", "")).strip()
            if code and name:
                cache[code] = name
        return cache

    def _load_etf_name_cache(self) -> dict[str, str]:
        frame = ak.fund_etf_spot_em()
        if frame is None or frame.empty:
            return {}
        cache: dict[str, str] = {}
        for _, row in frame.iterrows():
            code = str(row.get("代码", "")).strip()
            name = str(row.get("名称", "")).strip()
            if code and name:
                cache[code] = name
        return cache

    def _load_trade_dates(self) -> set[date]:
        frame = ak.tool_trade_date_hist_sina()
        if frame is None or frame.empty:
            return set()

        trade_dates: set[date] = set()
        for value in frame["trade_date"].tolist():
            if isinstance(value, date):
                trade_dates.add(value)
            elif hasattr(value, "date"):
                trade_dates.add(value.date())
        return trade_dates

    def _fetch_daily_history_frame(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        adjust: str,
    ) -> pd.DataFrame:
        if self.is_etf(symbol):
            return ak.fund_etf_hist_em(
                symbol=symbol,
                period="daily",
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                adjust=adjust or "",
            )
        return ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            adjust=adjust or "",
        )

    def get_index_history(
        self,
        index_symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, object]]:
        """拉大盘指数日线 (沪深300/创业板指等)。

        akshare.stock_zh_index_daily 不支持区间参数,内部全量拉回后切片。
        返回 records 字段为 akshare 原生英文 (date/open/close/high/low/volume)。
        """
        try:
            frame = ak.stock_zh_index_daily(symbol=index_symbol)
        except Exception as exc:  # noqa: BLE001
            logger.warning("load index history failed, symbol=%s, error=%s", index_symbol, exc)
            return []
        if frame is None or frame.empty:
            return []

        date_column = "date" if "date" in frame.columns else ("日期" if "日期" in frame.columns else None)
        if date_column is not None:
            frame = frame.copy()
            frame[date_column] = pd.to_datetime(frame[date_column], errors="coerce")
            frame = frame.dropna(subset=[date_column])
            if start_date is not None:
                frame = frame[frame[date_column].dt.date >= start_date]
            if end_date is not None:
                frame = frame[frame[date_column].dt.date <= end_date]

        if frame.empty:
            return []
        return _normalize_frame(frame)

    @staticmethod
    def _get_zt_pool(function_name: str, target_day: date) -> list[dict[str, object]]:
        frame_getter = getattr(ak, function_name, None)
        if frame_getter is None:
            return []
        try:
            frame = frame_getter(date=target_day.strftime("%Y%m%d"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("load %s failed, day=%s, error=%s", function_name, target_day, exc)
            return []
        if frame is None or frame.empty:
            return []
        return _normalize_frame(frame)

    @staticmethod
    def build_history_frame(history: list[dict[str, object]]) -> pd.DataFrame:
        if not history:
            return pd.DataFrame()

        frame = pd.DataFrame(history).copy()
        date_column = "日期" if "日期" in frame.columns else "date"
        if date_column in frame.columns:
            frame["日期"] = pd.to_datetime(frame[date_column], errors="coerce")
            frame = frame.dropna(subset=["日期"]).sort_values("日期").reset_index(drop=True)

        numeric_columns = ("开盘", "收盘", "最高", "最低", "成交量", "成交额", "换手率", "涨跌幅")
        for column in numeric_columns:
            if column in frame.columns:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
        return frame

    @staticmethod
    def _filter_snapshot_frame(frame: pd.DataFrame, symbols: list[str]) -> dict[str, dict[str, object]]:
        if frame is None or frame.empty:
            return {}

        normalized_codes = frame["代码"].astype(str).str.strip()
        filtered = frame.loc[normalized_codes.isin(symbols)].copy()
        if filtered.empty:
            return {}

        result: dict[str, dict[str, object]] = {}
        for _, row in filtered.iterrows():
            code = str(row.get("代码", "")).strip()
            if code:
                result[code] = _normalize_record(row.to_dict())
        return result


def _normalize_frame(frame: pd.DataFrame) -> list[dict[str, object]]:
    normalized_rows: list[dict[str, object]] = []
    for record in frame.to_dict(orient="records"):
        normalized_rows.append(_normalize_record(record))
    return normalized_rows


def _normalize_record(record: dict[object, object]) -> dict[str, object]:
    return {str(key): _normalize_value(value) for key, value in record.items()}


def _normalize_value(value: object) -> object:
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except TypeError:
            pass
    if isinstance(value, float):
        return float(value)
    if isinstance(value, (int, str, bool)) or value is None:
        return value
    return str(value)
