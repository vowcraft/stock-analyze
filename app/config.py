from __future__ import annotations

import os
from dataclasses import dataclass


def _read_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _read_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _read_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _read_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip()


@dataclass(frozen=True)
class Settings:
    app_host: str
    app_port: int
    app_log_level: str
    app_symbol: str
    app_symbols: tuple[str, ...]
    app_monitor_mode: str
    app_polling_enabled: bool
    app_polling_interval_seconds: int
    app_polling_lookback_days: int
    app_signal_adjust: str
    app_signal_strategy: str
    app_signal_top_n: int
    app_signal_scan_limit: int
    app_signal_cooldown_minutes: int
    app_signal_history_days: int
    app_signal_breakout_lookback_days: int
    app_signal_min_price: float
    app_signal_min_change_pct: float
    app_signal_max_change_pct: float
    app_signal_min_turnover_rate: float
    app_signal_min_volume_ratio: float
    app_signal_min_volume_multiple: float
    app_signal_min_amount: float
    app_signal_exclude_st: bool
    app_leader_top_industry_boards: int
    app_leader_top_concept_boards: int
    app_leader_max_signals_per_theme: int
    app_leader_max_signals_per_pool: int
    app_leader_min_board_change_pct: float
    app_leader_min_change_pct: float
    app_leader_max_change_pct: float
    app_leader_min_turnover_rate: float
    app_leader_min_volume_ratio: float
    app_leader_min_volume_multiple: float
    app_leader_min_amount: float
    app_leader_min_price: float
    app_leader_min_speed: float
    app_leader_min_close_to_high_ratio: float
    app_leader_min_close_in_range_ratio: float
    app_leader_min_3day_return_pct: float
    app_backtest_forward_days: tuple[int, ...]
    app_backtest_signal_cooldown_days: int
    wecom_callback_path: str
    wecom_callback_receive_id: str
    wecom_callback_token: str
    wecom_callback_encoding_aes_key: str
    wecom_webhook_url: str | None
    wecom_webhook_key: str | None
    wecom_webhook_base_url: str
    wecom_api_base_url: str
    wecom_corp_id: str
    wecom_corp_secret: str
    wecom_agent_id: str
    wecom_to_user: str | None
    wecom_to_party: str | None
    wecom_to_tag: str | None
    db_enabled: bool
    db_host: str | None
    db_port: int | None
    db_user: str | None
    db_password: str | None
    db_name: str | None
    db_ssl_mode: str
    db_connect_timeout: int


def load_settings() -> Settings:
    corp_id = _read_str("WECOM_CORP_ID", "wwad4729df5fff92cf")
    symbols = _read_symbols(
        "APP_SYMBOLS",
        ("000725", "515120", "159530", "002653"),
        legacy_name="APP_SYMBOL",
    )
    return Settings(
        app_host=_read_str("APP_HOST", "0.0.0.0"),
        app_port=_read_int("APP_PORT", 80),
        app_log_level=_read_str("APP_LOG_LEVEL", "INFO"),
        app_symbol=symbols[0],
        app_symbols=symbols,
        app_monitor_mode=_read_str("APP_MONITOR_MODE", "market_buy"),
        app_polling_enabled=_read_bool("APP_POLLING_ENABLED", True),
        app_polling_interval_seconds=_read_int("APP_POLLING_INTERVAL_SECONDS", 60),
        app_polling_lookback_days=_read_int("APP_POLLING_LOOKBACK_DAYS", 20),
        app_signal_adjust=_read_str("APP_SIGNAL_ADJUST", "qfq"),
        app_signal_strategy=_read_str("APP_SIGNAL_STRATEGY", "leader_momentum"),
        app_signal_top_n=_read_int("APP_SIGNAL_TOP_N", 10),
        app_signal_scan_limit=_read_int("APP_SIGNAL_SCAN_LIMIT", 40),
        app_signal_cooldown_minutes=_read_int("APP_SIGNAL_COOLDOWN_MINUTES", 120),
        app_signal_history_days=_read_int("APP_SIGNAL_HISTORY_DAYS", 120),
        app_signal_breakout_lookback_days=_read_int("APP_SIGNAL_BREAKOUT_LOOKBACK_DAYS", 20),
        app_signal_min_price=_read_float("APP_SIGNAL_MIN_PRICE", 3.0),
        app_signal_min_change_pct=_read_float("APP_SIGNAL_MIN_CHANGE_PCT", 2.0),
        app_signal_max_change_pct=_read_float("APP_SIGNAL_MAX_CHANGE_PCT", 9.8),
        app_signal_min_turnover_rate=_read_float("APP_SIGNAL_MIN_TURNOVER_RATE", 3.0),
        app_signal_min_volume_ratio=_read_float("APP_SIGNAL_MIN_VOLUME_RATIO", 1.8),
        app_signal_min_volume_multiple=_read_float("APP_SIGNAL_MIN_VOLUME_MULTIPLE", 1.5),
        app_signal_min_amount=_read_float("APP_SIGNAL_MIN_AMOUNT", 100000000.0),
        app_signal_exclude_st=_read_bool("APP_SIGNAL_EXCLUDE_ST", True),
        app_leader_top_industry_boards=_read_int("APP_LEADER_TOP_INDUSTRY_BOARDS", 3),
        app_leader_top_concept_boards=_read_int("APP_LEADER_TOP_CONCEPT_BOARDS", 5),
        app_leader_max_signals_per_theme=_read_int("APP_LEADER_MAX_SIGNALS_PER_THEME", 2),
        app_leader_max_signals_per_pool=_read_int("APP_LEADER_MAX_SIGNALS_PER_POOL", 3),
        app_leader_min_board_change_pct=_read_float("APP_LEADER_MIN_BOARD_CHANGE_PCT", 1.5),
        app_leader_min_change_pct=_read_float("APP_LEADER_MIN_CHANGE_PCT", 3.0),
        app_leader_max_change_pct=_read_float("APP_LEADER_MAX_CHANGE_PCT", 9.8),
        app_leader_min_turnover_rate=_read_float("APP_LEADER_MIN_TURNOVER_RATE", 5.0),
        app_leader_min_volume_ratio=_read_float("APP_LEADER_MIN_VOLUME_RATIO", 2.0),
        app_leader_min_volume_multiple=_read_float("APP_LEADER_MIN_VOLUME_MULTIPLE", 1.8),
        app_leader_min_amount=_read_float("APP_LEADER_MIN_AMOUNT", 300000000.0),
        app_leader_min_price=_read_float("APP_LEADER_MIN_PRICE", 3.0),
        app_leader_min_speed=_read_float("APP_LEADER_MIN_SPEED", 0.3),
        app_leader_min_close_to_high_ratio=_read_float("APP_LEADER_MIN_CLOSE_TO_HIGH_RATIO", 0.985),
        app_leader_min_close_in_range_ratio=_read_float("APP_LEADER_MIN_CLOSE_IN_RANGE_RATIO", 0.65),
        app_leader_min_3day_return_pct=_read_float("APP_LEADER_MIN_3DAY_RETURN_PCT", 3.0),
        app_backtest_forward_days=_read_int_tuple("APP_BACKTEST_FORWARD_DAYS", (1, 3, 5, 10)),
        app_backtest_signal_cooldown_days=_read_int("APP_BACKTEST_SIGNAL_COOLDOWN_DAYS", 5),
        wecom_callback_path=_normalize_path(_read_str("WECOM_CALLBACK_PATH", "/wecom/callback")),
        wecom_callback_receive_id=_read_str("WECOM_CALLBACK_RECEIVE_ID", corp_id),
        wecom_callback_token=_read_str("WECOM_CALLBACK_TOKEN", "stockanalyze2026"),
        wecom_callback_encoding_aes_key=_read_str(
            "WECOM_CALLBACK_ENCODING_AES_KEY",
            "stockanalyze2026abcdefghijklmnopqrstuvwxyz1",
        ),
        wecom_webhook_url=_read_optional("WECOM_WEBHOOK_URL"),
        wecom_webhook_key=_read_optional("WECOM_WEBHOOK_KEY"),
        wecom_webhook_base_url=_read_str("WECOM_WEBHOOK_BASE_URL", "https://qyapi.weixin.qq.com"),
        wecom_api_base_url=_read_str("WECOM_API_BASE_URL", "https://qyapi.weixin.qq.com"),
        wecom_corp_id=corp_id,
        wecom_corp_secret=_read_str("WECOM_CORP_SECRET", "E8KRmh7MmDj1fakhqkyeKeZxswq4AH6pm3NGkmiL8GA"),
        wecom_agent_id=_read_str("WECOM_AGENT_ID", "1000002"),
        wecom_to_user=_read_optional("WECOM_TO_USER"),
        wecom_to_party=_read_optional("WECOM_TO_PARTY") or "1",
        wecom_to_tag=_read_optional("WECOM_TO_TAG"),
        db_enabled=_read_bool("DB_ENABLED", False),
        db_host=_read_optional("DB_HOST"),
        db_port=_read_int("DB_PORT", 3306) if _read_optional("DB_PORT") else None,
        db_user=_read_optional("DB_USER"),
        db_password=_read_optional("DB_PASSWORD"),
        db_name=_read_optional("DB_NAME"),
        db_ssl_mode=_read_str("DB_SSL_MODE", "REQUIRED"),
        db_connect_timeout=_read_int("DB_CONNECT_TIMEOUT", 10),
    )


def _read_optional(name: str) -> str | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    trimmed = raw.strip()
    return trimmed or None


def _read_symbols(name: str, default: tuple[str, ...], legacy_name: str | None = None) -> tuple[str, ...]:
    raw = _read_optional(name)
    if raw is None and legacy_name is not None:
        legacy_value = _read_optional(legacy_name)
        if legacy_value is not None:
            raw = legacy_value

    if raw is None:
        return default

    symbols = [item.strip() for item in raw.replace(";", ",").split(",") if item.strip()]
    if not symbols:
        return default

    # Keep order while removing duplicates.
    return tuple(dict.fromkeys(symbols))


def _read_int_tuple(name: str, default: tuple[int, ...]) -> tuple[int, ...]:
    raw = _read_optional(name)
    if raw is None:
        return default

    values: list[int] = []
    for item in raw.replace(";", ",").split(","):
        trimmed = item.strip()
        if not trimmed:
            continue
        values.append(int(trimmed))

    if not values:
        return default

    return tuple(dict.fromkeys(values))


def _normalize_path(value: str) -> str:
    return value if value.startswith("/") else "/" + value


settings = load_settings()
