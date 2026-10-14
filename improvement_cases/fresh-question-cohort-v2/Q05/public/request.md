# Warehouse stock reservation

Implement `ReservationService.reserve` for the warehouse app. An operator submits an order ID and positive quantities of SKU IDs to reserve against a warehouse. The UI uses the outcome to decide whether to proceed with the order. Reserving stock changes what other operators can reserve.

An example stock snapshot contains SKU-A quantity 7 and SKU-B quantity 1. An order includes SKU-A quantity 3 and SKU-B quantity 2.

Edit only `lib/implementation.dart`. The provided models and in-memory transactional store are protected. Do not add dependencies. Run the supplied Dart/Flutter checks. No device, network or provider is required.

## Contract

- C01: Use the supplied identity tenant to authorize the requested warehouse before validation or content reads. Missing and inaccessible warehouses return `not_found` with empty result lists. Never expose another tenant's stock or change its data.
- C02: After access validation, reject a whitespace-only order ID, empty rows, whitespace-only SKU ID, quantity zero or less, and duplicate exact SKU IDs with `invalid_request`, before stock reads or writes. IDs are compared exactly. Trimming is only for detecting blank values.
- C03: Read a stock snapshot after C02. Every SKU must exist. Unknown SKUs return `invalid_request` before looking up an existing order or making writes.
- C04: An order's identity is scoped to its warehouse. Identical rows under the same order ID return the recorded outcome without writes. Row order does not affect request identity. Changed SKU IDs or quantities return `conflict` without writes. Results from a retry retain their original order.
- C05: When every requested quantity is available, reserve exactly those quantities in request order and decrement each stock quantity once. Return `ok` with those reserved rows and no shortage rows.
- C06: Stock must never become negative. Reserved quantities must not exceed requested quantities. Shortage rows list the SKU, requested quantity and snapshot available quantity in request order. Returned rows must agree with persisted effects. Unrelated stock stays unchanged.
- C07: Persist stock changes and recorded outcomes together using the supplied atomic store operation. A storage failure returns `storage_failure` with empty result lists and leaves both unchanged. Do not expose exception text. Only `ok` outcomes are recorded.
- C08: The operation is synchronous. The supplied store provides atomic commit and isolated snapshot copies. Adapter construction, concurrency, UI and persistence infrastructure are outside this change.

Validation order is C01, C02, C03, C04, allocation, C07. The supplied store has nonnegative starting stock. `ok`, `not_found`, `invalid_request`, `conflict` and `storage_failure` are the complete result codes.
