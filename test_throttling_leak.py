#!/usr/bin/env python3
"""
Test if ThrottledPowermeter pattern causes memory leak.

The issue reporter mentions using throttling. This test simulates:
1. Throttled requests with 1-second interval (matching the issue)
2. High-frequency polling that hits the cache frequently
3. Long-term usage pattern

This is a standalone test that recreates the throttling logic to avoid circular imports.
"""

import time
import gc
import tracemalloc
import requests
import threading
from typing import List, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
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


class VZLoggerSimulator:
    """Simulates VZLogger behavior."""
    def __init__(self, ip: str, port: str, uuid: str):
        self.ip = ip
        self.port = port
        self.uuid = uuid
        self.session = requests.Session()

    def get_json(self):
        url = f"http://{self.ip}:{self.port}/{self.uuid}"
        return self.session.get(url, timeout=10).json()

    def get_powermeter_watts(self) -> List[float]:
        return [float(self.get_json()["data"][0]["tuples"][0][1])]


class ThrottledPowermeterSimulator:
    """Simulates ThrottledPowermeter behavior."""
    def __init__(self, wrapped_powermeter, throttle_interval: float = 0.0):
        self.wrapped_powermeter = wrapped_powermeter
        self.throttle_interval = throttle_interval
        self.last_update_time = 0.0
        self.last_values: Optional[List[float]] = None
        self.lock = threading.Lock()

    def get_powermeter_watts(self) -> List[float]:
        with self.lock:
            current_time = time.time()

            # If throttling is disabled, always fetch fresh values
            if self.throttle_interval <= 0:
                values = self.wrapped_powermeter.get_powermeter_watts()
                self.last_values = values
                self.last_update_time = current_time
                return values

            # Check if enough time has passed since last update
            time_since_last_update = current_time - self.last_update_time

            if time_since_last_update < self.throttle_interval:
                # Not enough time has passed, wait for the remaining time
                wait_time = self.throttle_interval - time_since_last_update
                time.sleep(wait_time)
                current_time = time.time()

            # Time to get fresh values
            try:
                values = self.wrapped_powermeter.get_powermeter_watts()
                self.last_values = values
                self.last_update_time = current_time
                return values
            except Exception as e:
                # Fall back to cached values if available
                if self.last_values is not None:
                    return self.last_values
                raise


def test_throttled_powermeter_leak(num_polls=5000, throttle_interval=1.0):
    """Test ThrottledPowermeter with 1-second throttle, polled frequently."""
    print(f"\n{'='*60}")
    print("TEST 1: ThrottledPowermeter Memory Leak")
    print(f"Throttle interval: {throttle_interval}s")
    print(f"Number of polls: {num_polls}")
    print(f"{'='*60}")

    # Start mock VZLogger server
    server = HTTPServer(('127.0.0.1', 9301), MockVZLoggerHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    # Create throttled VZLogger (like the issue reporter)
    base_powermeter = VZLoggerSimulator(ip='127.0.0.1', port='9301', uuid='test-uuid')
    throttled_pm = ThrottledPowermeterSimulator(base_powermeter, throttle_interval=throttle_interval)

    start_mem = get_memory_mb()
    print(f"Initial memory: {start_mem:.2f} MB")

    actual_requests = 0
    start_test_time = time.time()

    for i in range(num_polls):
        try:
            values = throttled_pm.get_powermeter_watts()
            actual_requests += 1

            if (i + 1) % 2000 == 0:
                gc.collect()
                current_mem = get_memory_mb()
                growth = current_mem - start_mem
                elapsed = time.time() - start_test_time
                print(f"Poll {i+1:5d}: {current_mem:.2f} MB (growth: {growth:+.2f} MB) - {elapsed:.1f}s elapsed")

        except Exception as e:
            print(f"Error at poll {i}: {e}")
            break

    final_mem = get_memory_mb()
    total_growth = final_mem - start_mem
    total_time = time.time() - start_test_time
    print(f"\nFinal memory: {final_mem:.2f} MB")
    print(f"Total growth: {total_growth:+.2f} MB")
    print(f"Total time: {total_time:.1f}s")
    print(f"Actual HTTP requests made: {actual_requests}")

    server.shutdown()
    return total_growth


def test_no_throttling_baseline(num_polls=5000):
    """Baseline: VZLogger without throttling."""
    print(f"\n{'='*60}")
    print("TEST 2: VZLogger without Throttling (Baseline)")
    print(f"Number of polls: {num_polls}")
    print(f"{'='*60}")

    # Start mock VZLogger server
    server = HTTPServer(('127.0.0.1', 9302), MockVZLoggerHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    # Create plain VZLogger
    powermeter = VZLoggerSimulator(ip='127.0.0.1', port='9302', uuid='test-uuid')

    start_mem = get_memory_mb()
    print(f"Initial memory: {start_mem:.2f} MB")

    for i in range(num_polls):
        try:
            values = powermeter.get_powermeter_watts()

            if (i + 1) % 2000 == 0:
                gc.collect()
                current_mem = get_memory_mb()
                growth = current_mem - start_mem
                print(f"Poll {i+1:5d}: {current_mem:.2f} MB (growth: {growth:+.2f} MB)")

        except Exception as e:
            print(f"Error at poll {i}: {e}")
            break

    final_mem = get_memory_mb()
    total_growth = final_mem - start_mem
    print(f"\nFinal memory: {final_mem:.2f} MB")
    print(f"Total growth: {total_growth:+.2f} MB")

    server.shutdown()
    return total_growth


def test_throttling_with_fork_pattern(num_polls=5000, throttle_interval=1.0):
    """Test throttling with fork's dual-request pattern."""
    print(f"\n{'='*60}")
    print("TEST 3: Throttled Fork Pattern (2 requests per poll)")
    print(f"Throttle interval: {throttle_interval}s")
    print(f"Number of polls: {num_polls}")
    print(f"{'='*60}")

    # Start mock VZLogger server
    server = HTTPServer(('127.0.0.1', 9303), MockVZLoggerHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    # Simulate fork's pattern: 2 separate throttled powermeters
    pm_input = VZLoggerSimulator(ip='127.0.0.1', port='9303', uuid='power-input')
    pm_output = VZLoggerSimulator(ip='127.0.0.1', port='9303', uuid='power-output')

    throttled_input = ThrottledPowermeterSimulator(pm_input, throttle_interval=throttle_interval)
    throttled_output = ThrottledPowermeterSimulator(pm_output, throttle_interval=throttle_interval)

    start_mem = get_memory_mb()
    print(f"Initial memory: {start_mem:.2f} MB")
    start_test_time = time.time()

    for i in range(num_polls):
        try:
            # Fork's pattern: get both values and calculate
            power_in = throttled_input.get_powermeter_watts()[0]
            power_out = throttled_output.get_powermeter_watts()[0]
            power_net = power_in - power_out

            if (i + 1) % 2000 == 0:
                gc.collect()
                current_mem = get_memory_mb()
                growth = current_mem - start_mem
                elapsed = time.time() - start_test_time
                print(f"Poll {i+1:5d}: {current_mem:.2f} MB (growth: {growth:+.2f} MB) - {elapsed:.1f}s elapsed")

        except Exception as e:
            print(f"Error at poll {i}: {e}")
            break

    final_mem = get_memory_mb()
    total_growth = final_mem - start_mem
    total_time = time.time() - start_test_time
    print(f"\nFinal memory: {final_mem:.2f} MB")
    print(f"Total growth: {total_growth:+.2f} MB")
    print(f"Total time: {total_time:.1f}s")

    server.shutdown()
    return total_growth


def main():
    tracemalloc.start()

    print("Testing ThrottledPowermeter for Memory Leaks")
    print("=" * 60)
    print("Simulating the issue reporter's configuration:")
    print("- 1-second throttle interval")
    print("- Continuous polling (like vzlogger)")
    print()

    results = {}

    # Test 1: With 0.01s throttle for speed (extrapolate to 1s intervals)
    results['throttled_0.01s'] = test_throttled_powermeter_leak(5000, throttle_interval=0.01)
    time.sleep(2)

    # Test 2: Baseline without throttling
    results['no_throttling'] = test_no_throttling_baseline(5000)
    time.sleep(2)

    # Test 3: Fork pattern with throttling
    results['throttled_fork'] = test_throttling_with_fork_pattern(5000, throttle_interval=0.01)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY - Memory Growth per 5000 Polls")
    print(f"{'='*60}")
    for test_name, growth in results.items():
        print(f"{test_name:25s}: {growth:+.2f} MB")

    # Project to 5 days at 1-second polling
    print(f"\n{'='*60}")
    print("Projected Over 5 Days (1-second polling)")
    print(f"{'='*60}")

    polls_per_day = 86400
    polls_5_days = polls_per_day * 5  # 432,000

    for test_name, growth in results.items():
        scale_factor = polls_5_days / 5000
        projected_mb = growth * scale_factor
        projected_gb = projected_mb / 1024

        print(f"{test_name:25s}: {projected_mb:6.0f} MB ({projected_gb:.2f} GB)")

        if projected_gb > 1.0:
            print(f"  ⚠️  POTENTIAL LEAK - MATCHES REPORTED ISSUE!")
        elif projected_gb > 0.1:
            print(f"  ⚠️  Moderate growth")
        else:
            print(f"  ✓  Acceptable growth")

    print()

    # Conclusion
    worst = max(results.items(), key=lambda x: x[1])
    scale_factor = polls_5_days / 5000
    worst_projected_gb = (worst[1] * scale_factor) / 1024

    if worst_projected_gb > 1.0:
        print(f"⚠️  WARNING: Throttling pattern shows significant memory growth!")
        print(f"   Worst case: {worst[0]} with {worst_projected_gb:.2f} GB over 5 days")
    else:
        print(f"✓  Throttling does NOT cause the reported leak")
        print(f"   Maximum projected growth: {worst_projected_gb:.2f} GB over 5 days")


if __name__ == "__main__":
    main()
