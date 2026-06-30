from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

import pymysql
from pymysql.connections import Connection

from app.config import settings


logger = logging.getLogger(__name__)


class DatabaseNotConfigured(RuntimeError):
    pass


def _build_connect_kwargs() -> dict[str, object]:
    if not settings.db_enabled:
        raise DatabaseNotConfigured(
            "DB is disabled. Set DB_ENABLED=true plus DB_HOST/DB_USER/DB_PASSWORD/DB_NAME."
        )
    missing = [
        n
        for n, v in (("DB_HOST", settings.db_host),
                     ("DB_USER", settings.db_user),
                     ("DB_PASSWORD", settings.db_password),
                     ("DB_NAME", settings.db_name))
        if not v
    ]
    if missing:
        raise DatabaseNotConfigured(
            f"DB enabled but missing env vars: {', '.join(missing)}"
        )

    kwargs: dict[str, object] = {
        "host": settings.db_host,
        "port": settings.db_port or 3306,
        "user": settings.db_user,
        "password": settings.db_password,
        "database": settings.db_name,
        "connect_timeout": settings.db_connect_timeout,
        "charset": "utf8mb4",
    }
    if (settings.db_ssl_mode or "").upper() in {"REQUIRED", "VERIFY_CA", "VERIFY_IDENTITY"}:
        kwargs["ssl"] = {"ssl_mode": settings.db_ssl_mode.upper()}
    return kwargs


@contextmanager
def get_connection() -> Iterator[Connection]:
    conn = pymysql.connect(**_build_connect_kwargs())
    try:
        yield conn
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        raise
    finally:
        conn.close()


def health_check() -> bool:
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                row = cursor.fetchone()
        return row is not None and row[0] == 1
    except Exception as exc:  # noqa: BLE001
        logger.warning("DB health_check failed: %s", exc)
        return False
