#!/usr/bin/env python3
import datetime as dt
import json
import math
import sys
from decimal import Decimal

try:
    import akshare as ak
    import pandas as pd
except Exception as exc:
    payload = {
        "success": False,
        "function": None,
        "errorType": type(exc).__name__,
        "errorMessage": f"failed to import bridge dependencies: {exc}",
    }
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
    sys.exit(1)

try:
    import numpy as np
except Exception:
    np = None


def emit_error(function_name, error_type, error_message, exit_code=1):
    payload = {
        "success": False,
        "function": function_name,
        "errorType": error_type,
        "errorMessage": error_message,
    }
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
    sys.exit(exit_code)


def normalize(value):
    if value is None:
        return None
    if isinstance(value, pd.DataFrame):
        return [normalize(record) for record in value.to_dict(orient="records")]
    if isinstance(value, pd.Series):
        return normalize(value.to_dict())
    if np is not None and isinstance(value, np.ndarray):
        return [normalize(item) for item in value.tolist()]
    if isinstance(value, dict):
        return {str(key): normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [normalize(item) for item in value]
    if isinstance(value, Decimal):
        return float(value)
    if np is not None and isinstance(value, np.generic):
        return normalize(value.item())
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if value is pd.NA:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (str, bool, int)):
        return value
    return str(value)


def main():
    if len(sys.argv) < 2:
        emit_error(None, "ArgumentError", "usage: akshare_bridge.py <function> [params_json]", 2)

    function_name = sys.argv[1]
    raw_params = sys.argv[2] if len(sys.argv) > 2 else "{}"

    try:
        kwargs = json.loads(raw_params)
    except json.JSONDecodeError as exc:
        emit_error(function_name, "JSONDecodeError", str(exc), 2)

    if not isinstance(kwargs, dict):
        emit_error(function_name, "ArgumentError", "params_json must be a JSON object", 2)

    target = getattr(ak, function_name, None)
    if target is None or not callable(target):
        emit_error(
            function_name,
            "AttributeError",
            f"akshare has no callable function named '{function_name}'",
            2,
        )

    try:
        result = target(**kwargs)
    except Exception as exc:
        emit_error(function_name, type(exc).__name__, str(exc))

    payload = {
        "success": True,
        "function": function_name,
        "data": normalize(result),
    }
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
