# P02 implementation task

Implement the published contract in exactly `lib/event_processor.dart` and `lib/checkpoint_codec.dart`. Every other starting file is protected. Do not alter dependencies, APIs, tests, helpers or generated files. Private helpers in the two editable files are allowed. Run `dart analyze` and `flutter test --reporter expanded` offline. No GUI, network, providers or credentials are required.

## Protected public API

The fixture author must supply these declarations unchanged. Public API names, field types, result codes, and semantics are part of the task. Constructors create immutable value objects. Collection fields are defensive unmodifiable copies. There are no implicit clocks, randomness, global singletons, or disk accesses.

```dart
enum ProcessorCode {
  ok, unauthorized, busy, notInitialized, invalidBatch,
  replayConflict, stockOutOfRange, capacityExceeded,
  concurrentCommit, storageUnavailable, corruptCheckpoint,
}

class AccessContext {
  AccessContext({required Set<String> allowedTenants});
  final Set<String> allowedTenants;
}

class TenantView {
  TenantView({required String tenantId, required int revision,
    required Map<String, int> stock, required int processedCount});
  final String tenantId;
  final int revision;
  final Map<String, int> stock;
  final int processedCount;
}

class ProcessorResult {
  ProcessorResult({required ProcessorCode code, TenantView? view,
    int accepted = 0, int replayed = 0, bool recovered = false});
  final ProcessorCode code;
  final TenantView? view;
  final int accepted;
  final int replayed;
  final bool recovered;
}

class StoreRecord {
  StoreRecord({required int revision, String? primary, String? recovery});
  final int revision;
  final String? primary;
  final String? recovery;
}

abstract interface class CheckpointStore {
  Future<StoreRecord> read(String tenantId);
  Future<bool> compareAndSwap(String tenantId, int expectedRevision,
    StoreRecord replacement);
}

class StoreUnavailable implements Exception {}

abstract interface class IntegrityService {
  String sha256Hex(List<int> bytes);
  String signCheckpoint(List<int> payload);
  bool verifyCheckpoint(List<int> payload, String tag);
}

class CheckpointState {
  CheckpointState({required String tenantId, required int revision,
    required Map<String, int> stock, required Map<String, String> replays});
  final String tenantId;
  final int revision;
  final Map<String, int> stock;
  final Map<String, String> replays;
}

class InvalidCheckpoint implements Exception {}
```

The two editable files expose exactly these entry points. Implementations may introduce private helpers inside these files.

```dart
// lib/checkpoint_codec.dart
class CheckpointCodec {
  CheckpointCodec(IntegrityService integrity);
  String encode(CheckpointState state);
  CheckpointState decode(String checkpoint,
    {required String expectedTenant, required int expectedRevision});
}

// lib/event_processor.dart
class EventProcessor {
  EventProcessor({required String tenantId, required AccessContext context,
    required CheckpointStore store, required IntegrityService integrity});
  TenantView? get current;
  Future<ProcessorResult> restore();
  Future<ProcessorResult> ingest(String batchJson);
}
```

`current` returns null until successful restore, and always returns null for a processor whose bound tenant is unauthorized. A returned view must not change after a later operation. The processor's private replay ledger must not be exposed through `TenantView`.

Store contract: an absent tenant reads as `(revision: 0, primary: null, recovery: null)`. CAS checks the current record revision atomically. On a mismatch it returns false and performs no write. On success it atomically installs the entire replacement and returns true. It may throw `StoreUnavailable` before committing and must then leave the durable record unchanged. It never throws after committing. Read may also throw `StoreUnavailable`. The fixture controls these failures and scheduling. The processor does not need to solve ambiguous commit acknowledgments or a store that violates this contract.

Integrity contract: SHA-256 returns 64 lowercase hexadecimal characters. Checkpoint tags are HMAC-SHA256 over the exact supplied payload bytes, also 64 lowercase hexadecimal characters, under a service-owned fixture key. `verifyCheckpoint` is a trusted constant-time comparison boundary and returns false for bad tags. The service is synchronous and does not fail for valid byte lists. The processor must use it, not implement a replacement hash or MAC. The fixture key and helper are testing resources, not a claim that source-visible fixture keys are production secrets.

## R1: authorization, isolation, and observable errors

The constructor binds one processor to one tenant. Tenant IDs match ASCII `[a-z][a-z0-9_-]{0,31}`. The constructor performs no I/O and does not throw. Each operation first checks exact membership of the bound tenant in `allowedTenants`. A missing membership or malformed bound tenant returns `unauthorized`, with null view, zero counts, and `recovered: false`. It must not call the store or integrity service, decode caller input, or mutate any state. No operation can request a different tenant, and the JSON batch must not contain a tenant selector.

Failures return a `ProcessorResult`, not exception text. For every non-ok result, `accepted` and `replayed` are zero and `recovered` is false. Its view is the unchanged pre-operation current view, except unauthorized always returns null. No raw event body, checkpoint payload, key, authenticator, or internal exception is included in a result. Integrity failure, tenant mismatch, revision mismatch, malformed checkpoint, and mutually inconsistent valid copies all become `corruptCheckpoint` at the processor boundary.

Two overlapping operations on the same processor are not queued. After authorization, the second invocation returns `busy` immediately and performs no I/O or integrity work. The first invocation keeps the instance busy until its Future settles, including a store exception. Different processor instances are independent.

## R2: public batch grammar and complete validation

`ingest` accepts a JSON string with exactly one effective root field, `events`, whose value is a list containing 1 through 100 events. UTF-8 encoding of the full string must be at most 65,536 bytes. Every event is a JSON object with exactly the fields `id`, `sku`, `delta`, and `occurredAt`.

- `id` and `sku`: ASCII `[A-Za-z0-9][A-Za-z0-9_-]{0,63}`. Case-sensitive, with no trimming or normalization.
- `delta`: a Dart `int` after `jsonDecode`, from -1,000,000 through 1,000,000, excluding zero. A JSON floating representation such as `1.0` is invalid even when numerically integral.
- `occurredAt`: exactly `YYYY-MM-DDTHH:mm:ss.SSSZ`, ASCII, year 2000 through 2099, real Gregorian calendar date, hour 00..23, minute and second 00..59, millisecond 000..999. Offsets, omitted milliseconds, whitespace, leap seconds, and DateTime-normalized overflow dates are invalid.
- Timestamp is event content used for replay equality, not an ordering or expiry rule. Events may arrive with earlier or equal timestamps. No current-time policy exists.
- Missing fields, extra fields, wrong types, malformed JSON, excess bytes, or an invalid event produce `invalidBatch`.

Use Dart SDK `jsonDecode` semantics for input objects. If input JSON repeats an object key, its last occurrence determines the effective object. This policy is explicit and is not separately graded as an ambiguity. Object key order and JSON whitespace do not affect event equality. Validate all effective event objects in list order before replay lookup or any inventory transition. This makes a malformed later event yield `invalidBatch` even when an earlier well-formed event would conflict or underflow. No store call occurs for invalid input.

## R3: replay identity and ordered stock transitions

The event fingerprint is `sha256Hex(utf8.encode(jsonEncode([id, sku, delta, occurredAt])))`. Do not fingerprint raw JSON, drop a field, or include the caller's JSON field order. IDs are tenant-local.

For a structurally valid batch, copy the current stock and replay ledger into private working state. Process events in list order:

1. If its ID is already present in working replays and the fingerprint matches, count one replay and make no stock change.
2. If its ID is present but its fingerprint differs, fail with `replayConflict`.
3. For a new ID, compute `currentStockForSku + delta`, with absent SKU meaning zero. The result must be 0 through 2,147,483,647. Otherwise fail with `stockOutOfRange`.
4. Before adding a valid new ID, if working replays already has 10,000 entries, fail with `capacityExceeded`. Stock validation precedes this capacity check for this event.
5. Record the new fingerprint, count one accepted event, and set the new stock. Omit a SKU key when its stock becomes zero.

Repeated equal events within the same batch count as accepted once and replayed thereafter. A later conflicting repeat invalidates the entire batch. If multiple semantic failures are possible, the first failure encountered in the list wins, using the per-event order above. Stock changes are sequential, so a removal before a replenishment may fail although the final mathematical sum would be valid.

All-replay success returns `ok`, current unchanged view, accepted zero, and the replay count. It does not call CAS, increment revision, or rewrite damaged checkpoint copies. No event ages out of the replay ledger in this pilot. At capacity, exact replays continue to work.

## R4: atomic optimistic commit and partial failure

An ingest requires a successful earlier restore on the same instance. An authorized, idle, uninitialized processor returns `notInitialized` before inspecting batch JSON.

If the valid staged batch contains new events, create the next checkpoint at exactly current revision + 1. Revisions range from 0 through 2,147,483,647. If revision is already at the maximum, return `capacityExceeded` after successful semantic staging and before encoding or CAS. Persist one replacement record whose `primary` and `recovery` are identical encoded checkpoint strings. Make exactly one CAS call with the current revision as expectedRevision. Do not perform a separate read or retry within ingest.

CAS false produces `concurrentCommit`. CAS `StoreUnavailable` produces `storageUnavailable`. Neither updates local state, counts, revision, or durable data. The caller resolves a concurrent commit by explicitly calling restore and retrying. On CAS success only, replace the local state with staged state and return `ok` with the new immutable view and exact counts. A failed later event must cause no encoding or CAS call and leave all earlier staged changes invisible. Batch persistence cannot be decomposed into event-by-event writes.

The public operation order is authorization, same-instance busy check, initialization check, complete structural validation, sequential semantic staging, revision capacity check, checkpoint encoding, one CAS, local publication. These are the complete precedence rules. Restore does not require initialization.

## R5: authenticated checkpoint format

`CheckpointCodec.encode` accepts a valid CheckpointState. Invalid states throw `InvalidCheckpoint`; validation uses the same tenant, revision, SKU, stock, ID, replay count, and lowercase SHA-256 grammar defined here. Zero stock keys, empty replay IDs, duplicate effective identities, and unknown properties are not valid persisted states. An empty state at revision zero is encodable. A state may have empty stock with nonempty replays.

The canonical payload is UTF-8 bytes of SDK `jsonEncode` of this insertion-ordered map:

```text
{
  "schema": 1,
  "tenant": <tenantId>,
  "revision": <revision>,
  "stock": <map of nonzero stocks sorted by ASCII SKU ascending>,
  "replays": <map of ID -> fingerprint sorted by ASCII ID ascending>
}
```

The canonical outer string is SDK `jsonEncode` of the insertion-ordered map `{"payload": base64Encode(payloadBytes), "tag": integrity.signCheckpoint(payloadBytes)}`. The base64 representation is standard padded Dart SDK base64. No newline is appended. Codec output must be deterministic for equal states, including map insertion order differences. There are no optional fields and no legacy schema migration.

`decode` verifies all of the following, otherwise throwing `InvalidCheckpoint`:

1. Outer string parses to exactly payload and tag strings and equals canonical outer re-encoding. Tag has 64 lowercase hex characters. Payload base64 decodes and equals canonical base64 re-encoding.
2. Call `verifyCheckpoint` on the decoded payload bytes before interpreting their JSON content. A false result fails immediately.
3. Payload is strict UTF-8 (`allowMalformed: false`) and parses to the exact five fields above. Schema is Dart int 1. Types and value bounds match valid state, revision equals expectedRevision, and tenant equals expectedTenant. There are at most 10,000 replay entries. Stock contains only nonzero integers at most 2,147,483,647.
4. Canonical payload bytes reconstructed from validated state equal the supplied payload bytes. This rejects duplicate persisted object keys, alternate number forms, whitespace, unknown fields, and unsorted payload map keys even when authenticated.

Decode has no external state and never repairs data. Its returned maps are immutable. The fixture may use a properly authenticated malformed payload to exercise state validation separately from MAC validation. This is public behavior, not a secret-key attack requirement.

## R6: restore, recovery, and failure preservation

`restore` makes exactly one read of the bound tenant. A store failure produces `storageUnavailable`. A record with negative or excessive revision is corrupt. The only empty-store form is revision zero and both checkpoint strings null. It successfully initializes an empty local state with revision zero and recovered false. A nonempty checkpoint record at revision zero may also be valid if its decoded state is valid.

For other records, independently try to decode each non-null copy against the bound tenant and record revision:

- Both valid and exactly equal strings: load the state, return `ok`, recovered false.
- Exactly one valid: load that state, return `ok`, recovered true. The other may be null, malformed, tampered, wrong-tenant, or wrong-revision.
- Both valid but different strings, or no valid copy: `corruptCheckpoint`.

The recovery copy is redundant data for the same committed revision, not an older revision or a historical backup. Restore never lowers a store revision, writes a repair, calls CAS, or treats a signed foreign tenant as valid. A subsequent novel successful ingest rewrites both copies and completes repair. An all-replay ingest leaves persisted bytes untouched.

A failed restore preserves the prior initialized flag and the exact prior local state. Thus a previously initialized instance may keep its old state after a failed refresh and attempt ingest using its old revision; CAS will detect an external revision change. A first failed restore remains uninitialized. A successful restore replaces the local state only after the full record has been checked, and returns accepted zero and replayed zero. No partial decoded copy becomes visible before the recovery decision finishes.

