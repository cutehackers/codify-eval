# D01: Search request lifecycle regression

Repair the multi-module SearchController used by a Flutter search screen. The service cannot cancel pending requests. Use the existing SearchService and SearchState modules and exports from lib/main.dart. No GUI is required.

Public contract:
1. SearchController(SearchService), state, Future<void> search(String), Future<void> retry(), ChangeNotifier listeners and dispose() remain available.
2. Initial state is idle, empty query/items, null message. Search trims input. Every live nonempty invocation calls the service exactly once, synchronously enters loading with its normalized query, empty items and null message, and notifies once. Success enters ready, including an empty result, with null message and notifies once.
3. Only the latest invocation may publish its result or failure, even when query strings match. Obsolete completions produce no state changes or notifications. All service errors are consumed by returned Future<void>. Current errors enter failed with empty items and exactly `Search failed`, never exception details.
4. Empty or whitespace input invalidates pending work, calls no service, enters idle with empty query/items and null message, and notifies once.
5. retry() invokes the failed state's normalized query exactly once. In idle/loading/ready it does nothing and does not notify. Retrying enters normal loading and can succeed or fail again.
6. State item lists are immutable snapshots detached from service-owned mutable lists. Existing states remain unchanged after later requests.
7. dispose() is idempotent. Pending completions cannot mutate state or notify afterward. search/retry after disposal are completed no-ops, make no service call and do not throw. Pending failures still complete their public futures normally.

Change only lib/** and test/**. Keep dependencies and public model/API names. Verify using `flutter pub get --offline` and `flutter test`. Public smoke tests are examples, not the full contract. Evaluation uses additional tests of the requirements above.

The existing `test/smoke_test.dart` is protected. You may add tests but must not edit or remove this smoke test.
