# S01: Tenant document commands

Implement `implementation.dart` in `lib/` of the supplied repository. Preserve the public
API, modify only this implementation file, and use no external dependencies.
The service runs offline and receives all state through its arguments and
injected repository. Production/provider/device integration is out of scope.

This command service edits tenant-scoped documents.

1. **D1 Authorization first.** An actor may execute a command only when their
   tenant equals the command tenant and `writableDocumentIds` contains the document
   ID. Check this before validation and before any store method. Unauthorized
   commands return `forbidden`, message `Not allowed`, and no revision. Neither
   reads nor writes are allowed on this path, even for malformed commands.
2. **D2 Validation.** Authorized commands require nonempty tenant/document IDs and
   a nonnegative expected revision. Rename requires a non-null title whose trimmed
   value has 1–80 Dart string code units. Invalid commands return `invalid`,
   `Invalid command`, without store access. Archive ignores the title argument.
3. **D3 Scope.** Load exactly the requested tenant and document. No returned
   record is `missing` with `Document unavailable`. If the store returns a record
   with a different ID or tenant, return `forbidden` without writing.
4. **D4 Concurrency and lifecycle.** A mismatched current revision or an already
   archived document is `conflict` with `Document changed`, without a write.
   Otherwise rename stores the trimmed title and retains active state. Archive
   retains the current title and marks archived. Both increment revision once and
   call `compareAndSave` once with the original expected revision.
5. **D5 Safe result.** A false compare-and-save or any store exception becomes
   `conflict`, `Document changed`, with no revision. Success returns `applied`,
   `Applied`, and the new revision. Do not expose exception text, titles, or tenant
   identifiers in messages. Do not mutate input objects or the actor's grant set.
   The store owns its compare-and-save atomicity.


Completion means the complete contract is implemented, the public smoke passes,
and the change stays within the owned file. Do not infer unstated product policy.
