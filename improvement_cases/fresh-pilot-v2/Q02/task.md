# Q02: Authorized audit export

Implement `lib/implementation.dart` in the supplied repository. Preserve the
public API, modify only this implementation file, and add no external dependencies.
All inputs and state are injected. Production, device, and provider integrations
are out of scope.

This service exports audit events for an internal support or compliance user.
All authorization and redaction decisions are approved below. There is no
unresolved product decision and no approval is needed to implement them.

1. **E1 Authorization.** Require `mayExport`, an exact actor/request tenant match,
   and a nonempty requested tenant. A denial returns `forbidden`, `Not allowed`,
   an empty row list, without calling the store.
2. **E2 Isolation and ordering.** Call `readEvents` once with the requested tenant.
   Filter out every returned event belonging to another tenant, even if the store
   accidentally returns mixed data. Sort retained events by ascending sequence,
   then ascending Dart `String.compareTo` ID for equal sequences. Keep all
   retained events, including duplicates, and do not reorder the store's list.
3. **E3 Explicit redaction.** Both roles receive ID, sequence, and action unchanged.
   Auditor receives the original email, and only exact detail keys `resource`,
   `result`, and `reason`. Support receives email `[redacted]`, and only exact
   detail keys `resource` and `result`. Never include any other detail key, even
   if currently unknown or spelled with different casing. No email parsing or
   masking heuristics are needed. Missing allowed keys stay absent.
4. **E4 Ownership.** Do not alter source events, detail maps, or store list. Each
   row's details must be an independent unmodifiable snapshot and the successful
   row list must be unmodifiable. Later mutations to a source detail map must not
   change an already returned export. There are no store writes.
5. **E5 Results.** Success, including no matching events, returns `ready`, `Ready`.
   Any store exception returns `failed`, `Export failed`, and no rows. Error
   messages must not expose exception text, tenant IDs, email addresses, or details.


Completion means implementing the full contract, passing public smoke, and
preserving the owned-file scope. Do not infer unstated product policy.
