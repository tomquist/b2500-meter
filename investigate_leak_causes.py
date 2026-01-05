#!/usr/bin/env python3
"""
Comprehensive memory leak investigation for issue #218.

This script tests various potential causes of the memory leak:
1. Response objects not being released
2. Connection pool issues
3. Threading-related leaks
4. Throttling wrapper interactions
5. JSON parsing accumulation
"""

import requests
import time
import gc
import tracemalloc
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
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
        pass


def get_memory_mb():
    """Get current process memory usage in MB."""
    current, peak = tracemalloc.get_traced_memory()
    return current / 1024 / 1024


def test_response_leak(num_requests=5000):
    """Test if response objects are being leaked."""
    print(f"\n{'='*60}")
    print("TEST 1: Response Object Leak")
    print(f"{'='*60}")

    server = HTTPServer(('127.0.0.1', 8880), MockVZLoggerHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    session = requests.Session()
    start_mem = get_memory_mb()
    print(f"Initial memory: {start_mem:.2f} MB")

    # Store references to responses to see if they're the problem
    responses = []

    for i in range(num_requests):
        try:
            resp = session.get('http://127.0.0.1:8880/test', timeout=5)
            data = resp.json()
            responses.append(resp)  # Keep reference

            if (i + 1) % 1000 == 0:
                gc.collect()
                current_mem = get_memory_mb()
                growth = current_mem - start_mem
                print(f"Request {i+1:5d}: {current_mem:.2f} MB (growth: {growth:+.2f} MB) - {len(responses)} responses stored")
        except Exception as e:
            print(f"Error: {e}")
            break

    final_mem = get_memory_mb()
    total_growth = final_mem - start_mem
    print(f"\nWith {len(responses)} response objects kept:")
    print(f"Final memory: {final_mem:.2f} MB")
    print(f"Total growth: {total_growth:+.2f} MB")

    # Now release references and check memory
    responses.clear()
    gc.collect()
    after_clear = get_memory_mb()
    print(f"After clearing responses: {after_clear:.2f} MB (freed: {final_mem - after_clear:.2f} MB)")

    server.shutdown()
    return total_growth


def test_without_storing_responses(num_requests=5000):
    """Test if memory grows even without storing response objects."""
    print(f"\n{'='*60}")
    print("TEST 2: Without Storing Responses")
    print(f"{'='*60}")

    server = HTTPServer(('127.0.0.1', 8881), MockVZLoggerHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    session = requests.Session()
    start_mem = get_memory_mb()
    print(f"Initial memory: {start_mem:.2f} MB")

    for i in range(num_requests):
        try:
            resp = session.get('http://127.0.0.1:8881/test', timeout=5)
            data = resp.json()
            # Don't store anything

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


def test_connection_pool_leak(num_requests=5000):
    """Test if connection pool accumulates connections."""
    print(f"\n{'='*60}")
    print("TEST 3: Connection Pool Leak")
    print(f"{'='*60}")

    server = HTTPServer(('127.0.0.1', 8882), MockVZLoggerHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    session = requests.Session()
    start_mem = get_memory_mb()
    print(f"Initial memory: {start_mem:.2f} MB")
    print(f"Connection pool size: {len(session.adapters['http://'].poolmanager.pools)}")

    for i in range(num_requests):
        try:
            resp = session.get('http://127.0.0.1:8882/test', timeout=5)
            data = resp.json()

            if (i + 1) % 1000 == 0:
                gc.collect()
                current_mem = get_memory_mb()
                growth = current_mem - start_mem
                pool_size = len(session.adapters['http://'].poolmanager.pools)
                print(f"Request {i+1:5d}: {current_mem:.2f} MB (growth: {growth:+.2f} MB) - Pool size: {pool_size}")
        except Exception as e:
            print(f"Error: {e}")
            break

    final_mem = get_memory_mb()
    total_growth = final_mem - start_mem
    print(f"\nFinal memory: {final_mem:.2f} MB")
    print(f"Total growth: {total_growth:+.2f} MB")

    server.shutdown()
    return total_growth


def test_new_session_each_request(num_requests=5000):
    """Test if creating new sessions causes leaks (anti-pattern but testing)."""
    print(f"\n{'='*60}")
    print("TEST 4: New Session Per Request (Anti-pattern)")
    print(f"{'='*60}")

    server = HTTPServer(('127.0.0.1', 8883), MockVZLoggerHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    start_mem = get_memory_mb()
    print(f"Initial memory: {start_mem:.2f} MB")

    for i in range(num_requests):
        try:
            session = requests.Session()  # NEW SESSION EACH TIME
            resp = session.get('http://127.0.0.1:8883/test', timeout=5)
            data = resp.json()
            # Don't close session

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


def test_threaded_access(num_requests=5000, num_threads=5):
    """Test if threaded access to same session causes leaks."""
    print(f"\n{'='*60}")
    print(f"TEST 5: Threaded Access ({num_threads} threads)")
    print(f"{'='*60}")

    server = HTTPServer(('127.0.0.1', 8884), MockVZLoggerHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    session = requests.Session()
    start_mem = get_memory_mb()
    print(f"Initial memory: {start_mem:.2f} MB")

    counter = {'count': 0}
    lock = threading.Lock()

    def worker():
        for _ in range(num_requests // num_threads):
            try:
                resp = session.get('http://127.0.0.1:8884/test', timeout=5)
                data = resp.json()

                with lock:
                    counter['count'] += 1
                    if counter['count'] % 1000 == 0:
                        gc.collect()
                        current_mem = get_memory_mb()
                        growth = current_mem - start_mem
                        print(f"Request {counter['count']:5d}: {current_mem:.2f} MB (growth: {growth:+.2f} MB)")
            except Exception as e:
                pass

    threads = []
    for _ in range(num_threads):
        t = threading.Thread(target=worker)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    final_mem = get_memory_mb()
    total_growth = final_mem - start_mem
    print(f"\nFinal memory: {final_mem:.2f} MB")
    print(f"Total growth: {total_growth:+.2f} MB")

    server.shutdown()
    return total_growth


def test_json_parsing_leak(num_requests=5000):
    """Test if JSON parsing accumulates memory."""
    print(f"\n{'='*60}")
    print("TEST 6: JSON Parsing Leak")
    print(f"{'='*60}")

    server = HTTPServer(('127.0.0.1', 8885), MockVZLoggerHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    session = requests.Session()
    start_mem = get_memory_mb()
    print(f"Initial memory: {start_mem:.2f} MB")

    for i in range(num_requests):
        try:
            resp = session.get('http://127.0.0.1:8885/test', timeout=5)
            # Parse JSON multiple times to test parser
            data1 = resp.json()
            data2 = json.loads(resp.text)
            data3 = json.loads(json.dumps(data1))

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


def main():
    tracemalloc.start()

    print("Comprehensive Memory Leak Investigation for Issue #218")
    print("=" * 60)
    print(f"Testing with 5000 requests each")
    print()

    results = {}

    # Run all tests
    results['response_objects'] = test_response_leak(5000)
    time.sleep(1)

    results['no_storage'] = test_without_storing_responses(5000)
    time.sleep(1)

    results['connection_pool'] = test_connection_pool_leak(5000)
    time.sleep(1)

    results['new_session_each'] = test_new_session_each_request(5000)
    time.sleep(1)

    results['threaded'] = test_threaded_access(5000, 5)
    time.sleep(1)

    results['json_parsing'] = test_json_parsing_leak(5000)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY - Memory Growth per 5000 Requests")
    print(f"{'='*60}")
    for test_name, growth in results.items():
        print(f"{test_name:20s}: {growth:+.2f} MB")

    # Find the worst offender
    worst = max(results.items(), key=lambda x: x[1])
    print(f"\nWorst offender: {worst[0]} with {worst[1]:.2f} MB growth")

    # Project to 5 days at 1-second interval
    requests_per_day = 86400
    requests_5_days = requests_per_day * 5
    scale_factor = requests_5_days / 5000
    projected = worst[1] * scale_factor

    print(f"\nProjected over 5 days (432,000 requests):")
    print(f"  {worst[0]}: {projected:.0f} MB ({projected/1024:.2f} GB)")

    if projected > 1000:  # More than 1GB
        print(f"\n⚠️  LIKELY CAUSE IDENTIFIED!")
        print(f"   {worst[0]} shows significant growth")
    else:
        print(f"\n✓  No severe leak detected in these tests")
        print("   The issue may require longer-term testing or different conditions")


if __name__ == "__main__":
    main()
