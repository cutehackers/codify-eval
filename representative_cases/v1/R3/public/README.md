# Shared catalog lookup service
Implement `record_service.py` using only the Python standard library (Python 3.11+). A catalog loader is an async callable taking a string key and returning any Python value. It may block on I/O, raise, or cooperate with cancellation.

`RecordService(loader)` exposes `async get(key)`, `async get_many(keys)`, and `async close()`.
- Concurrent gets for the same key share exactly one in-flight loader task. Different keys can load concurrently. Successful results are not cached after the in-flight task completes.
- Cancelling one caller must not cancel shared work or other callers, even if it is the only current caller. The service owns that task until it completes or the service closes.
- All callers waiting on a failed load observe its exception. A subsequent call starts a fresh attempt, including a retry immediately inside the exception handler.
- `get_many` starts loads concurrently, returns values in input order (including duplicates), and returns `[]` for empty input. Cancelling a batch must release its caller tasks without cancelling service-owned loads.
- `close` marks the service closed, cancels all in-flight loads, waits for their cooperative cleanup, and clears ownership. Waiting gets observe `asyncio.CancelledError`. Close is idempotent and concurrent close callers must all wait for cleanup. No new work is allowed once closing begins: both get and get_many (including empty batches) raise `RuntimeError`.
- Do not retain finished tasks. Expose read-only `pending_count` for the number of unfinished service-owned tasks, including work whose callers have cancelled. After completed work or close, it is zero.
- If any load in a batch fails, propagate that error and release every batch-owned caller task. Other service-owned loads continue until completion or close.

Editable path: `record_service.py` only. Preserve public API. Run `python3 -m unittest -v test_smoke.py` from this directory. Implement the behavior fully, not only the smoke tests. No dependencies, network or background processes.
