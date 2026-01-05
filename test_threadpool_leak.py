#!/usr/bin/env python3
"""
Test if ThreadPoolExecutor with untracked futures causes memory leak.

The Shelly UDP server does:
    self._executor.submit(self._handle_request, sock, data, addr)

Without storing the returned Future object. This test checks if that pattern leaks.
"""

import time
import gc
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
import requests
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


def worker_function(session, url):
    """Simulates what Shelly does: calls powermeter.get_powermeter_watts()"""
    try:
        resp = session.get(url, timeout=5)
        data = resp.json()
        return int(data["data"][0]["tuples"][0][1])
    except:
        return 0


def test_threadpool_with_untracked_futures(num_submits=10000):
    """Test if submitting many tasks without tracking futures causes leak."""
    print(f"\n{'='*60}")
    print("TEST 1: ThreadPoolExecutor with Untracked Futures")
    print("(Simulates Shelly UDP server pattern)")
    print(f"{'='*60}")

    server = HTTPServer(('127.0.0.1', 9201), MockHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    session = requests.Session()
    executor = ThreadPoolExecutor(max_workers=5)

    start_mem = get_memory_mb()
    print(f"Initial memory: {start_mem:.2f} MB")

    for i in range(num_submits):
        # DON'T STORE THE FUTURE - just like Shelly code does
        executor.submit(worker_function, session, 'http://127.0.0.1:9201/test')

        if (i + 1) % 2000 == 0:
            gc.collect()
            current_mem = get_memory_mb()
            growth = current_mem - start_mem
            print(f"Submit {i+1:5d}: {current_mem:.2f} MB (growth: {growth:+.2f} MB)")

    # Wait for all tasks to complete
    print("Waiting for tasks to complete...")
    executor.shutdown(wait=True)

    gc.collect()
    final_mem = get_memory_mb()
    total_growth = final_mem - start_mem
    print(f"\nAfter shutdown:")
    print(f"Final memory: {final_mem:.2f} MB")
    print(f"Total growth: {total_growth:+.2f} MB")

    server.shutdown()
    return total_growth


def test_threadpool_with_tracked_futures(num_submits=10000):
    """Test if tracking and clearing futures prevents leak."""
    print(f"\n{'='*60}")
    print("TEST 2: ThreadPoolExecutor with Tracked Futures")
    print("(Alternative pattern - store and clear periodically)")
    print(f"{'='*60}")

    server = HTTPServer(('127.0.0.1', 9202), MockHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    session = requests.Session()
    executor = ThreadPoolExecutor(max_workers=5)
    futures = []

    start_mem = get_memory_mb()
    print(f"Initial memory: {start_mem:.2f} MB")

    for i in range(num_submits):
        # STORE THE FUTURE
        future = executor.submit(worker_function, session, 'http://127.0.0.1:9202/test')
        futures.append(future)

        # Clear completed futures periodically
        if (i + 1) % 1000 == 0:
            futures = [f for f in futures if not f.done()]
            gc.collect()
            current_mem = get_memory_mb()
            growth = current_mem - start_mem
            print(f"Submit {i+1:5d}: {current_mem:.2f} MB (growth: {growth:+.2f} MB) - {len(futures)} pending")

    # Wait for all tasks to complete
    print("Waiting for tasks to complete...")
    executor.shutdown(wait=True)
    futures.clear()

    gc.collect()
    final_mem = get_memory_mb()
    total_growth = final_mem - start_mem
    print(f"\nAfter shutdown and clear:")
    print(f"Final memory: {final_mem:.2f} MB")
    print(f"Total growth: {total_growth:+.2f} MB")

    server.shutdown()
    return total_growth


def test_no_threadpool_direct_calls(num_calls=10000):
    """Baseline: Direct calls without ThreadPoolExecutor."""
    print(f"\n{'='*60}")
    print("TEST 3: Direct Calls (No ThreadPoolExecutor)")
    print("(Baseline)")
    print(f"{'='*60}")

    server = HTTPServer(('127.0.0.1', 9203), MockHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    session = requests.Session()

    start_mem = get_memory_mb()
    print(f"Initial memory: {start_mem:.2f} MB")

    for i in range(num_calls):
        worker_function(session, 'http://127.0.0.1:9203/test')

        if (i + 1) % 2000 == 0:
            gc.collect()
            current_mem = get_memory_mb()
            growth = current_mem - start_mem
            print(f"Call {i+1:5d}: {current_mem:.2f} MB (growth: {growth:+.2f} MB)")

    gc.collect()
    final_mem = get_memory_mb()
    total_growth = final_mem - start_mem
    print(f"\nFinal memory: {final_mem:.2f} MB")
    print(f"Total growth: {total_growth:+.2f} MB")

    server.shutdown()
    return total_growth


def main():
    tracemalloc.start()

    print("Testing ThreadPoolExecutor Memory Leak")
    print("=" * 60)
    print("Simulating Shelly UDP server's pattern of submitting tasks")
    print()

    results = {}

    results['untracked_futures'] = test_threadpool_with_untracked_futures(10000)
    time.sleep(2)

    results['tracked_futures'] = test_threadpool_with_tracked_futures(10000)
    time.sleep(2)

    results['no_threadpool'] = test_no_threadpool_direct_calls(10000)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY - Memory Growth per 10000 Operations")
    print(f"{'='*60}")
    for test_name, growth in results.items():
        print(f"{test_name:25s}: {growth:+.2f} MB")

    # Project to 5 days at 1-second polling
    print(f"\n{'='*60}")
    print("Projected Over 5 Days (1-second UDP polling)")
    print(f"{'='*60}")

    # Assume 1 UDP request per second
    requests_per_day = 86400
    requests_5_days = requests_per_day * 5  # 432,000

    worst = max(results.items(), key=lambda x: x[1])
    scale_factor = requests_5_days / 10000
    projected_mb = worst[1] * scale_factor
    projected_gb = projected_mb / 1024

    print(f"Worst case: {worst[0]}")
    print(f"  Growth: {projected_mb:.0f} MB ({projected_gb:.2f} GB)")

    if projected_gb > 1.0:
        print(f"\n⚠️  POTENTIAL LEAK IDENTIFIED!")
        print(f"  ThreadPoolExecutor with untracked futures may be the culprit")
    else:
        print(f"\n✓  No significant leak from ThreadPoolExecutor pattern")


if __name__ == "__main__":
    main()
