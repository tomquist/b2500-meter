#!/usr/bin/env python3
"""
Test script to reproduce the memory leak reported in issue #218.

This script simulates the vzlogger powermeter behavior with high-frequency
HTTP requests and monitors memory usage over time.
"""

import requests
import time
import os
import gc
import tracemalloc
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import json


class MockVZLoggerHandler(BaseHTTPRequestHandler):
    """Mock HTTP server simulating vzlogger responses."""

    def do_GET(self):
        response = {
            "data": [{
                "tuples": [[int(time.time() * 1000), 1500]]
            }]
        }
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())

    def log_message(self, format, *args):
        # Suppress log messages
        pass


class VZLoggerSimulator:
    """Simulates VZLogger powermeter without closing session."""

    def __init__(self, ip: str, port: str, uuid: str):
        self.ip = ip
        self.port = port
        self.uuid = uuid
        self.session = requests.Session()

    def get_json(self):
        url = f"http://{self.ip}:{self.port}/{self.uuid}"
        return self.session.get(url, timeout=10).json()

    def get_powermeter_watts(self):
        return [int(self.get_json()["data"][0]["tuples"][0][1])]


class VZLoggerWithClose:
    """Simulates VZLogger powermeter WITH closing session."""

    def __init__(self, ip: str, port: str, uuid: str):
        self.ip = ip
        self.port = port
        self.uuid = uuid
        self.session = requests.Session()

    def get_json(self):
        url = f"http://{self.ip}:{self.port}/{self.uuid}"
        return self.session.get(url, timeout=10).json()

    def get_powermeter_watts(self):
        return [int(self.get_json()["data"][0]["tuples"][0][1])]

    def close(self):
        if self.session:
            self.session.close()


def get_memory_mb():
    """Get current process memory usage in MB using tracemalloc."""
    current, peak = tracemalloc.get_traced_memory()
    return current / 1024 / 1024


def test_without_close(num_requests=1000, delay=0.01):
    """Test memory usage without closing session."""
    print(f"\n{'='*60}")
    print("TEST 1: WITHOUT closing session")
    print(f"{'='*60}")

    # Start mock server
    server = HTTPServer(('127.0.0.1', 8888), MockVZLoggerHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)  # Let server start

    pm = VZLoggerSimulator('127.0.0.1', '8888', 'test-uuid')

    start_memory = get_memory_mb()
    print(f"Initial memory: {start_memory:.2f} MB")

    # Make many requests
    for i in range(num_requests):
        try:
            pm.get_powermeter_watts()
        except Exception as e:
            print(f"Error at request {i}: {e}")
            break

        # Report memory every 100 requests
        if (i + 1) % 100 == 0:
            current_memory = get_memory_mb()
            growth = current_memory - start_memory
            print(f"Request {i+1:4d}: {current_memory:.2f} MB (growth: {growth:+.2f} MB)")

        time.sleep(delay)

    final_memory = get_memory_mb()
    total_growth = final_memory - start_memory
    print(f"\nFinal memory: {final_memory:.2f} MB")
    print(f"Total growth: {total_growth:+.2f} MB ({(total_growth/start_memory)*100:+.1f}%)")

    server.shutdown()
    return start_memory, final_memory, total_growth


def test_with_close(num_requests=1000, delay=0.01):
    """Test memory usage WITH closing session."""
    print(f"\n{'='*60}")
    print("TEST 2: WITH closing session")
    print(f"{'='*60}")

    # Start mock server
    server = HTTPServer(('127.0.0.1', 8889), MockVZLoggerHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)  # Let server start

    pm = VZLoggerWithClose('127.0.0.1', '8889', 'test-uuid')

    start_memory = get_memory_mb()
    print(f"Initial memory: {start_memory:.2f} MB")

    # Make many requests
    for i in range(num_requests):
        try:
            pm.get_powermeter_watts()
        except Exception as e:
            print(f"Error at request {i}: {e}")
            break

        # Report memory every 100 requests
        if (i + 1) % 100 == 0:
            current_memory = get_memory_mb()
            growth = current_memory - start_memory
            print(f"Request {i+1:4d}: {current_memory:.2f} MB (growth: {growth:+.2f} MB)")

        time.sleep(delay)

    pm.close()  # Close session after use

    final_memory = get_memory_mb()
    total_growth = final_memory - start_memory
    print(f"\nFinal memory: {final_memory:.2f} MB")
    print(f"Total growth: {total_growth:+.2f} MB ({(total_growth/start_memory)*100:+.1f}%)")

    server.shutdown()
    return start_memory, final_memory, total_growth


def main():
    # Start memory tracking
    tracemalloc.start()

    print("Memory Leak Reproduction Test for Issue #218")
    print("=" * 60)

    # Test parameters - simulating 1-second polling
    # Using 1000 requests with 0.01s delay = 10 seconds total
    # (scaled down from 5 days for quick testing)
    num_requests = 1000
    delay = 0.01

    print(f"\nTest parameters:")
    print(f"  Requests: {num_requests}")
    print(f"  Delay: {delay}s between requests")
    print(f"  Total duration: ~{num_requests * delay:.1f} seconds")

    # Run test without closing session
    start1, end1, growth1 = test_without_close(num_requests, delay)

    # Give system time to settle
    time.sleep(2)

    # Run test with closing session
    start2, end2, growth2 = test_with_close(num_requests, delay)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"WITHOUT close(): {growth1:+.2f} MB growth ({(growth1/start1)*100:+.1f}%)")
    print(f"WITH close():    {growth2:+.2f} MB growth ({(growth2/start2)*100:+.1f}%)")
    print(f"Difference:      {growth1-growth2:.2f} MB")

    if abs(growth1 - growth2) > 1.0:  # More than 1MB difference
        print("\n⚠️  MEMORY LEAK DETECTED!")
        print("   Closing the session makes a significant difference.")
    else:
        print("\n✓  No significant memory leak detected.")
        print("   The issue may be elsewhere or require longer testing.")


if __name__ == "__main__":
    main()
