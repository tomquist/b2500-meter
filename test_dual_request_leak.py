#!/usr/bin/env python3
"""
Test if the fork's pattern of 2 requests per poll causes memory leak.

The fork makes 2 sequential HTTP requests when POWER_CALCULATE = True:
1. One for power_input_uuid
2. One for power_output_uuid

This test simulates that exact pattern.
"""

import requests
import time
import gc
import tracemalloc
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import json


class MockVZLoggerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        response = {"data": [{"tuples": [[int(time.time() * 1000), 1500]]}]}
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())

    def log_message(self, format, *args):
        pass


def get_memory_mb():
    current, peak = tracemalloc.get_traced_memory()
    return current / 1024 / 1024


def test_single_request_per_poll(num_polls=5000):
    """Baseline: Single request per poll (original vzlogger)."""
    print(f"\n{'='*60}")
    print("TEST 1: Single Request Per Poll (Original)")
    print(f"{'='*60}")

    server = HTTPServer(('127.0.0.1', 9101), MockVZLoggerHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    session = requests.Session()
    start_mem = get_memory_mb()
    print(f"Initial memory: {start_mem:.2f} MB")

    for i in range(num_polls):
        try:
            # Original pattern: 1 request
            resp = session.get('http://127.0.0.1:9101/uuid', timeout=5)
            data = resp.json()
            value = int(data["data"][0]["tuples"][0][1])

            if (i + 1) % 1000 == 0:
                gc.collect()
                current_mem = get_memory_mb()
                growth = current_mem - start_mem
                print(f"Poll {i+1:5d}: {current_mem:.2f} MB (growth: {growth:+.2f} MB)")
        except Exception as e:
            print(f"Error: {e}")
            break

    final_mem = get_memory_mb()
    total_growth = final_mem - start_mem
    print(f"\nFinal memory: {final_mem:.2f} MB")
    print(f"Total growth: {total_growth:+.2f} MB")

    server.shutdown()
    return total_growth


def test_dual_request_per_poll(num_polls=5000):
    """Fork pattern: Two sequential requests per poll."""
    print(f"\n{'='*60}")
    print("TEST 2: Dual Request Per Poll (Fork - POWER_CALCULATE=True)")
    print(f"{'='*60}")

    server = HTTPServer(('127.0.0.1', 9102), MockVZLoggerHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    session = requests.Session()
    start_mem = get_memory_mb()
    print(f"Initial memory: {start_mem:.2f} MB")

    for i in range(num_polls):
        try:
            # Fork pattern: 2 sequential requests
            resp1 = session.get('http://127.0.0.1:9102/power_input_uuid', timeout=5)
            data1 = resp1.json()
            power_in = int(data1["data"][0]["tuples"][0][1])

            resp2 = session.get('http://127.0.0.1:9102/power_output_uuid', timeout=5)
            data2 = resp2.json()
            power_out = int(data2["data"][0]["tuples"][0][1])

            value = power_in - power_out

            if (i + 1) % 1000 == 0:
                gc.collect()
                current_mem = get_memory_mb()
                growth = current_mem - start_mem
                print(f"Poll {i+1:5d}: {current_mem:.2f} MB (growth: {growth:+.2f} MB) - 2 requests/poll")
        except Exception as e:
            print(f"Error: {e}")
            break

    final_mem = get_memory_mb()
    total_growth = final_mem - start_mem
    print(f"\nFinal memory: {final_mem:.2f} MB")
    print(f"Total growth: {total_growth:+.2f} MB")

    server.shutdown()
    return total_growth


def test_dual_request_with_local_vars(num_polls=5000):
    """Test if keeping local vars power_in/power_out makes a difference."""
    print(f"\n{'='*60}")
    print("TEST 3: Dual Request with Local Var Pattern")
    print(f"{'='*60}")

    server = HTTPServer(('127.0.0.1', 9103), MockVZLoggerHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    session = requests.Session()
    start_mem = get_memory_mb()
    print(f"Initial memory: {start_mem:.2f} MB")

    for i in range(num_polls):
        try:
            # Fork's exact pattern from the diff
            power_in = 0
            power_out = 0
            power_in = int(session.get('http://127.0.0.1:9103/power_input_uuid', timeout=5).json()["data"][0]["tuples"][0][1])
            power_out = int(session.get('http://127.0.0.1:9103/power_output_uuid', timeout=5).json()["data"][0]["tuples"][0][1])
            value = power_in - power_out

            if (i + 1) % 1000 == 0:
                gc.collect()
                current_mem = get_memory_mb()
                growth = current_mem - start_mem
                print(f"Poll {i+1:5d}: {current_mem:.2f} MB (growth: {growth:+.2f} MB)")
        except Exception as e:
            print(f"Error: {e}")
            break

    final_mem = get_memory_mb()
    total_growth = final_mem - start_mem
    print(f"\nFinal memory: {final_mem:.2f} MB")
    print(f"Total growth: {total_growth:+.2f} MB")

    server.shutdown()
    return total_growth


def main():
    tracemalloc.start()

    print("Testing Fork's Dual-Request Pattern for Memory Leaks")
    print("=" * 60)
    print("Simulating 5000 polls with the fork's POWER_CALCULATE=True pattern")
    print()

    results = {}

    results['single_request'] = test_single_request_per_poll(5000)
    time.sleep(1)

    results['dual_request'] = test_dual_request_per_poll(5000)
    time.sleep(1)

    results['dual_with_locals'] = test_dual_request_with_local_vars(5000)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY - Memory Growth per 5000 Polls")
    print(f"{'='*60}")
    for test_name, growth in results.items():
        total_requests = 5000 if 'single' in test_name else 10000
        print(f"{test_name:25s}: {growth:+.2f} MB ({total_requests} requests)")

    # Project to 5 days
    print(f"\n{'='*60}")
    print("Projected Over 5 Days (1-second polling)")
    print(f"{'='*60}")

    polls_per_day = 86400
    polls_5_days = polls_per_day * 5  # 432,000

    for test_name, growth in results.items():
        scale_factor = polls_5_days / 5000
        projected_mb = growth * scale_factor
        projected_gb = projected_mb / 1024

        total_requests = polls_5_days if 'single' in test_name else polls_5_days * 2

        print(f"{test_name:25s}: {projected_mb:6.0f} MB ({projected_gb:.2f} GB)")
        print(f"  Total requests: {total_requests:,}")

        if projected_gb > 1.0:
            print(f"  ⚠️  MATCHES REPORTED LEAK!")

    print()


if __name__ == "__main__":
    main()
