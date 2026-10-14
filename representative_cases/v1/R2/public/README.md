# R2: Durable notification outbox
Implement `outbox.py` using only Python's standard library. Edit only `outbox.py`. Run `python -m unittest discover -s . -p 'test_*.py' -v` for public smoke tests.

The service persists notifications until delivery succeeds. Implement `Outbox(path)` with `enqueue(tenant, key, payload)`, `claim(tenant, now, lease_seconds, limit)`, `complete(tenant, message_id)`, `retry(tenant, message_id, available_at)`, and `close()`. `path` is a SQLite file. Each method must commit before returning. Reopening the same file restores state.

* `enqueue` takes nonempty string tenant/key and a JSON-compatible payload. Store canonical JSON (`sort_keys=True`, compact separators, `allow_nan=False`). Return the integer message ID. A repeated tenant/key with the same canonical payload returns that ID without changing state. A different payload for that key raises `ConflictError`. Tenants may reuse keys. Invalid arguments raise `ValueError` without any mutation.
* `claim` returns a list of dictionaries containing `id`, `key`, `payload`, and `attempts`. Initial messages are pending, available at 0, attempts 0. Select only the requested tenant's pending messages with available_at <= now or leased messages whose lease deadline <= now. Order by ID. Mark all selected messages leased until now + lease_seconds and increment their attempts, atomically. now must be a finite number >= 0, lease_seconds a finite number > 0, and limit a positive integer (not bool). Invalid arguments raise ValueError before state changes. Zero matches returns []. Competing Outbox instances must not concurrently claim the same unexpired message.
* `complete` permanently marks a currently leased message done. `retry` changes a currently leased message to pending with the supplied finite nonnegative available_at. Both methods are tenant-scoped and return True on success, False for missing, wrong-tenant, pending, or done messages. Invalid retry times raise ValueError before mutation. No wall clock is used. Callers control supplied times.
* A failure while selecting/updating any member of a claim batch rolls back the whole batch. Exceptions propagate. The object remains usable afterward. SQLite triggers may cause such failures.
* Preserve delivered messages for idempotency. IDs must not be reused. No external service, network, dependencies, background worker, or automatic retry scheduler is needed.

Acceptance is correct persisted behavior, including failure recovery and tenant isolation. No clarification or approval is needed for these specified choices.

For operational inspection and deterministic database fault injection, the SQLite message table must expose integer `id` and `attempts` columns. Its table name and other columns are your choice.
