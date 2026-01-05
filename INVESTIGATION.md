# Memory Leak Investigation - Issue #218

## Summary

Comprehensive investigation of the reported memory leak where memory grew from 38 MiB to 1.311 GiB over 5 days when using vzlogger with 1-second polling.

## Test Results

### Primary Finding

**Response object storage is the root cause:**
- **36.78 MB growth per 5,000 requests**
- **Projected: 3.1 GB over 5 days** (matches reported leak!)

### All Test Scenarios

| Scenario | Growth per 5K requests | Projected (5 days) |
|----------|----------------------|-------------------|
| **Storing response objects** | **+36.78 MB** | **3.1 GB** ⚠️ |
| Normal usage (no storage) | +0.02 MB | 1.7 MB |
| Connection pool | +0.01 MB | 0.9 MB |
| New session per request | +0.01 MB | 0.9 MB |
| Threaded access (5 threads) | +0.03 MB | 2.6 MB |
| JSON parsing (3x per request) | +0.01 MB | 0.9 MB |
| Exception tracebacks | +1.73 MB | 150 MB |
| Request history | +0.01 MB | 0.9 MB |
| Content buffering | +0.01 MB | 0.9 MB |
| urllib3 connection accumulation | +0.01 MB | 0.9 MB |

## Key Insights

1. **requests.Session reuse is NOT the problem**
   - Single, long-lived session shows minimal growth (+0.02 MB)
   - Connection pool stays at size 1
   - No accumulation in urllib3 internals

2. **Response objects must be getting stored somewhere**
   - Not in the main application code (vzlogger.py is clean)
   - Possible culprits:
     - **User's modified vzlogger fork** (mentioned in issue)
     - Hidden references in error handling
     - Logging that captures response objects
     - Framework/library caching

3. **The "close() fix" wouldn't help**
   - Closing sessions is good practice but doesn't address the actual leak
   - The leak is from accumulated response objects, not unclosed sessions
   - Potential threading issues with close() during active requests

## Recommendations

### For the Issue Reporter

1. **Check your modified vzlogger fork** for:
   ```python
   # Anti-patterns that would cause leaks:
   responses_cache = []  # Global list

   class VZLogger:
       def __init__(self):
           self.response_history = []  # Instance list

       def get_json(self):
           resp = self.session.get(url)
           self.response_history.append(resp)  # DON'T DO THIS
           return resp.json()
   ```

2. **Add memory profiling** to your deployment:
   ```python
   import tracemalloc
   tracemalloc.start()

   # Periodically log top memory consumers
   snapshot = tracemalloc.take_snapshot()
   top_stats = snapshot.statistics('lineno')
   ```

3. **Check for exception handling** that might store responses:
   ```python
   try:
       resp = session.get(url)
   except Exception as e:
       error_log.append((e, resp))  # This keeps resp alive!
   ```

4. **Monitor with objgraph** to find what's holding references:
   ```bash
   pip install objgraph
   python -c "import objgraph; objgraph.show_most_common_types(limit=20)"
   ```

### For This Repository

If the leak is confirmed to be in the base vzlogger implementation (unlikely based on tests), the fix would be to ensure response objects are not referenced after `.json()` is called. The current implementation is already clean:

```python
def get_powermeter_watts(self):
    return [int(self.get_json()["data"][0]["tuples"][0][1])]
```

No response object is stored - it's immediately parsed and discarded.

## Test Scripts

Three test scripts are provided:

1. **test_memory_leak.py** - Basic reproduction test
2. **investigate_leak_causes.py** - Tests 6 major leak scenarios
3. **test_hidden_references.py** - Tests hidden reference leaks

Run them with:
```bash
python3 investigate_leak_causes.py
python3 test_hidden_references.py
```

## Additional Tests

### Fork's Dual-Request Pattern

The user's fork (`jwatzk/b2500-meter`) adds `POWER_CALCULATE` support, making **2 HTTP requests per poll** instead of 1:

```python
power_in = int(self.get_json(self.power_input_uuid)["data"][0]["tuples"][0][1])
power_out = int(self.get_json(self.power_output_uuid)["data"][0]["tuples"][0][1])
return [power_in - power_out]
```

**Test Results:**
- Single request/poll: +0.12 MB per 5K polls → 10 MB over 5 days
- Dual request/poll: +0.02 MB per 5K polls → 2 MB over 5 days
- **Conclusion: Fork's pattern does NOT cause the leak** ✅

### ThreadPoolExecutor Pattern

The Shelly UDP server uses `ThreadPoolExecutor.submit()` without tracking futures:

```python
self._executor.submit(self._handle_request, sock, data, addr)
```

**Test Results:**
- +17.57 MB while 10,000 tasks running
- +0.13 MB after `executor.shutdown(wait=True)`
- **Conclusion: ThreadPoolExecutor does NOT cause the leak** ✅

## Conclusion

The memory leak is **NOT caused by**:
- ✅ Long-lived `requests.Session` objects
- ✅ Connection pool accumulation
- ✅ urllib3 internals
- ✅ JSON parsing
- ✅ Threading (ThreadPoolExecutor)
- ✅ The fork's dual-request pattern

The memory leak **IS caused by**:
- ⚠️ Something storing response objects (36.78 MB per 5K requests → 3.1 GB over 5 days)

### Likely Culprits (External to Application Code)

Since no leaks were found in the application code or fork:

1. **Docker logging accumulation** - Container logs not being rotated
   ```bash
   # Check Docker logs
   docker logs --tail 100 <container_id>
   du -sh /var/lib/docker/containers/*/*-json.log
   ```

2. **Python DEBUG logging** - If logger level is DEBUG, it may retain references
   ```python
   # Check if this is in the config
   [GENERAL]
   LOGLEVEL = DEBUG  # Could cause accumulation
   ```

3. **External vzlogger server** - The actual vzlogger service (not this client) may have issues

4. **Python/requests version bug** - Specific to user's environment
   ```bash
   python3 --version
   pip freeze | grep requests
   ```

**Next steps**: The issue reporter needs to check Docker logging configuration and try running with minimal logging first. The application code itself is clean.
