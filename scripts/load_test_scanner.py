#!/usr/bin/env python3
"""Load-test Shorelight scanner Apps Script endpoint with configurable scenarios."""

from __future__ import annotations

import json
import random
import re
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "index.html"
REPORTS_DIR = ROOT / "reports"


@dataclass(frozen=True)
class Scenario:
    name: str
    users: int
    interval_seconds: float
    duration_seconds: int


def read_api_url(index_html: Path) -> str:
    text = index_html.read_text(encoding="utf-8")
    match = re.search(r'const\s+API_URL\s*=\s*"([^"]+)";', text)
    if not match:
        raise RuntimeError("Could not find API_URL in index.html")
    return match.group(1)


def make_scan_url(api_url: str, scenario: Scenario, user_id: int, iteration: int) -> str:
    payload = {
        "uni": f"LOADTEST_{scenario.name.upper()}_{user_id:02d}",
        "uuid": f"{scenario.name}-{user_id}-{iteration}-{int(time.time() * 1000)}-{random.randint(1000, 9999)}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return f"{api_url}?{urlencode(payload)}"


def send_request(url: str) -> Dict[str, str]:
    req = Request(url, method="GET")
    started = time.perf_counter()
    try:
        with urlopen(req, timeout=30) as response:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            body = response.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return {
                    "status": str(response.status),
                    "result": "invalid_json",
                    "elapsed_ms": str(elapsed_ms),
                }
            return {
                "status": str(response.status),
                "result": str(data.get("result", "unknown")),
                "message": str(data.get("message", "")),
                "elapsed_ms": str(elapsed_ms),
            }
    except HTTPError as exc:
        return {
            "status": str(exc.code),
            "result": "http_error",
            "message": str(exc),
            "elapsed_ms": str(int((time.perf_counter() - started) * 1000)),
        }
    except URLError as exc:
        return {
            "status": "network",
            "result": "url_error",
            "message": str(exc.reason),
            "elapsed_ms": str(int((time.perf_counter() - started) * 1000)),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "result": "exception",
            "message": str(exc),
            "elapsed_ms": str(int((time.perf_counter() - started) * 1000)),
        }


def run_scenario(api_url: str, scenario: Scenario) -> Dict[str, object]:
    lock = threading.Lock()
    records: List[Dict[str, str]] = []
    end_time = time.time() + scenario.duration_seconds

    def worker(user_id: int) -> None:
        iteration = 0
        while time.time() < end_time:
            iteration += 1
            url = make_scan_url(api_url, scenario, user_id, iteration)
            result = send_request(url)
            with lock:
                records.append(result)
            sleep_for = scenario.interval_seconds
            if sleep_for > 0:
                time.sleep(sleep_for)

    with ThreadPoolExecutor(max_workers=scenario.users) as executor:
        for user_id in range(1, scenario.users + 1):
            executor.submit(worker, user_id)

    total = len(records)
    success = sum(1 for r in records if r.get("status") == "200" and r.get("result") == "success")
    server_busy = sum(
        1
        for r in records
        if r.get("result") == "error" and "server busy" in r.get("message", "").lower()
    )
    errors = total - success
    elapsed_values = [int(r.get("elapsed_ms", "0")) for r in records]
    avg_ms = int(sum(elapsed_values) / len(elapsed_values)) if elapsed_values else 0
    p95_ms = sorted(elapsed_values)[int(len(elapsed_values) * 0.95) - 1] if elapsed_values else 0

    result_counter = Counter(f"{r.get('status')}:{r.get('result')}" for r in records)

    return {
        "scenario": scenario.__dict__,
        "total_requests": total,
        "successful_requests": success,
        "error_requests": errors,
        "server_busy_errors": server_busy,
        "success_rate": round((success / total * 100), 2) if total else 0,
        "avg_latency_ms": avg_ms,
        "p95_latency_ms": p95_ms,
        "result_breakdown": dict(result_counter),
    }


def print_summary(results: List[Dict[str, object]]) -> None:
    print("\nLoad Test Results")
    print("=" * 92)
    print(
        f"{'Scenario':<22}{'Users':>7}{'Intvl(s)':>10}{'Reqs':>10}{'Success%':>11}{'Busy':>8}{'Avg ms':>10}{'P95 ms':>10}"
    )
    print("-" * 92)
    for item in results:
        scenario = item["scenario"]
        print(
            f"{scenario['name']:<22}{scenario['users']:>7}{scenario['interval_seconds']:>10.1f}"
            f"{item['total_requests']:>10}{item['success_rate']:>11.2f}{item['server_busy_errors']:>8}"
            f"{item['avg_latency_ms']:>10}{item['p95_latency_ms']:>10}"
        )


def main() -> None:
    api_url = read_api_url(INDEX_HTML)
    scenarios = [
        Scenario("normal_load", users=8, interval_seconds=2.0, duration_seconds=30),
        Scenario("burst_load", users=26, interval_seconds=2.0, duration_seconds=30),
        Scenario("max_load", users=26, interval_seconds=1.0, duration_seconds=30),
    ]

    print(f"Using API_URL from index.html: {api_url}")
    print(f"Running {len(scenarios)} scenarios...")

    all_results = []
    for scenario in scenarios:
        print(
            f"\nRunning scenario '{scenario.name}' "
            f"(users={scenario.users}, interval={scenario.interval_seconds}s, duration={scenario.duration_seconds}s)"
        )
        result = run_scenario(api_url, scenario)
        all_results.append(result)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = REPORTS_DIR / f"load_test_results_{stamp}.json"
    output_path.write_text(json.dumps(all_results, indent=2), encoding="utf-8")

    print_summary(all_results)
    print(f"\nSaved detailed results: {output_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
