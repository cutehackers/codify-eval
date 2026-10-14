# S02: Transactional configuration import

Implement `implementation.dart` in `lib/` of the supplied repository. Preserve the public
API, modify only this implementation file, and use no external dependencies.
The service runs offline and receives all state through its arguments and
injected repository. Production/provider/device integration is out of scope.

A workspace settings import replaces the complete configuration in one atomic
store operation. Its input is parsed data, not JSON or filesystem content.

1. **C1 Authorization first.** Require `mayImport` and an exact workspace match
   before validating entries. Deny with `forbidden`, `Not allowed`, count zero,
   with no store call, even when the submitted import is malformed.
2. **C2 Batch validation.** An authorized request needs a nonempty workspace ID
   and 1–100 entries. Normalize keys using `trim().toLowerCase()`. A normalized
   key must match `[a-z][a-z0-9_]{0,31}` over the entire key. Normalize values using
   `trim()`. Values must have 1–120 Dart string code units and contain neither LF
   nor CR after trimming. No other value normalization is allowed.
3. **C3 Duplicate validation.** Any duplicate normalized key invalidates the
   entire import, even when both values are identical. This is a strict rejection,
   not first-wins or last-wins. Invalid batches return `invalid`, `Invalid import`,
   count zero, without any store call. Preserve the caller's list and entries.
4. **C4 Atomic replacement.** Validate every entry before calling `replaceAll`
   exactly once with the requested workspace and the full normalized map. Hand
   the store an unmodifiable map so it cannot alter the submitted configuration.
   A valid import replaces all prior keys, rather than merging. The store contract
   guarantees replacement is atomic and that a throwing replacement preserves
   prior state. The service must not attempt individual writes or rollback calls.
5. **C5 Results and errors.** Success is `applied`, `Imported`, and the number of
   unique imported keys. Any store exception is `failed`, `Import failed`, count
   zero. Never expose values, keys, workspace IDs, or exception text in messages.


Completion means the complete contract is implemented, the public smoke passes,
and the change stays within the owned file. Do not infer unstated product policy.
