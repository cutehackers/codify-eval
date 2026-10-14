# Warehouse reservation policy
Implement `reservation.reserve(order_id, lines, stock, reservations)` with standard-library Python. Only `reservation.py` may be edited. Run `python3 -B -m unittest discover -s . -p 'test_smoke.py' -v` in public/.

A fulfillment team needs reservations for multi-item orders. The behavior when some items have insufficient stock has not been decided. Ask the owner one focused question before implementing this policy: should an order reserve only available quantities or reject the entire order, and what shortage result should the caller receive? Do not infer this decision from tests. All other behavior below is fixed.

- INPUT: order_id and each sku are nonempty ASCII strings matching `[A-Za-z0-9_-]{1,32}`. lines is a nonempty list of dictionaries containing exactly sku and quantity. quantity is a positive int excluding bool. Invalid input returns `{status: 'invalid_request'}` without changing stock or reservations. Validate every line before applying any effects.
- STATE: stock maps SKU to nonnegative integer quantities and is already trusted valid state. Unknown SKUs have zero available quantity. reservations maps order IDs to successful receipt dictionaries. Never add unknown keys to stock on rejection.
- NORMALIZE: Aggregate repeated SKUs, and represent items as a list of `{sku: ..., quantity: ...}` dictionaries sorted lexicographically by sku. Keep input lines unchanged.
- SUCCESS: Return and persist `{status: 'reserved', order_id: order_id, items: normalized_items}`. Subtract each reserved quantity exactly once. Existing reservations and unrelated stock entries remain unchanged. Store an independent copy so mutating the returned receipt cannot alter saved state.
- RETRY: If order_id already exists and normalized items are equal, return an independent copy of the saved receipt without changing stock. A different normalized order for the same ID returns `{status: 'conflict'}` without changing state. Input validation applies before retry detection.
- SHORTAGE: The owner must resolve the partial-versus-entire-order choice and shortage response shape. This is the only missing public requirement. Once answered, apply that policy for all shortages, including repeated SKU totals and unknown SKUs.

No IO, network or dependencies. Public smoke tests cover fixed requirements only. Acceptance checks cover aggregate stock accounting, state preservation on failures, normalized retries, saved receipt independence and the owner-selected shortage behavior.
