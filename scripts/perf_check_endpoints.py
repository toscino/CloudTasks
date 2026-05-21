#!/usr/bin/env python3
"""Time key API endpoints (run with app server up). Usage:
  .venv/Scripts/python.exe scripts/perf_check_endpoints.py
  .venv/Scripts/python.exe scripts/perf_check_endpoints.py --base https://YOUR_PROJECT.appspot.com
"""
import argparse
import time

import requests

DEFAULT_PATHS = [
    "/api/user",
    "/api/user/settings",
    "/api/task-points/today",
    "/api/task-points/balance",
    "/api/tasks",
    "/api/task-points/daily-history?days=365",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Time CloudTasks API endpoints")
    parser.add_argument("--base", default="http://127.0.0.1:8080", help="Server base URL")
    parser.add_argument("--paths", nargs="*", default=DEFAULT_PATHS)
    args = parser.parse_args()
    base = args.base.rstrip("/")
    print(f"Base: {base}\n")
    for path in args.paths:
        url = f"{base}{path}"
        t0 = time.perf_counter()
        try:
            r = requests.get(url, timeout=120)
            elapsed = time.perf_counter() - t0
            print(f"{path}: HTTP {r.status_code} in {elapsed:.2f}s")
        except requests.RequestException as e:
            elapsed = time.perf_counter() - t0
            print(f"{path}: ERROR after {elapsed:.2f}s — {e}")


if __name__ == "__main__":
    main()
