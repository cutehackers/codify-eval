# Tenant-scoped background-job queue

Implement `QueueService` in `lib/implementation.dart`. This is an offline service for a Flutter application's background jobs. Jobs carry opaque string payloads. The service manages submission, claiming, retries, and settlement. It does not execute jobs.

Only `lib/implementation.dart` may change. Preserve the provided public classes, fields, enum values, constructor signatures, and method signatures. Private helpers may be added. Do not change dependencies or other files. Use only existing Dart/Flutter libraries. No network, devices, providers, or real clock are needed. Run `flutter test`. The public smoke tests are examples, not the full contract.

All product policies are specified below. No product clarification is necessary.

## R01: API and trusted dependencies

`enqueue(principal, tenantId, key, payload)` requires producer permission. `claim`, `complete`, and `fail` require worker permission. A principal is supplied by the caller's trusted authentication layer. Its tenant, user ID, and permissions are authoritative. A producer does not automatically have worker permission or vice versa.

The injected clock returns valid UTC timestamps, and may advance between retries. Never use `DateTime.now`. `IdSource` returns candidate job or lease IDs and may throw or produce invalid/reused candidates. IDs need not be consecutive. The store may return malformed or foreign snapshots, throw, or lose a compare-and-swap race. Snapshot reads are point-in-time immutable values. Store CAS is atomic over one tenant: true replaces all state, false or an exception writes nothing. Other callers may commit between reads and CAS. CAS receives the old revision and a next snapshot with revision exactly old + 1. A fresh tenant has an empty revision-zero snapshot.

## R02: Authorization, input, and result precedence

First check exact principal-tenant equality and the required permission. If either fails, return `unavailable`, regardless of malformed input, without calling store, clock, or ID source. Next validate inputs. IDs, tenant IDs, user IDs, and submission keys are ASCII strings matching the complete string `[A-Za-z0-9_-]{1,64}`. Payload is a nonempty string of at most 4096 Dart string code units. Do not trim, normalize, parse, log, or compare payloads by anything other than exact string value. `fail` delay is an integer number of seconds in 0..300 inclusive. Invalid authorized input returns `invalidInput` without dependency calls.

Then read and validate the snapshot (R03) before using its records, including when returning replays. A malformed snapshot returns `storageUnavailable`. For valid snapshots apply operation-specific policies below. All store, clock, and ID-source exceptions become `storageUnavailable`. Every non-`ok` result has a null job. `ok` enqueue and claim results contain a job. `ok` complete and fail results have a null job. Do not throw backend exceptions, add diagnostic fields, or expose backend text. Authorized enqueue and claim may return the job's payload. Do not log payloads or backend details.

## R03: Returned snapshot integrity

Reject the entire snapshot before any ID generation or write if any condition below fails. Do not filter foreign or malformed rows and continue.

- Snapshot tenant equals requested tenant and revision is nonnegative.
- Every job map key is a valid ID equal to that job's ID. Every job tenant equals the snapshot tenant. Payload meets R02. Creation and availability timestamps are UTC. Attempts are in 0..3.
- A leased job has attempts in 1..3, valid non-null worker and lease IDs, a non-null UTC expiration, and its lease ID is in `usedLeaseIds`. Active lease IDs are distinct across jobs.
- Every non-leased job has null worker, lease, and expiration fields. A pending job has attempts in 0..2. A completed job has attempts in 1..3. A failed job has attempts exactly 3.
- Every `usedLeaseIds` entry is a valid ID.
- Each submission map key is a valid key. Its job ID is valid and references an existing job whose payload exactly equals the submission payload. Its payload meets R02.
- Each settlement map key is a valid lease ID in `usedLeaseIds`, is not an active job's lease ID, and references an existing job and a valid worker ID. Its delay is in 0..300. A completion settlement has delay zero.

These checks are exhaustive. Do not invent relationships such as requiring every job to have a submission, all historical leases to have settlements, or timestamps to match a historical duration. Records may have been created by other compatible producers.

## R04: Submission and idempotency

Submission keys are tenant-wide, independent of producer user ID. For a new key, create one pending job with attempts zero, creation and availability equal to the current injected time, no lease fields, and the exact payload. Persist the job and submission record in one CAS. Obtain its ID from `nextJobId`. An invalid ID or an ID already present in the tenant's jobs returns `storageUnavailable` with no write. Do not try a second candidate within the same attempt.

An existing key with identical payload returns `ok` and that job's current snapshot record, including any later state or lease. It does not write, generate IDs, or change the job. A different payload returns `requestConflict`. A failed write reserves neither job nor key. An identical submission by another authorized producer in the same tenant follows the same rule.

## R05: Claim eligibility and ordering

Pending jobs are eligible when `availableAt <= now`. Leased jobs are eligible when `expiresAt <= now`, except for the exhaustion rule in R08. Completed and failed jobs are never eligible. Pick the eligible job with earliest `createdAt`. Break ties with ascending Dart `String.compareTo` on job ID, independent of map insertion order.

One successful claim increments attempts by one, sets state to leased, sets the principal user as worker, and sets expiration to current time + 60 seconds. Preserve payload, creation, availability, and job identity. Obtain a lease ID from `nextLeaseId`. It must be valid and absent from the tenant's permanent `usedLeaseIds`. Retain all prior used lease IDs forever. Invalid or reused candidate returns `storageUnavailable` without committing anything from that attempt, including exhaustion cleanup. Reclaim by the same worker still requires a fresh lease ID.

## R06: Settlement authorization and exact expiry

For a lease with no prior settlement record, complete or fail succeeds only when the job exists, is leased, the worker equals the principal user, the supplied lease ID equals the current lease ID, and `now < expiresAt`. Otherwise return `unavailable` without writing. Thus unknown jobs/leases, wrong workers, expired leases, and stale leases share one result. At exact expiration a lease cannot settle and can be reclaimed.

Successful completion sets state completed, preserves attempts and availability, clears all lease fields, and records the settlement in the same CAS. Successful failure before attempt three sets pending, preserves attempts, sets availability to current time + delay, clears lease fields, and records settlement in the same CAS. Completion on attempt three is allowed. Neither operation generates IDs.

## R07: Historical settlement replay

Look up settlement by supplied lease ID before checking current job lease or time. If the receipt's job ID or worker differs from the supplied job ID or principal user, return `unavailable`. Otherwise an exact operation replay returns `ok` without writing, even after expiration or later claims/settlements. Exact failure replay includes the same delay. Completion versus failure, or a changed failure delay, returns `settlementConflict`. A historical replay never changes the current job. Complete receipts use delay zero. Keep all receipts permanently.

## R08: Third-attempt exhaustion and empty results

Failure on attempt three sets failed, clears lease fields, preserves attempts, sets availability to current time + supplied delay, and records the failure receipt. It cannot be claimed again.

A claim operation examines all jobs. Every expired leased job at attempt three becomes failed with attempts three, clears lease fields, and preserves availability. Expiration creates no settlement receipt. Skip these jobs and claim the next eligible job in the same atomic tenant CAS. If only exhaustion cleanup is needed, commit it and return `empty` with a null job. If neither a claim nor cleanup is possible, return `empty` without writing or generating IDs. No fourth claim attempt is permitted.

## R09: Conflict recovery and atomicity

Commit complete tenant snapshots. Never mutate store-returned snapshots or persist partial submission, lease, receipt, or exhaustion state. On CAS false, discard the proposed snapshot, read again, revalidate it, obtain current time again, and recompute the operation, including authorization-dependent ownership, replay, ordering, availability, and exhaustion. IDs consumed by a failed attempt may be skipped. Stop after eight CAS failures and return `busy` with no successful service commit. A no-write result found on a later fresh read may return immediately. Exceptions do not retry. A successful CAS is the operation's commit point. Do not read again after it to verify or replace its result.

## R10: Preservation and implementation scope

Preserve unrelated tenant records and historical keys/receipts/used IDs. Public value constructors detach caller collections and expose immutable collections as provided. Maintain those properties. Implement the service, including concurrent calls on the same or separate service instances sharing a store. Do not add process-local ownership or deduplication state that replaces persisted decisions.

Completion means the service obeys these public behaviors and the existing project tests run offline. This task does not ask for UI, persistence-engine implementation, background execution, logs, documentation changes, or external delivery.
