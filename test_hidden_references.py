#!/usr/bin/env python3
"""
Test for hidden references that might keep response objects alive.

Scenarios to test:
1. Exception tracebacks holding response references
2. Request history keeping old responses
3. urllib3 response buffers not being released
"""

import requests
import time
import gc
import tracemalloc
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import json


class MockHandler(BaseHTTPRequestHandler):
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


def test_exception_traceback_leak(num_requests=5000):
    """Test if exception tracebacks hold response references."""
    print(f"\n{'='*60}")
    print("TEST: Exception Traceback Leak")
    print(f"{'='*60}")

    server = HTTPServer(('127.0.0.1', 9001), MockHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    session = requests.Session()
    start_mem = get_memory_mb()
    print(f"Initial memory: {start_mem:.2f} MB")

    # Store exceptions (which might contain response references in tracebacks)
    exceptions = []

    for i in range(num_requests):
        try:
            resp = session.get('http://127.0.0.1:9001/test', timeout=5)
            data = resp.json()

            # Intentionally cause an exception that might capture response
            try:
                _ = 1 / 0  # Causes exception
            except Exception as e:
                exceptions.append(e)
                exceptions.append(sys.exc_info())  # Store traceback info

            if (i + 1) % 1000 == 0:
                gc.collect()
                current_mem = get_memory_mb()
                growth = current_mem - start_mem
                print(f"Request {i+1:5d}: {current_mem:.2f} MB (growth: {growth:+.2f} MB) - {len(exceptions)} exceptions stored")
        except Exception as e:
            print(f"Error: {e}")
            break

    final_mem = get_memory_mb()
    total_growth = final_mem - start_mem
    print(f"\nWith {len(exceptions)} exceptions/tracebacks:")
    print(f"Final memory: {final_mem:.2f} MB")
    print(f"Total growth: {total_growth:+.2f} MB")

    # Clear and check
    exceptions.clear()
    gc.collect()
    after_clear = get_memory_mb()
    print(f"After clearing: {after_clear:.2f} MB (freed: {final_mem - after_clear:.2f} MB)")

    server.shutdown()
    return total_growth


def test_request_history_leak(num_requests=5000):
    """Test if requests keeps history of redirects/responses."""
    print(f"\n{'='*60}")
    print("TEST: Request History Leak")
    print(f"{'='*60}")

    server = HTTPServer(('127.0.0.1', 9002), MockHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    session = requests.Session()
    start_mem = get_memory_mb()
    print(f"Initial memory: {start_mem:.2f} MB")

    # Check session's redirect history
    for i in range(num_requests):
        try:
            resp = session.get('http://127.0.0.1:9002/test', timeout=5)
            data = resp.json()

            if (i + 1) % 1000 == 0:
                gc.collect()
                current_mem = get_memory_mb()
                growth = current_mem - start_mem
                history_len = len(resp.history) if hasattr(resp, 'history') else 0
                print(f"Request {i+1:5d}: {current_mem:.2f} MB (growth: {growth:+.2f} MB) - History: {history_len}")
        except Exception as e:
            print(f"Error: {e}")
            break

    final_mem = get_memory_mb()
    total_growth = final_mem - start_mem
    print(f"\nFinal memory: {final_mem:.2f} MB")
    print(f"Total growth: {total_growth:+.2f} MB")

    server.shutdown()
    return total_growth


def test_response_content_buffering(num_requests=5000):
    """Test if response content stays buffered."""
    print(f"\n{'='*60}")
    print("TEST: Response Content Buffering")
    print(f"{'='*60}")

    server = HTTPServer(('127.0.0.1', 9003), MockHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    session = requests.Session()
    start_mem = get_memory_mb()
    print(f"Initial memory: {start_mem:.2f} MB")

    for i in range(num_requests):
        try:
            resp = session.get('http://127.0.0.1:9003/test', timeout=5)
            # Access content multiple ways - does this cause buffering?
            _ = resp.text
            _ = resp.content
            data = resp.json()

            if (i + 1) % 1000 == 0:
                gc.collect()
                current_mem = get_memory_mb()
                growth = current_mem - start_mem
                print(f"Request {i+1:5d}: {current_mem:.2f} MB (growth: {growth:+.2f} MB)")
        except Exception as e:
            print(f"Error: {e}")
            break

    final_mem = get_memory_mb()
    total_growth = final_mem - start_mem
    print(f"\nFinal memory: {final_mem:.2f} MB")
    print(f"Total growth: {total_growth:+.2f} MB")

    server.shutdown()
    return total_growth


def test_urllib3_connection_leak(num_requests=5000):
    """Test urllib3 poolmanager connection accumulation."""
    print(f"\n{'='*60}")
    print("TEST: urllib3 Connection Accumulation")
    print(f"{'='*60}")

    server = HTTPServer(('127.0.0.1', 9004), MockHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    session = requests.Session()
    start_mem = get_memory_mb()
    print(f"Initial memory: {start_mem:.2f} MB")

    for i in range(num_requests):
        try:
            resp = session.get('http://127.0.0.1:9004/test', timeout=5)
            data = resp.json()

            if (i + 1) % 1000 == 0:
                gc.collect()
                current_mem = get_memory_mb()
                growth = current_mem - start_mem

                # Check internal pool state
                adapter = session.adapters.get('http://')
                if adapter and hasattr(adapter, 'poolmanager'):
                    pools = adapter.poolmanager.pools if hasattr(adapter.poolmanager, 'pools') else {}
                    print(f"Request {i+1:5d}: {current_mem:.2f} MB (growth: {growth:+.2f} MB) - Pools: {len(pools)}")
                else:
                    print(f"Request {i+1:5d}: {current_mem:.2f} MB (growth: {growth:+.2f} MB)")
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

    print("Testing Hidden Reference Leaks")
    print("=" * 60)

    results = {}

    results['exception_traceback'] = test_exception_traceback_leak(5000)
    time.sleep(1)

    results['request_history'] = test_request_history_leak(5000)
    time.sleep(1)

    results['content_buffering'] = test_response_content_buffering(5000)
    time.sleep(1)

    results['urllib3_connections'] = test_urllib3_connection_leak(5000)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY - Memory Growth per 5000 Requests")
    print(f"{'='*60}")
    for test_name, growth in results.items():
        print(f"{test_name:25s}: {growth:+.2f} MB")

    worst = max(results.items(), key=lambda x: x[1])
    print(f"\nWorst: {worst[0]} with {worst[1]:.2f} MB growth")

    # Project to 5 days
    requests_5_days = 86400 * 5
    scale_factor = requests_5_days / 5000
    projected = worst[1] * scale_factor

    print(f"\nProjected over 5 days (432,000 requests):")
    print(f"  {worst[0]}: {projected:.0f} MB ({projected/1024:.2f} GB)")


if __name__ == "__main__":
    main()
