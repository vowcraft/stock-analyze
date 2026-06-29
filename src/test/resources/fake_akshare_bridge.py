import json
import sys


def main():
    function_name = sys.argv[1]
    params = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}

    if function_name == "explode":
        payload = {
            "success": False,
            "function": function_name,
            "errorType": "RuntimeError",
            "errorMessage": "boom",
        }
        print(json.dumps(payload), file=sys.stderr)
        sys.exit(1)

    if function_name == "stock_info_a_code_name":
        payload = {
            "success": True,
            "function": function_name,
            "data": [
                {"code": "600519", "name": "贵州茅台"},
                {"code": "000001", "name": "平安银行"},
            ],
        }
        print(json.dumps(payload))
        return

    payload = {
        "success": True,
        "function": function_name,
        "data": [
            {
                "symbol": params.get("symbol"),
                "period": params.get("period"),
                "close": 123.45,
            }
        ],
    }
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
