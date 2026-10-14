# Atomic transfer batches

Implement BatchValidator and BatchService in the two allowed files:
`lib/batch_validator.dart` and `lib/batch_service.dart`. All other public files,
including contracts, fake support, tests, README and pubspec, are protected.
This is an offline service/domain feature. Flutter supplies the test framework.
There is no GUI, provider, device, network or production qualification.

## Public requirements

R01 Validation: owner, key, transfer ID and account IDs are nonempty, have no
leading/trailing whitespace and contain no NUL. Transfers contain 1..20 items,
unique transfer IDs, distinct from/to IDs, and integer amounts 1..1,000,000,000.
Invalid commands return FailureCode.invalid without opening a store transaction.
The validator returns either a ValidatedBatch or the typed invalid result.

R02 Identity: fingerprint includes owner and every transfer's ID, source,
destination and amount. It is deterministic, insensitive to input order, and
unambiguous even when identifiers contain punctuation. The key identifies a
request within its owner and is not part of the payload fingerprint. No exact
fingerprint serialization is required.

R03 Authorization: actor.owner must equal command.owner. Before validation,
replay or store access, await canTransfer on every invocation whose actor owner
matches. A mismatch or false decision returns forbidden. Never access the store
before authorization completes. Accounts on both sides must belong to the
command owner. Foreign accounts produce forbidden. The authorizer can revoke
access between calls. The service trusts its boolean decision for that invocation.

R04 Success: apply the summed net delta for each touched account. Evaluate final
balances, not intermediate transfer ordering. This allows a cycle or incoming
transfer to fund outgoing transfers in the same batch. Final balances must be
0..1,000,000,000. Return missingAccount for an absent account,
insufficientFunds for a negative final balance, and balanceLimit for an excessive
final balance. No precedence is required when multiple account errors coexist.
Return a receipt with owner, key, fingerprint, transferCount and balances of all
and only touched accounts. Its balances are an immutable snapshot.

R05 Atomicity: all account changes and the receipt belong in one store transaction.
Any business rejection or commit failure leaves all pre-transaction accounts and
receipts intact. Never save a receipt for rejected work. The provided store
serializes across all service instances and rolls callback mutations back on
failure before commit. The service must use that transaction interface, and not
maintain authoritative local state.

R06 Idempotency: within the atomic transaction, a previously committed owner/key
with equal fingerprint returns the original receipt, without transfers being
applied again. Replay keeps the original balances even if other batches changed
accounts later. The same owner/key with a different valid payload returns
conflict and changes nothing. Reordering is an equal payload. Different owners
may use the same key. Invalid payloads remain invalid even for a used key.

R07 Concurrency: simultaneous identical requests, including different service
instances, apply once and all successful callers receive the same receipt values.
Different payloads racing on one owner/key have one winner and a conflict loser.
Different keys spending the same funds cannot overspend. Use the store's atomic
serialization, which covers service instances and restarts.

R08 Recovery: StoreUnavailable may happen before commit or after durable commit,
including after an asynchronous delay. Return unavailable for that invocation.
A subsequent call, including from a new service instance, must safely retry:
apply once if nothing committed, replay if it committed, and reject a changed
payload if it committed. Do not automatically retry an unavailable invocation.
A failed invocation must not poison later work or leave service locks blocked.

R09 Safe failures: expected business errors use the listed FailureCode values.
StoreUnavailable maps to unavailable. Unexpected exceptions from authorization,
validation or transaction map to internal. No exception may escape submit.
Failed BatchResult has no receipt, the relevant failure code, and exactly the
public message `Batch could not be completed.`. Never expose exception details,
account data, owner names or stack traces through the result. Success has no
failure or message. BatchRejected carries a business code through the boundary.

The public test fake has controllable awaited authorization, beforeCommit and
afterCommit hooks. They allow deterministic failures and scheduling without any
real provider. Hooks execute inside the store's serialization. Its account and
receipt maps are test observation surfaces, not service APIs. Seeded accounts
have valid balances. Tests may reuse the fake with multiple service instances.
Public smoke tests deliberately pass the starting stubs. Implementing these
requirements is necessary for behavioral acceptance.
